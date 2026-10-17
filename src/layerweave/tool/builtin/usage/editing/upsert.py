"""按同层精确匹配键新增或更新，保留已有身份；不删除缺席的记录。"""
from functools import partial

from layerweave.support import records
from layerweave.support.api import PositionMath, run_operation
from layerweave.support.configuration.loader import DEFAULT_ROOT
from layerweave.support.feedback import InputError, target
from layerweave.support.providers import DEFAULT_CHECKER, optional_checker
from layerweave.support.transaction import require_write_session


def _key_path(match_by):
    if not isinstance(match_by, str):
        raise InputError("match_by 应为 name 或 information 下的字段路径", field="match_by")
    parts = match_by.split(".")
    if match_by != "name" and (len(parts) < 2 or parts[0] != "information" or not all(parts)):
        raise InputError("match_by 应为 name 或 information 下的字段路径，例如 information.source_key", field="match_by")
    return parts


def _key(record, path):
    value = record
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    if (type(value) is str and value != "") or (path[0] == "information" and type(value) is int):
        return (type(value), value)  # 字符串 "1" 和数字 1 是不同的稳定键。
    return None


def upsert_objects_in_session(write, project_id, layer_id, objects, *, match_by="name"):
    """返回 scope/counts/items；每项含匹配值、动作和对象记录，失败由外层回滚。"""
    connection = require_write_session(write).connection
    path = _key_path(match_by)
    if not isinstance(objects, list):
        raise InputError("objects 需要对象字段字典的列表", field="objects")
    layer = write.read("layer", project_id=project_id, id=layer_id) if layer_id is not None else None
    if layer is None:
        raise InputError(f"层 ({project_id}, {layer_id}) 不存在", code="missing_reference", field="layer_id",
                         target=target("layer", project_id, layer_id))
    indexed = {}
    for row in write.read("object", project_id=project_id, filters={"layer": layer_id}):
        key = _key(row, path)
        if key is not None:
            indexed.setdefault(key, []).append(row["id"])
    plans, seen = [], set()
    for index, payload in enumerate(objects):
        if not isinstance(payload, dict):
            raise InputError("每项需要对象字段字典", field="objects", request_index=index)
        key = _key(payload, path)
        if key is None:
            raise InputError("匹配键需要非空字符串；information 下也可使用整数", code="missing_match_key",
                             field=match_by, request_index=index)
        if key in seen:
            raise InputError("本批次重复提供了同一匹配键", code="duplicate_match_key", field=match_by,
                             match_value=key[1], request_index=index)
        seen.add(key)
        ids = indexed.get(key, [])
        if len(ids) > 1:
            raise InputError(f"同层匹配到多个对象 {ids}，请改用稳定键或按明确 ID 更新", code="ambiguous_match",
                             field=match_by, match_value=key[1], candidate_ids=ids, request_index=index)
        if "layer" in payload and payload["layer"] != layer_id:
            raise InputError("对象的 layer 与本次目标层不一致", field="layer", request_index=index)
        plans.append((key[1], ids[0] if ids else None, {**payload, "layer": layer_id}))

    math = PositionMath(partial(records.read, connection), project_id)
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    items = []
    for index, (value, id, payload) in enumerate(plans):
        try:
            args = {"project_id": project_id, "operation_id": write.operation_id, "position_math": math}
            if id is None:
                row, change = records.create(connection, "object", payload, **args)
            else:
                row, change = records.update(connection, "object", id, payload, **args)
        except Exception as error:
            error.details = {"target": target("object", project_id, id), **getattr(error, "details", {}),
                             "request_index": index, "match_value": value}
            raise
        action = "create" if id is None else "update" if change is not None else "unchanged"
        counts[{"create": "created", "update": "updated", "unchanged": "unchanged"}[action]] += 1
        items.append({"match_value": value, "action": action, "record": row})
    return {"scope": {"project_id": project_id, "layer_id": layer_id, "match_by": match_by},
            "counts": counts, "items": items}


def upsert_objects(connection, project_id, layer_id, objects, *, match_by="name",
                   config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """同层精确匹配后更新或创建；一批一个事务，提交后运行可选检测。"""
    return run_operation(connection, lambda write: upsert_objects_in_session(
        write, project_id, layer_id, objects, match_by=match_by),
        checker=optional_checker(checker, config_root=config_root))


def main():
    import json
    from pathlib import Path
    from layerweave.support.cli import parser_for, run_cli

    parser = parser_for("LayerWeave 按匹配键更新或新增对象", commands=COMMANDS)
    parser.add_argument("layer_id", type=int, help="只匹配此层直属对象")
    parser.add_argument("--data-file", type=Path, required=True, help="对象字段字典组成的 JSON 列表")
    parser.add_argument("--match-by", default="name", help="精确匹配 name 或 information.source_key 等路径")
    parser.add_argument("--config-root", type=Path, default=DEFAULT_ROOT)
    return run_cli(parser, lambda connection, args: upsert_objects(
        connection, args.project_id, args.layer_id, json.loads(args.data_file.read_text(encoding="utf-8-sig")),
        match_by=args.match_by, config_root=args.config_root), operation_output=True)


COMMANDS = [{'name': 'upsert_objects',
  'summary': '按同层名字或稳定键更新原对象，缺失时创建；保留身份与引用',
  'entrypoint': 'layerweave.tool.builtin.usage.editing.upsert:upsert_objects',
  'session_entrypoint': 'layerweave.tool.builtin.usage.editing.upsert:upsert_objects_in_session',
  'cli': 'python -m layerweave.tool.builtin.usage.editing.upsert',
  'read_only': False,
  'context': ['database', 'project_id'],
  'returns': '标准操作结果；data 含 scope、created/updated/unchanged 计数和逐项匹配值、动作、record。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.usage.editing.upsert DATABASE 1 4 --data-file '
                       'scenes.json --match-by information.source_key',
                'files': {'scenes.json': [{'name': '开场',
                                           'config_ref': 'objects/text.toml',
                                           'information': {'source_key': 'scene_017', 'text': '故事正文'}}]},
                'arguments': {'layer_id': 4,
                              'objects': [{'name': '开场',
                                           'config_ref': 'objects/text.toml',
                                           'information': {'text': '正文'}}]}}],
  'notes': ['只匹配指定层，不模糊匹配；空键、批内重复键及匹配歧义会令整批失败。', '不删除未提供的旧对象，不改关联或批注；更新只覆盖传入字段，information 整体替换。'],
  'aliases': ['upsert'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'project_id': {'type': 'integer', 'description': '明确的项目编号'},
                                  'layer_id': {'type': 'integer', 'description': '匹配范围为该层直属对象'},
                                  'objects': {'type': 'array',
                                              'description': '对象字段字典列表；创建项需要 config_ref',
                                              'items': {}},
                                  'match_by': {'type': 'string',
                                               'default': 'name',
                                               'description': '精确匹配路径，例如 information.source_key；名字改动时宜使用稳定键'},
                                  'config_root': {'type': 'string', 'description': '提交后检查使用的配置根目录'}},
                   'additionalProperties': False,
                   'required': ['database', 'layer_id', 'objects', 'project_id']},
  'mcp': {'route': 'edit', 'group': 'editing', 'database': 'connection', 'paths': ['config_root']},
  'cli_mapping': {'objects': ['data_file']},
  'cli_only': ['text']}]


if __name__ == "__main__":
    raise SystemExit(main())

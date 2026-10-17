"""查询实体引用谁、被谁引用；保持完整引用，不自动递归或装载目标。"""

from layerweave.support.api import read_bindings


def query_relations(connection, project_id, kind, id, *, direction="both"):
    """返回 entity/direction/outgoing/incoming；自关联在两个方向各出现一次。"""
    rows = read_bindings(connection, kind, project_id, id, direction=direction)
    entity = {"kind": kind, "project_id": project_id, "id": id}
    result = {"entity": entity, "direction": direction, "outgoing": [], "incoming": []}
    for row in rows:
        for side, group in (("source", "outgoing"), ("target", "incoming")):
            if direction in {"both", group} and all(row[f"{side}_{field}"] == value for field, value in entity.items()):
                result[group].append(row)
    return result


def main():
    from layerweave.support.cli import parser_for, run_cli

    parser = parser_for("LayerWeave 关联查询（只读，输出 JSON）", commands=COMMANDS)
    parser.add_argument("kind", choices=("layer", "object"), help="实体种类")
    parser.add_argument("id", type=int, help="实体在项目内的编号")
    parser.add_argument("--direction", choices=("both", "outgoing", "incoming"), default="both")
    return run_cli(parser, lambda connection, args: query_relations(
        connection, args.project_id, args.kind, args.id, direction=args.direction,
    ))



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'query_relations',
  'summary': '查看实体的入向、出向或双向关联',
  'entrypoint': 'layerweave.tool.builtin.usage.query.relations:query_relations',
  'cli': 'python -m layerweave.tool.builtin.usage.query.relations',
  'read_only': True,
  'context': ['database', 'project_id'],
  'returns': 'entity、direction、incoming、outgoing；失效引用仍可读取。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.usage.query.relations DATABASE 1 object 8 --direction '
                       'both',
                'arguments': {'kind': 'object', 'id': 8}}],
  'aliases': ['relations'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'project_id': {'type': 'integer', 'description': '明确的项目编号'},
                                  'kind': {'type': 'string', 'description': '实体种类', 'enum': ['layer', 'object']},
                                  'id': {'type': 'integer', 'description': '项目内实体编号'},
                                  'direction': {'type': 'string',
                                                'description': '关联方向',
                                                'default': 'both',
                                                'enum': ['both', 'incoming', 'outgoing']}},
                   'additionalProperties': False,
                   'required': ['database', 'id', 'kind', 'project_id']},
  'mcp': {'route': 'query', 'group': 'query', 'database': 'connection', 'paths': []}}]


if __name__ == "__main__":
    raise SystemExit(main())

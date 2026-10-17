"""接续新增与对象复制：只创建对象记录，不自动复制关联或资源文件。"""

from layerweave.support.api import DEFAULT_CHECKER
from ._plan import dispatch, execute_in_session
from ._records import _duration, _number, _objects, _tail
from layerweave.support.api import PositionMath, decimal_value


def append_object(connection, project_id, layer_id, data, *, duration, after_id=None, empty_start=0, checker=DEFAULT_CHECKER):
    """从层内最大 end（或指定同层对象的 end）新增；空层使用 empty_start。"""
    plan = _append_object_plan(
        project_id, layer_id, data, duration=duration, after_id=after_id, empty_start=empty_start,
    )
    return dispatch(connection, plan, checker=checker)


def append_object_in_session(write, project_id, layer_id, data, *, duration, after_id=None, empty_start=0):
    """复用已有写会话，返回记录或记录列表；失败抛出异常。"""
    plan = _append_object_plan(
        project_id, layer_id, data, duration=duration, after_id=after_id, empty_start=empty_start,
    )
    return execute_in_session(write, plan)


def _append_object_plan(project_id, layer_id, data, *, duration, after_id=None, empty_start=0):
    def plan(read):
        length = decimal_value(_number(duration, "时长"))
        begin = decimal_value(_tail(read, project_id, layer_id, after_id=after_id, empty_start=empty_start))
        math = PositionMath(read, project_id)
        return {"action": "create", "kind": "object", "project_id": project_id,
                "data": {**data, "layer": layer_id, "begin": math.snap(layer_id, begin), "end": math.snap(layer_id, begin + length)}}
    return plan


def copy_object(connection, project_id, object_id, *, layer_id=None, begin=None, append=False, name=None, checker=DEFAULT_CHECKER):
    """同项目复制内容与配置并发放新编号；可另选层、起点，或明确接续到目标层末尾。"""
    plan = _copy_object_plan(
        project_id, object_id, layer_id=layer_id, begin=begin, append=append, name=name,
    )
    return dispatch(connection, plan, checker=checker)


def copy_object_in_session(write, project_id, object_id, *, layer_id=None, begin=None, append=False, name=None):
    """复用已有写会话，返回记录或记录列表；失败抛出异常。"""
    plan = _copy_object_plan(
        project_id, object_id, layer_id=layer_id, begin=begin, append=append, name=name,
    )
    return execute_in_session(write, plan)


def _copy_object_plan(project_id, object_id, *, layer_id=None, begin=None, append=False, name=None):
    def plan(read):
        if append and begin is not None:
            raise ValueError("复制位置请选择 begin 或 append，不要同时指定")
        source = _objects(read, project_id, [object_id])[0]
        destination = source["layer"] if layer_id is None else layer_id
        data = {key: value for key, value in source.items() if key not in {"id", "project_id"}}
        data["layer"] = destination
        if name is not None:
            data["name"] = name
        start = _tail(read, project_id, destination) if append else begin
        if start is not None:
            start = decimal_value(_number(start, "复制起点"))
            math = PositionMath(read, project_id)
            data.update(begin=math.snap(destination, start), end=math.snap(destination, start + _duration(source)))
        return {"action": "create", "kind": "object", "project_id": project_id, "data": data}
    return plan


def main():
    import json
    from pathlib import Path
    from layerweave.support.cli import parser_for, run_cli

    parser = parser_for("LayerWeave 对象新增工具（写入并返回 JSON）", commands=COMMANDS)
    commands = parser.add_subparsers(dest="command", required=True)
    append = commands.add_parser("append", help="按指定时长接续新增")
    append.add_argument("layer_id", type=int)
    append.add_argument("duration", type=float)
    append.add_argument("--data-file", type=Path, required=True, help="对象创建字段的 JSON 文件")
    append.add_argument("--after-id", type=int)
    append.add_argument("--empty-start", type=float, default=0)
    copy = commands.add_parser("copy", help="复制对象自身，不复制关联")
    copy.add_argument("object_id", type=int)
    copy.add_argument("--layer-id", type=int)
    copy.add_argument("--name")
    placement = copy.add_mutually_exclusive_group()
    placement.add_argument("--begin", type=float)
    placement.add_argument("--append", action="store_true")

    def execute(connection, args):
        if args.command == "append":
            data = json.loads(args.data_file.read_text(encoding="utf-8-sig"))
            return append_object(connection, args.project_id, args.layer_id, data, duration=args.duration,
                                 after_id=args.after_id, empty_start=args.empty_start)
        return copy_object(connection, args.project_id, args.object_id, layer_id=args.layer_id,
                           name=args.name, begin=args.begin, append=args.append)
    return run_cli(parser, execute, operation_output=True)


# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'append_object',
  'summary': '按层尾或指定对象终点接续新增对象',
  'entrypoint': 'layerweave.tool.builtin.usage.editing.objects:append_object',
  'session_entrypoint': 'layerweave.tool.builtin.usage.editing.objects:append_object_in_session',
  'cli': 'python -m layerweave.tool.builtin.usage.editing.objects',
  'read_only': False,
  'context': ['database', 'project_id'],
  'returns': '标准操作结果、operation_id、data/results 和提交后 checks；可按操作编号撤销。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.usage.editing.objects DATABASE 1 append 4 2 --data-file '
                       'object.json',
                'files': {'object.json': {'config_ref': 'objects/text.toml', 'information': {'text': '新增'}}},
                'arguments': {'layer_id': 4,
                              'duration': 2,
                              'data': {'config_ref': 'objects/text.toml', 'information': {'text': '新文字'}}}}],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'project_id': {'type': 'integer', 'description': '明确的项目编号'},
                                  'layer_id': {'type': 'integer', 'description': '新增对象所属层'},
                                  'data': {'type': 'object', 'description': '对象创建字段，含 config_ref 和 information'},
                                  'duration': {'type': 'number', 'description': '新增对象时长'},
                                  'after_id': {'type': ['integer', 'null'], 'description': '同层锚点对象编号；省略用层内最大 end'},
                                  'empty_start': {'type': 'number', 'description': '空层起点', 'default': 0}},
                   'additionalProperties': False,
                   'required': ['data', 'database', 'duration', 'layer_id', 'project_id']},
  'mcp': {'route': 'edit', 'group': 'editing', 'database': 'connection', 'paths': []},
  'cli_mapping': {'data': ['data_file']},
  'cli_only': ['command', 'text']},
 {'name': 'copy_object',
  'summary': '同项目复制一个对象，可选新层、新起点或接续位置',
  'entrypoint': 'layerweave.tool.builtin.usage.editing.objects:copy_object',
  'session_entrypoint': 'layerweave.tool.builtin.usage.editing.objects:copy_object_in_session',
  'cli': 'python -m layerweave.tool.builtin.usage.editing.objects',
  'read_only': False,
  'context': ['database', 'project_id'],
  'returns': '标准操作结果、operation_id、data/results 和提交后 checks；可按操作编号撤销。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.usage.editing.objects DATABASE 1 copy 8 --layer-id 4 '
                       '--append',
                'arguments': {'object_id': 8, 'layer_id': 4, 'begin': 20}}],
  'notes': ['只复制对象记录，不复制关联或资源文件。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'project_id': {'type': 'integer', 'description': '明确的项目编号'},
                                  'object_id': {'type': 'integer', 'description': '原对象编号'},
                                  'layer_id': {'type': ['integer', 'null'], 'description': '该项目内的层编号，仅直属对象'},
                                  'begin': {'type': ['number', 'null'], 'description': '轴上的数值位置，不换算单位'},
                                  'append': {'type': 'boolean',
                                             'description': '接续到目标层末尾，与 begin 互斥',
                                             'default': False},
                                  'name': {'type': ['string', 'null'], 'description': '副本名字'}},
                   'additionalProperties': False,
                   'required': ['database', 'object_id', 'project_id']},
  'mcp': {'route': 'edit', 'group': 'editing', 'database': 'connection', 'paths': []},
  'cli_only': ['command', 'text']}]


if __name__ == "__main__":
    raise SystemExit(main())

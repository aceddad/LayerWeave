"""通用位置工具：只计算 begin/end，事务、实际写入与诊断复用核心。"""

from math import isfinite

from runtime.api import DEFAULT_CHECKER, dispatch
from ._precision import PositionMath, decimal_value


def _number(value, label):
    if type(value) not in {int, float} or not isfinite(value):
        raise ValueError(f"{label} 必须是可计算的有限数值")
    return value


def _position(record, field):
    return _number(record[field], f"对象 ({record['project_id']}, {record['id']}) 的 {field}")


def _duration(record):
    return decimal_value(_position(record, "end")) - decimal_value(_position(record, "begin"))


def _layer(read, project_id, layer_id):
    if layer_id is None:
        raise ValueError("需要明确的 layer_id")
    record = read("layer", project_id=project_id, id=layer_id)
    if record is None:
        raise KeyError(f"层 ({project_id}, {layer_id}) 不存在")
    return record


def _objects(read, project_id, object_ids=None, layer_id=None):
    """显式选择编号，或指定整层；顺序保留，重复编号只处理一次。"""
    if layer_id is not None:
        layer_id = _layer(read, project_id, layer_id)["id"]
    if object_ids is None:
        if layer_id is None:
            raise ValueError("请指定 object_ids 或 layer_id")
        return read("object", project_id=project_id, filters={"layer": layer_id})
    if isinstance(object_ids, (str, bytes)):
        raise TypeError("object_ids 需要编号序列，不能传入单个字符串")
    records = {}
    for id in dict.fromkeys(object_ids):
        if id is None:
            raise ValueError("对象选择需要明确的编号")
        record = read("object", project_id=project_id, id=id)
        if record is None:
            raise KeyError(f"对象 ({project_id}, {id}) 不存在")
        if layer_id is not None and record["layer"] != layer_id:
            raise ValueError(f"对象 {id} 不属于指定层 {layer_id}")
        records.setdefault(record["id"], record)
    return list(records.values())


def _tail(read, project_id, layer_id, *, after_id=None, empty_start=0):
    if after_id is not None:
        record = _objects(read, project_id, [after_id], layer_id)[0]
        return _position(record, "end")
    _layer(read, project_id, layer_id)
    records = read("object", project_id=project_id, filters={"layer": layer_id})
    if not records:
        return _number(empty_start, "空层起点")
    return max(_position(record, "end") for record in records)


def _update(project_id, record, begin, end):
    return {"action": "update", "kind": "object", "project_id": project_id, "id": record["id"],
            "data": {"begin": begin, "end": end}}


def arrange_objects(connection, project_id, layer_id, *, object_ids=None, start=None, checker=DEFAULT_CHECKER):
    """按原时长累计再按轴精度落点；显式编号按给定顺序，默认按现有位置顺序。"""
    def plan(read):
        if layer_id is None:
            raise ValueError("连续排列需要指定 layer_id")
        records = _objects(read, project_id, object_ids, layer_id)
        if not records:
            return []
        math = PositionMath(read, project_id)
        cursor = decimal_value(_number(records[0]["begin"] if start is None else start, "排列起点"))
        requests = []
        for record in records:
            end = cursor + _duration(record)
            requests.append(_update(project_id, record, math.snap(record["layer"], cursor), math.snap(record["layer"], end)))
            cursor = end
        return requests
    return dispatch(connection, plan, checker=checker)


def shift_objects(connection, project_id, object_ids=None, *, offset, layer_id=None, layer_ids=None,
                  from_position=None, config_root=None, checker=DEFAULT_CHECKER):
    """对象/直属层/子树范围，按 begin 下限筛选；保留原批次返回协议。"""
    from runtime.api import shift_objects as shift
    return shift(connection, project_id, object_ids, offset=offset, layer_id=layer_id, layer_ids=layer_ids,
                 from_position=from_position, checker=checker,
                 **({"config_root": config_root} if config_root is not None else {}))


def align_objects(connection, project_id, object_ids=None, *, position, edge="begin", layer_id=None, checker=DEFAULT_CHECKER):
    """以原时长计算对齐后的端点，再按各自轴精度落点；可选择同项目多个层的对象。"""
    def plan(read):
        target = decimal_value(_number(position, "对齐位置"))
        if edge not in {"begin", "end"}:
            raise ValueError("edge 应为 begin 或 end")
        requests = []
        math = PositionMath(read, project_id)
        for record in _objects(read, project_id, object_ids, layer_id):
            duration = _duration(record)
            begin, end = (target, target + duration) if edge == "begin" else (target - duration, target)
            requests.append(_update(project_id, record, math.snap(record["layer"], begin), math.snap(record["layer"], end)))
        return requests
    return dispatch(connection, plan, checker=checker)


def set_duration(connection, project_id, object_id, duration, *, checker=DEFAULT_CHECKER):
    """保持起点，计算并量化新终点；不会移动其他对象。"""
    def plan(read):
        value = decimal_value(_number(duration, "时长"))
        record = _objects(read, project_id, [object_id])[0]
        begin = _position(record, "begin")
        end = PositionMath(read, project_id).snap(record["layer"], decimal_value(begin) + value)
        return _update(project_id, record, begin, end)
    return dispatch(connection, plan, checker=checker)


def main():
    from tools._cli import parser_for, run_cli

    parser = parser_for("LayerWeave 位置工具（写入并返回 JSON）", commands=COMMANDS)
    commands = parser.add_subparsers(dest="command", required=True)
    arrange = commands.add_parser("arrange", help="同层连续排列")
    arrange.add_argument("layer_id", type=int)
    arrange.add_argument("--ids", nargs="+", type=int)
    arrange.add_argument("--start", type=float)
    shift = commands.add_parser("shift", help="整体平移")
    align = commands.add_parser("align", help="起终点对齐")
    for command in (shift, align):
        selection = command.add_mutually_exclusive_group(required=True)
        selection.add_argument("--ids", nargs="+", type=int)
        selection.add_argument("--layer-id", type=int)
        if command is shift:
            selection.add_argument("--layer-ids", nargs="*", type=int, help="子树范围，包含后代")
    shift.add_argument("--offset", type=float, required=True)
    shift.add_argument("--from-position", type=float, help="仅选择 begin 不早于此数值的对象")
    shift.add_argument("--config-root")
    align.add_argument("--position", type=float, required=True)
    align.add_argument("--edge", choices=("begin", "end"), default="begin")
    duration = commands.add_parser("duration", help="保持起点修改时长")
    duration.add_argument("object_id", type=int)
    duration.add_argument("duration", type=float)

    def execute(connection, args):
        if args.command == "arrange":
            return arrange_objects(connection, args.project_id, args.layer_id, object_ids=args.ids, start=args.start)
        if args.command == "shift":
            return shift_objects(connection, args.project_id, args.ids, offset=args.offset, layer_id=args.layer_id,
                                 layer_ids=args.layer_ids, from_position=args.from_position, config_root=args.config_root)
        if args.command == "align":
            return align_objects(connection, args.project_id, args.ids, position=args.position, edge=args.edge, layer_id=args.layer_id)
        return set_duration(connection, args.project_id, args.object_id, args.duration)
    return run_cli(parser, execute, operation_output=True)



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'arrange_objects',
  'summary': '按指定顺序连续排列对象，保留各自时长',
  'entrypoint': 'tools.common.positions:arrange_objects',
  'cli': 'python -m tools.common.positions',
  'read_only': False,
  'context': ['database', 'project_id'],
  'parameters': {'layer_id': {'type': 'integer', 'description': '同一层的编号', 'required': True},
                 'object_ids': {'type': 'array', 'description': '明确选择的对象编号列表，重复编号只处理一次'},
                 'start': {'type': 'number', 'description': '轴上的数值位置，不换算单位'}},
  'returns': '标准操作结果、operation_id、data/results 和提交后 checks；可按操作编号撤销。',
  'examples': [{'cli': 'python -m tools.common.positions DATABASE 1 arrange 4 --ids 8 12 --start 0'}]},
 {'name': 'shift_objects',
  'summary': '选择对象/直属层/子树，按起点下限筛选后整体平移',
  'entrypoint': 'runtime.api:shift_objects',
  'cli': 'python -m tools.common.positions',
  'read_only': False,
  'context': ['database', 'project_id'],
  'parameters': {'object_ids': {'type': 'array', 'description': '明确选择的对象编号列表，重复编号只处理一次'},
                 'layer_id': {'type': 'integer', 'description': '该项目内的层编号，仅直属对象'},
                 'layer_ids': {'type': 'array', 'description': '子树起始层编号列表，包含全部后代；空列表为空选择'},
                 'offset': {'type': 'number', 'description': '正值后移，负值前移', 'required': True},
                 'from_position': {'type': 'number', 'description': '筛选 begin >= 此数值，不是区间相交'},
                 'config_root': {'type': 'string', 'description': '检查或配置查询采用的配置根目录；省略使用项目 configs'}},
  'returns': '标准操作结果、operation_id、data/results 和提交后 checks；可按操作编号撤销。',
  'examples': [{'cli': 'python -m tools.common.positions DATABASE 1 shift --layer-ids 4 --from-position 30 --offset '
                       '2'}],
  'notes': ['重叠按层配置在提交后报告；批量平移不保证插入时段为空。']},
 {'name': 'align_objects',
  'summary': '按起点或终点对齐选中对象，保留各自时长',
  'entrypoint': 'tools.common.positions:align_objects',
  'cli': 'python -m tools.common.positions',
  'read_only': False,
  'context': ['database', 'project_id'],
  'parameters': {'object_ids': {'type': 'array', 'description': '明确选择的对象编号列表，重复编号只处理一次'},
                 'layer_id': {'type': 'integer', 'description': '该项目内的层编号，仅直属对象'},
                 'position': {'type': 'number', 'description': '对齐位置', 'required': True},
                 'edge': {'type': 'string', 'description': '对齐端点', 'default': 'begin', 'choices': ['begin', 'end']}},
  'returns': '标准操作结果、operation_id、data/results 和提交后 checks；可按操作编号撤销。',
  'examples': [{'cli': 'python -m tools.common.positions DATABASE 1 align --ids 8 12 --position 10 --edge begin'}]},
 {'name': 'set_duration',
  'summary': '保持起点，修改对象时长',
  'entrypoint': 'tools.common.positions:set_duration',
  'cli': 'python -m tools.common.positions',
  'read_only': False,
  'context': ['database', 'project_id'],
  'parameters': {'object_id': {'type': 'integer', 'description': '对象编号', 'required': True},
                 'duration': {'type': 'number', 'description': '新的时长', 'required': True}},
  'returns': '标准操作结果、operation_id、data/results 和提交后 checks；可按操作编号撤销。',
  'examples': [{'cli': 'python -m tools.common.positions DATABASE 1 duration 8 3'}]}]


if __name__ == "__main__":
    raise SystemExit(main())

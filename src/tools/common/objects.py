"""接续新增与对象复制：只创建对象记录，不自动复制关联或资源文件。"""

from runtime.api import DEFAULT_CHECKER, dispatch
from .positions import _duration, _number, _objects, _tail


def append_object(connection, project_id, layer_id, data, *, duration, after_id=None, empty_start=0, checker=DEFAULT_CHECKER):
    """从层内最大 end（或指定同层对象的 end）新增；空层使用 empty_start。"""
    def plan(read):
        length = _number(duration, "时长")
        begin = _tail(read, project_id, layer_id, after_id=after_id, empty_start=empty_start)
        return {"action": "create", "kind": "object", "project_id": project_id,
                "data": {**data, "layer": layer_id, "begin": begin, "end": begin + length}}
    return dispatch(connection, plan, checker=checker)


def copy_object(connection, project_id, object_id, *, layer_id=None, begin=None, append=False, name=None, checker=DEFAULT_CHECKER):
    """同项目复制内容与配置并发放新编号；可另选层、起点，或明确接续到目标层末尾。"""
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
            start = _number(start, "复制起点")
            data.update(begin=start, end=start + _duration(source))
        return {"action": "create", "kind": "object", "project_id": project_id, "data": data}
    return dispatch(connection, plan, checker=checker)


def main():
    import json
    from pathlib import Path
    from tools._cli import parser_for, run_cli

    parser = parser_for("LayerWeave 对象新增工具（写入并返回 JSON）")
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
    return run_cli(parser, execute)


if __name__ == "__main__":
    raise SystemExit(main())

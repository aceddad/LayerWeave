"""插空档的封装入口：范围选择、跨界分割和后移共用一个事务。"""

import json
from pathlib import Path
from runtime.api import insert_gap, format_feedback


def format_gap(result):
    lines = [f"插空档操作：{result['operation_id']}", format_feedback(result)]
    if result["ok"]:
        for gap in result["data"]["gaps"]:
            lines.append(f"层 {gap['layer_id']}：空档 [{gap['begin']}, {gap['end']})，实际长度 {gap['length']}")
        for split in result["data"]["splits"]:
            lines.append(f"对象 {split['object_id']} 分为：" + ", ".join(str(row["id"]) for row in split["segments"]))
        lines.append(f"另外平移 {len(result['data']['shifted'])} 个对象。")
    else:
        for item in result.get("error", {}).get("required_splits", []):
            lines.append(f"需提供对象 {item['object_id']} 的两段内容：层 {item['layer_id']}，[{item['begin']}, {item['end']})，切点 {item['at']}")
        if result.get("error", {}).get("unused_object_ids"):
            lines.append("这些对象当前不跨界：" + str(result["error"]["unused_object_ids"]))
    return "\n".join(lines)


def main():
    from tools._cli import parser_for, run_cli
    parser = parser_for("LayerWeave 插空档：省略层范围表示整个项目")
    parser.add_argument("at", type=float)
    parser.add_argument("length", type=float)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--layer-id", type=int, help="仅此层直接装载的对象")
    scope.add_argument("--layer-ids", type=int, nargs="*", help="一个或多个子树")
    parser.add_argument("--contents-file", type=Path, help="跨界对象内容列表，含 object_id/first_information/second_information")
    parser.add_argument("--config-root")
    def execute(connection, args):
        contents = json.loads(args.contents_file.read_text(encoding="utf-8-sig")) if args.contents_file else None
        return insert_gap(connection, args.project_id, at=args.at, length=args.length, layer_id=args.layer_id,
                          layer_ids=args.layer_ids, split_contents=contents,
                          **({"config_root": args.config_root} if args.config_root is not None else {}))
    return run_cli(parser, execute, formatter=format_gap)


if __name__ == "__main__":
    raise SystemExit(main())

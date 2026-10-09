"""按操作组织可读历史；完整操作可跨项目，不能把筛选结果当成部分撤销。"""

import json

from runtime.api import read_history


def history(connection, project_id=None, **options):
    return read_history(connection, project_id, **options)


def format_history(result):
    dump = lambda value: json.dumps(value, ensure_ascii=False, allow_nan=False)
    lines = [f"匹配历史：{result['operation_count']} 次操作，{result['change_count']} 条改动；本页 {len(result['items'])} 次操作。"]
    for op in result["items"]:
        lines.extend(["", f"操作 {op['operation_id']} · {op['started_at']} · 项目 {op['project_ids']}"])
        if op["undo_of"]:
            lines.append(f"  撤销自：{op['undo_of']}")
        if op["matched_change_count"] != op["change_count"]:
            lines.append(f"  范围命中 {op['matched_change_count']} 条；展开完整操作共 {op['change_count']} 条。")
        for change in op["changes"]:
            target = change["target"]
            identity = f"({target['project_id']}, {target['id']})" if target["project_id"] is not None else str(target["id"])
            action = {"create": "创建", "update": "修改", "delete": "删除"}[change["action"]]
            lines.append(f"  {action} {target['kind']} {identity}" + (f" · {change['name']}" if change["name"] else ""))
            for field in change.get("fields", []):
                old = dump(field["before"]) if field["before_present"] else "（未提供）"
                new = dump(field["after"]) if field["after_present"] else "（未提供）"
                lines.append(f"    {'.'.join(field['path'])}：{old} → {new}")
            if "before" in change:
                lines.extend(["    修改前：" + dump(change["before"]), "    修改后：" + dump(change["after"])])
    if result["next_cursor"] is not None:
        lines.append(f"下一页：--before {result['next_cursor']}")
    return "\n".join(lines)


def main():
    from tools._cli import parser_for, run_cli
    parser = parser_for("LayerWeave 历史查询：按操作分页，已删除实体也可查询", project=False)
    parser.add_argument("--project-id", type=int)
    parser.add_argument("--kind", choices=("project", "layer", "object", "bind"))
    parser.add_argument("--id", type=int, help="实体编号；层和对象还需 --project-id")
    parser.add_argument("--operation-id", help="展开完整操作，包含前后快照，不与实体范围混用")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--before", type=int, help="上一页的 next_cursor")
    parser.add_argument("--detail", action="store_true", help="列表中也展开完整前后快照")
    return run_cli(parser, lambda connection, args: history(connection, args.project_id, kind=args.kind, id=args.id,
                   operation_id=args.operation_id, limit=args.limit, before=args.before, detail=args.detail), formatter=format_history)


if __name__ == "__main__":
    raise SystemExit(main())

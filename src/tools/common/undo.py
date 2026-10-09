"""按操作编号撤销；传入上次撤销返回的操作编号即可重做。"""

import json

from runtime.api import undo_operation, format_feedback, format_issue


def undo(connection, operation_id, *, config_root=None):
    return undo_operation(connection, operation_id, **({"config_root": config_root} if config_root is not None else {}))


def format_undo(result):
    lines = [f"撤销目标：{result['undo_of']}", f"本次操作编号：{result['operation_id']}", format_feedback(result)]
    for conflict in result.get("error", {}).get("conflicts", []):
        lines.extend(["", format_issue(conflict)])
        for name, label in (("expected", "原操作结束时"), ("current", "当前记录"), ("restore", "拟恢复记录")):
            if name in conflict:
                lines.append(f"  {label}：" + json.dumps(conflict[name], ensure_ascii=False, allow_nan=False))
    return "\n".join(lines)


def main():
    from tools._cli import parser_for, run_cli
    parser = parser_for("LayerWeave 撤销完整操作；撤销上次撤销即可重做", project=False)
    parser.add_argument("operation_id", help="历史查询或写入返回的操作编号；跨项目批次也整体撤销")
    parser.add_argument("--config-root", help="恢复后检查采用的当前配置根目录")
    return run_cli(parser, lambda connection, args: undo(connection, args.operation_id, config_root=args.config_root), formatter=format_undo)


if __name__ == "__main__":
    raise SystemExit(main())

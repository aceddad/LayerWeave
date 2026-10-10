"""按操作编号撤销；传入上次撤销返回的操作编号即可重做。"""

import json

from layerweave.tool.builtin.usage.undo.service import undo_operation
from layerweave.support.api import format_feedback, format_issue


def undo(connection, operation_id, *, config_root=None):
    return undo_operation(connection, operation_id, **({"config_root": config_root} if config_root is not None else {}))


def format_undo(result):
    lines = [f"撤销目标：{result['undo_of']}", f"本次操作编号：{result['operation_id']}", format_feedback(result)]
    for conflict in result.get("error", {}).get("conflicts", []):
        lines.extend(["", format_issue(conflict)])
        if conflict.get("fields"):
            lines.append("  冲突顶层字段：" + ", ".join(".".join(item["path"]) for item in conflict["fields"]))
        for name, label in (("expected", "原操作结束时"), ("current", "当前记录"), ("restore", "拟恢复记录")):
            if name in conflict:
                lines.append(f"  {label}：" + json.dumps(conflict[name], ensure_ascii=False, allow_nan=False))
    return "\n".join(lines)


def main():
    from layerweave.support.cli import parser_for, run_cli
    parser = parser_for("LayerWeave 撤销完整操作；撤销上次撤销即可重做", project=False, commands=COMMANDS)
    parser.add_argument("operation_id", help="历史查询或写入返回的操作编号；跨项目批次也整体撤销")
    parser.add_argument("--config-root", help="恢复后检查采用的当前配置根目录")
    return run_cli(parser, lambda connection, args: undo(connection, args.operation_id, config_root=args.config_root), formatter=format_undo)



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'undo_operation',
  'summary': '整批撤销或重做；更新按顶层字段冲突判断，创建/删除按整条记录',
  'entrypoint': 'layerweave.tool.builtin.usage.undo.service:undo_operation',
  'cli': 'python -m layerweave.tool.builtin.usage.undo.cli',
  'read_only': False,
  'context': ['database'],
  'parameters': {'operation_id': {'type': 'string', 'description': '写入返回或历史查询取得的完整操作编号', 'required': True},
                 'config_root': {'type': 'string', 'description': '检查或配置查询采用的配置根目录；省略使用项目 configs'}},
  'returns': '标准操作结果及 undo_of；data 含恢复数量；error.conflicts 给出顶层字段或整条记录冲突。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.usage.undo.cli DATABASE OPERATION_ID --json'}],
  'aliases': ['undo'],
  'notes': ['information 与 axis 都按整体字段处理，不合并内部键。', '重做使用上次撤销返回的新 operation_id；冲突时整批不写。']}]


if __name__ == "__main__":
    raise SystemExit(main())

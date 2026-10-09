"""全部命令总览或按名称展开参数、返回及示例；不连接数据库。"""

import argparse
import json

from runtime.api import command_help
from tools.shared.catalog import help_examples


def format_commands(result):
    lines = ["LayerWeave 命令帮助（只读查询，不执行命令）"]
    for item in result["items"]:
        lines.extend(["", f"{item['name']} · {'只读' if item['read_only'] else '可写入'}：{item['summary']}", "  " + item["cli"]])
        if "parameters" in item:
            lines.append("  Python 入口：" + item["entrypoint"])
            for name, spec in item["parameters"].items():
                required = "必需" if spec.get("required") else "可选"
                suffix = " · 可选值=" + json.dumps(spec["choices"], ensure_ascii=False) if "choices" in spec else ""
                if "default" in spec:
                    suffix += " · 默认=" + json.dumps(spec["default"], ensure_ascii=False)
                lines.append(f"  {name} ({spec.get('type', '任意')}, {required})：{spec.get('description', '')}{suffix}")
            lines.extend(["  返回：" + item.get("returns", "见公共 API"), help_examples([item])])
    for issue in result["issues"]:
        lines.append("\n[说明不可用] " + json.dumps(issue, ensure_ascii=False))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="LayerWeave 命令总览；指定多个名称可展开详情", epilog=help_examples(COMMANDS), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="*", help="命令名或别名，如 split、insert_gap、undo")
    parser.add_argument("--json", action="store_true", help="返回未来 MCP 等调用方可复用的结构化说明")
    parser.add_argument("--source-root", help="扩展命令的 Python 源目录，默认项目 src")
    args = parser.parse_args()
    try:
        result = command_help(args.names or None, **({"source_root": args.source_root} if args.source_root else {}))
    except (OSError, ValueError, TypeError) as error:
        result = {"view": "details", "status": "failed", "items": [], "issues": [{"code": "command_query", "message": str(error)}]}
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_commands(result))
    return 1 if result["status"] == "failed" else 0



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'command_help',
  'summary': '命令总览或多目标详情，静态读取各工具自身说明',
  'entrypoint': 'runtime.api:command_help',
  'cli': 'python -m tools.shared.command_help',
  'read_only': True,
  'context': [],
  'parameters': {'names': {'type': 'array', 'description': '命令名或别名列表，省略为总览'},
                 'source_root': {'type': 'string', 'description': '扩展命令源目录，默认 src'}},
  'returns': 'view、status、items 与逐条 issues；不执行工具或连接数据库。',
  'examples': [{'cli': 'python -m tools.shared.command_help --json'},
               {'cli': 'python -m tools.shared.command_help split insert_gap undo --json'}],
  'aliases': ['commands']}]


if __name__ == "__main__":
    raise SystemExit(main())

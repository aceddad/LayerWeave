"""JSON 分流入口：从文件或标准输入读取请求，输出 JSON 结果。"""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.support.api import open_database
from layerweave.support.feedback import error_detail, format_feedback, operation_result


def main():
    from layerweave.support.commands import help_examples
    parser = argparse.ArgumentParser(description="AI 制作工具的 CRUD 分流入口", epilog=help_examples(COMMANDS), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("database", type=Path, help="已初始化的 SQLite 文件")
    parser.add_argument("--request", type=Path, help="UTF-8 JSON 请求文件；省略时从标准输入读取")
    parser.add_argument("--text", action="store_true", help="逐条显示操作结果和诊断；默认输出 JSON")
    args = parser.parse_args()
    try:
        content = args.request.read_text(encoding="utf-8-sig") if args.request else sys.stdin.read()
        request = json.loads(content)
        if not args.database.is_file():
            raise FileNotFoundError("数据库不存在，请先使用 layerweave.tool.builtin.developer.database.cli 初始化")
        with closing(open_database(args.database)) as connection:
            result = dispatch(connection, request)
    except (OSError, ValueError, sqlite3.Error) as error:
        result = {
            "ok": False, "applied": False, "operation": operation_result("failed"),
            "error": error_detail(error),
            "checks": {"status": "not_run", "reason": "entry_failed", "issues": []},
        }
    print(format_feedback(result) if args.text else json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0 if result["ok"] else 1



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'dispatch',
  'summary': '基础记录 CRUD 与批次请求的分流入口',
  'entrypoint': 'layerweave.tool.builtin.usage.records.dispatch:dispatch',
  'session_entrypoint': 'layerweave.tool.builtin.usage.records.dispatch:dispatch_in_session',
  'cli': 'python -m layerweave.tool.builtin.usage.records.cli',
  'read_only': False,
  'context': ['database'],
  'returns': '数据库操作是否写入看 operation.status：committed/unchanged/failed/read；checks 只说明检查进度与问题。具体改动见 '
             'operation.changes，记录见 data/results；change 仅支持 read。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.usage.records.cli DATABASE --request request.json',
                'files': {'request.json': {'action': 'read', 'kind': 'project'}},
                'arguments': {'request': {'action': 'create', 'kind': 'project', 'data': {'name': '示例项目'}}}}],
  'notes': ['写请求与业务日志同事务；配置和语义在提交后检查。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'request': {'type': ['object', 'array'],
                                              'description': '单条 CRUD 对象或同一事务内的请求数组；read 可走 query，写入走 edit',
                                              'items': {'type': 'object'}}},
                   'additionalProperties': False,
                   'required': ['database', 'request']},
  'mcp': {'route': 'edit',
          'group': 'records',
          'database': 'connection',
          'paths': [],
          'default_project': False,
          'route_by': 'request'},
  'cli_only': ['text']}]


if __name__ == "__main__":
    raise SystemExit(main())

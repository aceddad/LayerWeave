"""内部工具共用的小型命令行入口，不负责注册或发现工具。"""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

from layerweave.support.api import open_database, format_feedback, format_issue
from layerweave.support.serialization import binary_json_default


def parser_for(description, *, project=True, commands=None):
    from layerweave.support.commands import help_examples
    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=help_examples(commands) if commands else None)
    parser.add_argument("database", type=Path, help="已有的 SQLite 数据库")
    if project:
        parser.add_argument("project_id", type=int, help="项目编号")
    return parser


def run_cli(parser, query, *, formatter=None, operation_output=False):
    """query(connection, args) 返回数据；有 formatter 时默认文本，可用 --json 切换。"""
    if formatter is not None:
        parser.add_argument("--json", action="store_true", help="输出结构化 JSON")
    if operation_output:
        parser.add_argument("--text", action="store_true", help="逐条显示操作结果和诊断；放在子命令之前")
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("数据库不存在，请先初始化数据库")
    try:
        with closing(open_database(args.database)) as connection:
            result = query(connection, args)
        if operation_output and args.text:
            output = format_feedback(result)
        elif formatter is not None and not args.json:
            output = formatter(result)
        else:
            output = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False, default=binary_json_default)
    except (OSError, sqlite3.Error, ValueError, TypeError) as error:
        parser.exit(1, f"执行失败：{error}\n")
    print(output)
    if formatter is not None and not args.json and isinstance(result, dict):
        for issue in result.get("issues", []):
            print(format_issue(issue), file=sys.stderr)
    return 0 if result is not None and (not isinstance(result, dict) or result.get("ok", True)) else 1

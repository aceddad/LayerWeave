"""只读工具共用的小型命令行入口，不负责注册或发现工具。"""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

from runtime.api import open_database


def parser_for(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("database", type=Path, help="已有的 SQLite 数据库")
    parser.add_argument("project_id", type=int, help="项目编号")
    return parser


def run_cli(parser, query, *, formatter=None):
    """query(connection, args) 返回数据；有 formatter 时默认文本，可用 --json 切换。"""
    if formatter is not None:
        parser.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("数据库不存在，请先初始化数据库")
    try:
        with closing(open_database(args.database)) as connection:
            result = query(connection, args)
        output = formatter(result) if formatter is not None and not args.json else json.dumps(
            result, ensure_ascii=False, indent=2, allow_nan=False,
        )
    except (OSError, sqlite3.Error, ValueError, TypeError) as error:
        parser.exit(1, f"查询失败：{error}\n")
    print(output)
    if formatter is not None and not args.json and isinstance(result, dict):
        for issue in result.get("issues", []):
            print(f"{issue['severity']}: {issue.get('target', {})} {issue.get('field', '')}: {issue['message']}", file=sys.stderr)
    return 0 if result is not None else 1

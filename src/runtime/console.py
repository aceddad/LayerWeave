"""JSON 分流入口：从文件或标准输入读取请求，输出 JSON 结果。"""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

from .dispatch import dispatch
from .storage.database import open_database


def main():
    parser = argparse.ArgumentParser(description="AI 制作工具的 CRUD 分流入口")
    parser.add_argument("database", type=Path, help="已初始化的 SQLite 文件")
    parser.add_argument("--request", type=Path, help="UTF-8 JSON 请求文件；省略时从标准输入读取")
    args = parser.parse_args()
    try:
        content = args.request.read_text(encoding="utf-8-sig") if args.request else sys.stdin.read()
        request = json.loads(content)
        if not args.database.is_file():
            raise FileNotFoundError("数据库不存在，请先使用 runtime.storage.database 初始化")
        with closing(open_database(args.database)) as connection:
            result = dispatch(connection, request)
    except (OSError, ValueError, sqlite3.Error) as error:
        result = {
            "ok": False, "applied": False,
            "error": {"type": type(error).__name__, "message": str(error)},
            "checks": {"status": "not_run", "reason": "entry_failed", "issues": []},
        }
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

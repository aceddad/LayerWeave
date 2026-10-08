"""JSON 分流入口：从文件或标准输入读取请求，输出 JSON 结果。"""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

from .dispatch import dispatch
from .storage.database import open_database
from .feedback import error_detail, format_feedback, operation_result


def main():
    parser = argparse.ArgumentParser(description="AI 制作工具的 CRUD 分流入口")
    parser.add_argument("database", type=Path, help="已初始化的 SQLite 文件")
    parser.add_argument("--request", type=Path, help="UTF-8 JSON 请求文件；省略时从标准输入读取")
    parser.add_argument("--text", action="store_true", help="逐条显示操作结果和诊断；默认输出 JSON")
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
            "ok": False, "applied": False, "operation": operation_result("failed"),
            "error": error_detail(error),
            "checks": {"status": "not_run", "reason": "entry_failed", "issues": []},
        }
    print(format_feedback(result) if args.text else json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

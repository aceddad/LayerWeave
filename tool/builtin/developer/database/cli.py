"""开发工具：初始化或显式升级数据库；存储实现仍在 support。"""

import argparse
from pathlib import Path

from support.api import initialize_database


def main():
    from support.commands import help_examples
    parser = argparse.ArgumentParser(description="初始化 AI 制作工具的 SQLite 业务表和日志表", epilog=help_examples(COMMANDS), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("database", type=Path, help="数据库文件路径")
    args = parser.parse_args()
    print(initialize_database(args.database))
    return 0


# 命令目录和 --help 共用的只读接口说明。

COMMANDS = [{'name': 'initialize_database',
  'summary': '初始化或显式升级 SQLite 表结构，保留已有数据与日志',
  'entrypoint': 'support.api:initialize_database',
  'cli': 'python -m tool.builtin.developer.database.cli',
  'read_only': False,
  'context': ['database'],
  'parameters': {},
  'returns': 'Python 返回数据库路径，CLI 输出该路径。',
  'examples': [{'cli': 'python -m tool.builtin.developer.database.cli DATABASE'}],
  'notes': ['这是写入操作；普通只读工具不会暗中迁移数据库。']}]



if __name__ == "__main__":
    raise SystemExit(main())

"""JSON 分流入口：从文件或标准输入读取请求，输出 JSON 结果。"""

import argparse
from contextlib import closing
import json
from layerweave.support.serialization import binary_json_default
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
    print(format_feedback(result) if args.text else json.dumps(result, ensure_ascii=False, allow_nan=False, default=binary_json_default))
    return 0 if result["ok"] else 1



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'dispatch',
  'summary': '新建、读取、修改／更新、删除单条或多条记录',
  'entrypoint': 'layerweave.tool.builtin.usage.records.dispatch:dispatch',
  'session_entrypoint': 'layerweave.tool.builtin.usage.records.dispatch:dispatch_in_session',
  'cli': 'python -X utf8 -m layerweave.tool.builtin.usage.records.cli',
  'read_only': False,
  'context': ['database'],
  'returns': '数据库操作是否写入看 operation.status：committed/unchanged/failed/read；checks 只说明检查进度与问题。具体改动见 '
             'operation.changes，记录见 data/results；change 仅支持 read。',
  'examples': [{'title': '修改一个对象',
                'arguments': {'request': {'action': 'update',
                                          'kind': 'object',
                                          'project_id': 1,
                                          'id': 8,
                                          'data': {'tips': '调整节奏'}}}},
               {'title': '批量修改',
                'arguments': {'request': [{'action': 'update',
                                           'kind': 'object',
                                           'project_id': 1,
                                           'id': 8,
                                           'data': {'name': '开场'}},
                                          {'action': 'update',
                                           'kind': 'object',
                                           'project_id': 1,
                                           'id': 9,
                                           'data': {'tips': '待检查'}}]}},
               {'title': '读取对象',
                'arguments': {'request': {'action': 'read', 'kind': 'object', 'project_id': 1, 'id': 8}}},
               {'title': '创建项目',
                'cli': 'python -X utf8 -m layerweave.tool.builtin.usage.records.cli DATABASE --request request.json',
                'files': {'request.json': {'action': 'read', 'kind': 'project'}},
                'arguments': {'request': {'action': 'create', 'kind': 'project', 'data': {'name': '示例项目'}}}}],
  'notes': ['写请求与业务日志同事务；配置和语义在提交后检查。',
            '每条 layer/object 或有项目归属的工具记录请求须自己填写 project_id；启动默认项目不会补入 request。',
            'update 只修改传入字段；information 等 JSON 字段整体替换，不递归合并。',
            '声明的 BLOB 字段在 JSON 中使用标准 Base64，null 保持 null；filters 不支持 JSON/BLOB 列。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string',
                                               'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'request': {'description': '一条请求或同事务请求数组；read 用 query，写入用 edit。每条请求自行指定项目。',
                                              'type': ['object', 'array'],
                                              'allOf': [{'if': {'type': 'object'},
                                                         'then': {'$ref': '#/$defs/request'}}],
                                              'items': {'$ref': '#/$defs/request'}}},
                   'additionalProperties': False,
                   'required': ['database', 'request'],
                   '$defs': {'request': {'type': 'object',
                                         'properties': {'action': {'type': 'string',
                                                                   'enum': ['create',
                                                                            'read',
                                                                            'update',
                                                                            'delete']},
                                                        'kind': {'type': 'string',
                                                                 'description': 'project/layer/object/bind/change，或本库已登记的工具 '
                                                                                'kind；change 仅可读取'},
                                                        'project_id': {'type': 'integer',
                                                                       'description': 'layer、object '
                                                                                      '和有项目归属的工具表必填；不会补启动默认项目'},
                                                        'id': {'type': 'integer',
                                                               'description': 'update/delete 必填；read '
                                                                              '可省略以列出记录'},
                                                        'data': {'type': 'object',
                                                                 'description': 'create/update 字段；JSON '
                                                                                '字段整体替换；provided 表创建编号放 '
                                                                                'data.id'},
                                                        'filters': {'type': 'object',
                                                                    'description': 'read 的普通列等值条件，不支持 JSON/BLOB'},
                                                        'full': {'type': 'boolean',
                                                                 'description': 'read 单条 layer/object '
                                                                                '时装载完整内容'}},
                                         'required': ['action', 'kind'],
                                         'additionalProperties': False,
                                         'allOf': [{'if': {'properties': {'action': {'enum': ['create',
                                                                                              'update']}}},
                                                    'then': {'required': ['data']}},
                                                   {'if': {'properties': {'action': {'enum': ['update',
                                                                                              'delete']}}},
                                                    'then': {'required': ['id']}},
                                                   {'if': {'properties': {'kind': {'enum': ['layer',
                                                                                            'object']}}},
                                                    'then': {'required': ['project_id']}}]}}},
  'mcp': {'route': 'edit',
          'group': 'records',
          'database': 'connection',
          'paths': [],
          'default_project': False,
          'route_by': 'request'},
  'cli_only': ['text'],
  'help_order': 10,
  'keywords': ['增删改查', '新建', '创建', '读取', '修改', '更新', '删除', '备注', '批量']}]


if __name__ == "__main__":
    raise SystemExit(main())

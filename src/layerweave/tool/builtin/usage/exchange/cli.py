"""exchange 的文件入口；导出默认只打印文件概要，完整内容按需读取。"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from layerweave.support.api import open_database
from layerweave.support.commands import help_examples
from .exporting import export_project
from .importing import import_project
from .files import load_document, save_document, template_help


def format_import(result):
    if not result["ok"]:
        return ("[导入失败] 本批业务写入已回滚。\n" + json.dumps(result["error"], ensure_ascii=False, indent=2)
                + "\n跳过提示：" + json.dumps(result.get("import_issues", []), ensure_ascii=False)
                + "\n结构准备：" + json.dumps(result["schema"], ensure_ascii=False))
    data = result["data"]
    counts = data["counts"]
    lines = [f"[导入 {data['status']}] 项目 {data['project_id']}；项目操作：{data['project_action']}",
             f"创建 {counts['created']}，更新 {counts['updated']}，删除 {counts['deleted']}，未变化 {counts['unchanged']}，上下文 {counts['selected']}，跳过 {counts['skipped']}",
             "操作编号：" + result["operation_id"]]
    for issue in data["issues"]:
        lines.append(f"[WARN] {issue['pointer']}：{issue['message']}")
        if issue["code"] == "parent_mismatch":
            lines.append(f"  文件归属={issue['expected_parent']}，实际归属={issue['actual_parent']}")
    checks = result["checks"]
    if checks["status"] == "failed":
        lines.append("提交后检测未完成：" + json.dumps(checks["error"], ensure_ascii=False))
    for issue in checks.get("issues", []):
        lines.append("[提交后检查] " + json.dumps(issue, ensure_ascii=False))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="LayerWeave 分层 JSON 交换与模板", epilog=help_examples(COMMANDS),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="导出项目或局部到 JSON 文件", epilog=help_examples([COMMANDS[0]]),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    export.add_argument("database", type=Path)
    export.add_argument("project_id", type=int)
    export.add_argument("--output", type=Path, required=True, help="由调用方指定输出 JSON 路径")
    selection = export.add_mutually_exclusive_group()
    selection.add_argument("--layer-ids", nargs="*", type=int)
    selection.add_argument("--object-ids", nargs="*", type=int)
    export.add_argument("--begin", type=float)
    export.add_argument("--end", type=float)
    export.add_argument("--op", choices=("add","update","delete"), default="update")
    export.add_argument("--no-tools", action="store_true")
    export.add_argument("--include-global", action="store_true")
    export.add_argument("--include-baseline", action="store_true")
    export.add_argument("--compact", action="store_true", help="省略表定义和来源发号说明；目标库须已有工具表声明")
    apply = commands.add_parser("apply", help="执行文件或模板", epilog=help_examples([COMMANDS[1]]),
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    apply.add_argument("database", type=Path)
    source = apply.add_mutually_exclusive_group(required=True)
    source.add_argument("--data-file", type=Path)
    source.add_argument("--template")
    apply.add_argument("--template-root", type=Path)
    destination = apply.add_mutually_exclusive_group()
    destination.add_argument("--project-id", type=int)
    destination.add_argument("--new-project", action="store_true")
    apply.add_argument("--parent-layer-id", type=int)
    apply.add_argument("--external-refs", choices=("skip","preserve"), default="skip")
    apply.add_argument("--reference-map", type=Path, help="source/target 完整身份映射组成的 JSON 列表")
    apply.add_argument("--ignore-baseline", action="store_true", help="明确允许覆盖已变化内容，仍检查归属")
    apply.add_argument("--no-prepare", action="store_true", help="表结构已由调用方准备")
    apply.add_argument("--config-root", type=Path)
    apply.add_argument("--result-file", type=Path, help="保存完整反馈及编号映射，避免全部打印")
    apply.add_argument("--json", action="store_true", help="打印完整 JSON 反馈")
    templates = commands.add_parser("templates", help="先看模板用途，再按名称展开")
    templates.add_argument("name", nargs="?")
    templates.add_argument("--template-root", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "templates":
            print(json.dumps(template_help(args.name, template_root=args.template_root), ensure_ascii=False, indent=2))
            return 0
        if not args.database.is_file():
            parser.error("数据库不存在，请先使用 initialize_database 初始化")
        with closing(open_database(args.database)) as connection:
            if args.command == "export":
                document = export_project(connection, args.project_id, layer_ids=args.layer_ids, object_ids=args.object_ids,
                                          begin=args.begin, end=args.end, op=args.op, include_tools=not args.no_tools,
                                          include_global=args.include_global, include_baseline=args.include_baseline, compact=args.compact)
                path = save_document(document, args.output)
                print(json.dumps({"path":path,"counts":document["counts"],"scope":document["scope"],
                                  "external_references":len(document["external_references"]),
                                  "omitted_tool_records":document["omitted_tool_records"]}, ensure_ascii=False, indent=2))
                return 0
            if args.template is not None:
                catalog = template_help(args.template, template_root=args.template_root)
                if not catalog["items"]:
                    raise ValueError(json.dumps(catalog["issues"], ensure_ascii=False))
                document = catalog["items"][0]["document"]
            else:
                document = load_document(args.data_file)
            mapping = json.loads(args.reference_map.read_text(encoding="utf-8-sig")) if args.reference_map else None
            result = import_project(connection, document, project_id=args.project_id, new_project=args.new_project,
                                    parent_layer_id=args.parent_layer_id, external_refs=args.external_refs,
                                    reference_map=mapping, check_baseline=not args.ignore_baseline,
                                    prepare_tables=not args.no_prepare,
                                    **({"config_root":args.config_root} if args.config_root else {}))
        if args.result_file:
            save_document(result, args.result_file)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_import(result))
        return 0 if result["ok"] else 1
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
        parser.exit(1, f"交换失败：{error}\n")


COMMANDS = [{'name': 'export_project',
  'summary': '导出分层 JSON，可选择层、对象和时间范围；默认 op=update',
  'entrypoint': 'layerweave.tool.builtin.usage.exchange:export_project',
  'cli': 'python -m layerweave.tool.builtin.usage.exchange.cli',
  'read_only': True,
  'context': ['database', 'project_id'],
  'returns': '交换文档：project、items、records、tables、counts、scope；CLI 写文件并只输出概要。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.usage.exchange.cli export DATABASE 1 --output '
                       'project.json',
                'arguments': {'layer_ids': [4]}},
               {'cli': 'python -m layerweave.tool.builtin.usage.exchange.cli export DATABASE 1 --layer-ids 4 '
                       '--op add --output subtree.json'}],
  'notes': ['CLI 必须由 AI 指定 --output，不默认打印全部内容。source_numbering 只说明来源发号配置，不自动安装规则。',
            '工具数据通过 references/logical_references 收集；复制策略随表声明导出，在导入时执行。',
            '局部默认只带涉及的工具表及其定义依赖；compact 只省结构说明，include_tools 决定工具数据。'],
  'aliases': ['export'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string',
                                               'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'project_id': {'type': 'integer', 'description': '明确的项目编号'},
                                  'layer_ids': {'type': ['array', 'null'],
                                                'description': '层子树范围，与 object_ids 互斥',
                                                'items': {'type': 'integer'}},
                                  'object_ids': {'type': ['array', 'null'],
                                                 'description': '明确对象，与层/时间范围互斥',
                                                 'items': {'type': 'integer'}},
                                  'begin': {'type': ['number', 'null'], 'description': '相交范围起点'},
                                  'end': {'type': ['number', 'null'], 'description': '相交范围终点'},
                                  'op': {'type': 'string',
                                         'default': 'update',
                                         'enum': ['add', 'update', 'delete']},
                                  'include_tools': {'type': 'boolean',
                                                    'default': True,
                                                    'description': '本项目及声明引用连到选中内容的工具记录'},
                                  'include_global': {'type': 'boolean',
                                                     'default': False,
                                                     'description': '另含所有无项目归属工具记录'},
                                  'include_baseline': {'type': 'boolean',
                                                       'default': False,
                                                       'description': '附原状态摘要，供写回时核对'},
                                  'compact': {'type': 'boolean',
                                              'default': False,
                                              'description': '省略 '
                                                             'tables/source_numbering，保留业务数据与引用；用于目标库已有所需表声明的情况'}},
                   'additionalProperties': False,
                   'required': ['database', 'project_id']},
  'mcp': {'route': 'query',
          'group': 'exchange',
          'database': 'connection',
          'paths': [],
          'output': 'document',
          'variants': [{'command': 'export_project_file',
                        'route': 'admin',
                        'handler': 'layerweave.tool.builtin.usage.exchange.files:export_to_file',
                        'output': 'file',
                        'paths': ['output'],
                        'required': ['output'],
                        'properties': {'output': {'type': 'string',
                                                  'description': '明确的 JSON 输出文件路径',
                                                  'examples': ['exports/project.json']},
                                       'overwrite': {'type': 'boolean',
                                                     'default': False,
                                                     'description': '明确允许覆盖旧文件；默认排他创建'}},
                        'summary': '把所选范围的交换 JSON 保存到文件；仅明确 overwrite 时覆盖',
                        'returns': 'path 为绝对路径，counts/scope 为导出摘要，document_complete 表示文档完整。',
                        'notes': ['不需要文件时使用 export_project 直接取得 JSON。']}],
          'notes': ['直接返回所选范围的完整交换文档；无需输出文件。',
                    '复制使用 op=add，原编号用于引用映射，实际创建重新发号。',
                    '局部默认只带相关表定义；compact=true 省略 tables/source_numbering，目标库须已有工具表声明。',
                    'include_tools 控制是否导出工具数据；compact 不丢业务数据。']},
  'cli_mapping': {'include_tools': ['no_tools']},
  'cli_only': ['command', 'json', 'output', 'result_file']},
 {'name': 'import_project',
  'summary': '执行 JSON 操作或模板；归属不符跳过并警告，其他业务写入共用事务',
  'entrypoint': 'layerweave.tool.builtin.usage.exchange:import_project',
  'session_entrypoint': 'layerweave.tool.builtin.usage.exchange:import_project_in_session',
  'cli': 'python -m layerweave.tool.builtin.usage.exchange.cli',
  'read_only': False,
  'context': ['database'],
  'returns': '标准操作反馈，加 schema 准备信息；data 含逐项状态、跳过原因、计数、编号映射。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.usage.exchange.cli apply DATABASE --template '
                       'subtitles --new-project --result-file result.json',
                'arguments': {'project_id': 1,
                              'document': {'format_version': 1,
                                           'project_id': 1,
                                           'items': [{'kind': 'layer',
                                                      'id': 4,
                                                      'children': [{'kind': 'object',
                                                                    'op': 'update',
                                                                    'id': 8,
                                                                    'data': {'information': {'text': '修改后的正文'}}}]}]}}},
               {'cli': 'python -m layerweave.tool.builtin.usage.exchange.cli apply DATABASE --project-id 1 '
                       '--data-file patch.json --json',
                'files': {'patch.json': {'format_version': 1,
                                         'items': [{'kind': 'layer',
                                                    'id': 4,
                                                    'children': [{'kind': 'object',
                                                                  'op': 'add',
                                                                  'data': {'config_ref': 'objects/text.toml',
                                                                           'information': {'text': '新增字幕'}}}]}]}}}],
  'notes': ['没有 op 只选择上下文。add 自动表重发 ID；provided 表遵守自己的编号/引用声明。',
            'logical_references 参与换号，不建立外键。on_copy=skip 跳过带旧 id 的 add；全新 provided 身份写在 data.id 或 refs。',
            '父层不匹配不执行，该分支和依赖项一起跳过；partial 表示确有跳过，不是全部执行成功。',
            '重复运行含 add 的文件会再次创建。需要完整映射用 --json 或 --result-file。'],
  'aliases': ['import'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string',
                                               'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'document': {'type': 'object',
                                               'description': '直接传交换文档对象；无需先导出文件',
                                               'additionalProperties': True},
                                  'project_id': {'type': ['integer', 'null'], 'description': '明确导入到已有项目'},
                                  'new_project': {'type': 'boolean',
                                                  'default': False,
                                                  'description': '明确新建目标项目，不改节点 op'},
                                  'parent_layer_id': {'type': ['integer', 'null'],
                                                      'description': '顶层入口的附着层，新增时补归属'},
                                  'external_refs': {'type': 'string',
                                                    'default': 'skip',
                                                    'description': 'add 对文件外部引用的处理',
                                                    'enum': ['skip', 'preserve']},
                                  'reference_map': {'type': ['array', 'null'],
                                                    'description': 'source/target 完整身份的显式映射',
                                                    'items': {}},
                                  'check_baseline': {'type': 'boolean',
                                                     'default': True,
                                                     'description': '仅对文件提供了 base 的节点核对原状态'},
                                  'prepare_tables': {'type': 'boolean',
                                                     'default': True,
                                                     'description': '独立准备工具表声明，不属于内容撤销'},
                                  'config_root': {'type': 'string',
                                                  'description': '默认包内 configs，供层类型读取和提交后检查'}},
                   'additionalProperties': False,
                   'required': ['database', 'document']},
  'mcp': {'route': 'edit',
          'group': 'exchange',
          'database': 'connection',
          'paths': ['config_root'],
          'default_project': False,
          'variants': [{'command': 'import_project_file',
                        'handler': 'layerweave.tool.builtin.usage.exchange.files:import_from_file',
                        'omit': ['document'],
                        'paths': ['config_root', 'document_file'],
                        'required': ['document_file'],
                        'properties': {'document_file': {'type': 'string',
                                                         'description': '调用方选择的 JSON 输入文件路径',
                                                         'examples': ['exports/project.json']}},
                        'summary': '读取调用方选择的 JSON 文件并执行原有导入流程'}]},
  'cli_mapping': {'check_baseline': ['ignore_baseline'],
                  'document': ['data_file', 'template'],
                  'prepare_tables': ['no_prepare'],
                  'reference_map': ['reference_map']},
  'cli_only': ['command', 'json', 'output', 'result_file']},
 {'name': 'template_help',
  'summary': '列出模板用途和路径，按名称展开 JSON；新增模板文件自动发现',
  'entrypoint': 'layerweave.tool.builtin.usage.exchange:template_help',
  'cli': 'python -m layerweave.tool.builtin.usage.exchange.cli',
  'read_only': True,
  'context': [],
  'returns': 'status、items、issues；指定名称时 item 含完整 document。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.usage.exchange.cli templates'},
               {'cli': 'python -m layerweave.tool.builtin.usage.exchange.cli templates hand-drawn-video'}],
  'aliases': ['templates'],
  'input_schema': {'type': 'object',
                   'properties': {'name': {'type': ['string', 'null'], 'description': '模板名，省略只列概要'},
                                  'template_root': {'type': ['string', 'null'],
                                                    'description': '替换随包模板目录；普通文件也可直接导入'}},
                   'additionalProperties': False,
                   'required': []},
  'mcp': {'route': 'query', 'group': 'exchange', 'paths': ['template_root']},
  'cli_only': ['command', 'json', 'output', 'result_file']}]


if __name__ == "__main__":
    raise SystemExit(main())

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
                                          include_global=args.include_global, include_baseline=args.include_baseline)
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


COMMANDS = [
    {"name":"export_project", "summary":"导出分层 JSON，可选择层、对象和时间范围；默认 op=update",
     "entrypoint":"layerweave.tool.builtin.usage.exchange:export_project",
     "cli":"python -m layerweave.tool.builtin.usage.exchange.cli", "read_only":True, "context":["database","project_id"],
     "parameters":{
         "layer_ids":{"type":"array","description":"层子树范围，与 object_ids 互斥"},
         "object_ids":{"type":"array","description":"明确对象，与层/时间范围互斥"},
         "begin":{"type":"number","description":"相交范围起点"},
         "end":{"type":"number","description":"相交范围终点"},
         "op":{"type":"string","choices":["add","update","delete"],"default":"update"},
         "include_tools":{"type":"boolean","default":True,"description":"本项目及声明引用连到选中内容的工具记录"},
         "include_global":{"type":"boolean","default":False,"description":"另含所有无项目归属工具记录"},
         "include_baseline":{"type":"boolean","default":False,"description":"附原状态摘要，供写回时核对"}},
     "returns":"交换文档：project、items、records、tables、counts、scope；CLI 写文件并只输出概要。",
     "examples":[{"cli":"python -m layerweave.tool.builtin.usage.exchange.cli export DATABASE 1 --output project.json"},
                 {"cli":"python -m layerweave.tool.builtin.usage.exchange.cli export DATABASE 1 --layer-ids 4 --op add --output subtree.json"}],
     "notes":["CLI 必须由 AI 指定 --output，不默认打印全部内容。source_numbering 只说明来源发号配置，不自动安装规则。"],
     "aliases":["export"]},
    {"name":"import_project", "summary":"执行 JSON 操作或模板；归属不符跳过并警告，其他业务写入共用事务",
     "entrypoint":"layerweave.tool.builtin.usage.exchange:import_project",
     "session_entrypoint":"layerweave.tool.builtin.usage.exchange:import_project_in_session",
     "cli":"python -m layerweave.tool.builtin.usage.exchange.cli", "read_only":False, "context":["database"],
     "parameters":{
         "document":{"type":"object","required":True,"description":"format_version=1；CLI 用 --data-file 或 --template 提供"},
         "project_id":{"type":"integer","description":"明确导入到已有项目"},
         "new_project":{"type":"boolean","default":False,"description":"明确新建目标项目，不改节点 op"},
         "parent_layer_id":{"type":"integer","description":"顶层入口的附着层，新增时补归属"},
         "external_refs":{"type":"string","choices":["skip","preserve"],"default":"skip","description":"add 对文件外部引用的处理"},
         "reference_map":{"type":"array","description":"source/target 完整身份的显式映射"},
         "check_baseline":{"type":"boolean","default":True,"description":"仅对文件提供了 base 的节点核对原状态"},
         "prepare_tables":{"type":"boolean","default":True,"description":"独立准备工具表声明，不属于内容撤销"},
         "config_root":{"type":"string","description":"默认包内 configs，供层类型读取和提交后检查"}},
     "returns":"标准操作反馈，加 schema 准备信息；data 含逐项状态、跳过原因、计数、编号映射。",
     "examples":[{"cli":"python -m layerweave.tool.builtin.usage.exchange.cli apply DATABASE --template subtitles --new-project --result-file result.json"},
                 {"cli":"python -m layerweave.tool.builtin.usage.exchange.cli apply DATABASE --project-id 1 --data-file patch.json --json",
                  "files":{"patch.json":{"format_version":1,"items":[{"kind":"layer","id":4,"children":[
                      {"kind":"object","op":"add","data":{"config_ref":"objects/text.toml","information":{"text":"新增字幕"}}}]}]}}}],
     "notes":["没有 op 只选择上下文。add 自动表重发 ID；provided 表遵守自己的编号/引用声明。",
              "父层不匹配不执行，该分支和依赖项一起跳过；partial 表示确有跳过，不是全部执行成功。",
              "重复运行含 add 的文件会再次创建。需要完整映射用 --json 或 --result-file。"],
     "aliases":["import"]},
    {"name":"template_help", "summary":"列出模板用途和路径，按名称展开 JSON；新增模板文件自动发现",
     "entrypoint":"layerweave.tool.builtin.usage.exchange:template_help",
     "cli":"python -m layerweave.tool.builtin.usage.exchange.cli", "read_only":True, "context":[],
     "parameters":{"name":{"type":"string","description":"模板名，省略只列概要"},
                   "template_root":{"type":"string","description":"替换随包模板目录；普通文件也可直接导入"}},
     "returns":"status、items、issues；指定名称时 item 含完整 document。",
     "examples":[{"cli":"python -m layerweave.tool.builtin.usage.exchange.cli templates"},
                 {"cli":"python -m layerweave.tool.builtin.usage.exchange.cli templates hand-drawn-video"}],
     "aliases":["templates"]}
]


if __name__ == "__main__":
    raise SystemExit(main())

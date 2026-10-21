"""One launch interface, shared by uv, npm, and direct Python calls."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    from layerweave import __version__
    from layerweave.support.commands import help_examples
    parser = argparse.ArgumentParser(prog="layerweave", description="LayerWeave · 案例、项目与 MCP / examples, projects and MCP",
                                     epilog=help_examples(COMMANDS), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")
    demo = commands.add_parser("demo", help="准备或继续案例 / open an example")
    demo.add_argument("name", nargs="?", default="article-reading")
    demo.add_argument("--list", action="store_true", help="列出案例 / list examples")
    demo.add_argument("--dir", type=Path, help="保存项目的目录 / project directory")
    new = commands.add_parser("new", help="从模板创建项目 / create from a template")
    new.add_argument("directory", type=Path)
    new.add_argument("--template", default="subtitles")
    view = commands.add_parser("view", help="打开数据库或项目目录 / open a database or project directory")
    view.add_argument("database", type=Path)
    view.add_argument("--project", type=int)
    for command in (demo, new, view):
        command.add_argument("--port", type=int, default=0, help="端口，0 自动选择 / port, 0 selects a free port")
        command.add_argument("--no-browser", action="store_true", help="只打印地址 / do not open a browser")
    commands.add_parser("mcp", add_help=False, help="启动可选 MCP / run optional MCP")
    help_ = commands.add_parser("help", help="现有工具的详细帮助 / detailed tool help")
    help_.add_argument("names", nargs="*")
    values = list(sys.argv[1:] if argv is None else argv)
    # Keep MCP's argument parser and stdout protocol untouched.
    if values and values[0] == "mcp":
        try:
            from layerweave.tool.builtin.shared.mcp.__main__ import main as mcp_main
        except ModuleNotFoundError:
            parser.exit(1, "MCP 工具包未安装 / MCP tool package is not installed.\n")
        old = sys.argv
        try:
            sys.argv = ["layerweave-mcp", *values[1:]]
            return mcp_main()
        finally:
            sys.argv = old
    args = parser.parse_args(values)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "help":
            from layerweave.support.commands import command_help
            from layerweave.tool.builtin.shared.help.command_help import format_commands
            print(format_commands(command_help(args.names or None)))
            return 0
        if args.command == "demo" and args.list:
            from .catalog import catalog
            for item in catalog()["items"]:
                source = "随包 / bundled" if item["bundled"] else "按需下载 / download on demand"
                print(f"{item['name']} · {item['title']} [{source}]")
            return 0
        from layerweave.tool.builtin.view.server import serve
        from .projects import existing, prepare_demo, prepare_new, verify_database
        if args.command == "demo":
            print("准备案例 / Preparing example: " + args.name, file=sys.stderr, flush=True)
            result = prepare_demo(args.name, args.dir)
        elif args.command == "new":
            result = prepare_new(args.directory, args.template)
        elif args.database.is_dir():
            result = existing(args.database)
            if args.project is not None:
                result["project_id"] = args.project
        else:
            result = {"database": args.database.expanduser().resolve(), "project_id": args.project, "created": False}
        database = verify_database(result["database"], result["project_id"])
        print(("已创建 / Created: " if result["created"] else "继续使用 / Reopening: ") + str(database), flush=True)
        for issue in result.get("issues", []):
            print(json.dumps(issue, ensure_ascii=False), file=sys.stderr)
        serve(database, port=args.port, project=result["project_id"], open_browser=not args.no_browser)
        return 0
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        parser.exit(1, f"启动失败 / Cannot start: {error}\n")
    except ModuleNotFoundError as error:
        parser.exit(1, f"所需工具包未安装 / Required tool is missing: {error.name}\n")


COMMANDS = [{"name": "launcher", "summary": "统一启动案例、已有项目、模板和 MCP；重复打开保留修改",
             "entrypoint": "layerweave.tool.builtin.shared.launcher.__main__:main",
             "cli": "python -X utf8 -m layerweave.tool.builtin.shared.launcher", "read_only": False,
             "input_schema": {"type": "object", "properties": {"argv": {"type": "array", "items": {"type": "string"}, "description": "CLI 参数列表；此入口不在默认 MCP 中暴露"}}},
             "cli_mapping": {"argv": ["version", "command", "name", "list", "dir", "directory", "template", "database", "project", "port", "no_browser", "names"]},
             "returns": "命令退出码；demo/new/view 在前台运行视图服务。",
             "examples": [{"cli": "python -X utf8 -m layerweave demo"},
                          {"cli": "python -X utf8 -m layerweave view project.sqlite3 --no-browser"}],
             "mcp": {"enabled": False, "reason": "本机启动入口；通过 CLI 管理常驻进程"}}]

if __name__ == "__main__":
    raise SystemExit(main())

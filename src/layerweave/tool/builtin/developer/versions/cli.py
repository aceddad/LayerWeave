"""版本登记命令：同步声明或查看上次登记；不加载被扫描组件。"""
from layerweave.support.cli import parser_for, run_cli
from layerweave.support.feedback import format_feedback

from .service import manage_versions


def format_versions(result):
    if not result["ok"]:
        return format_feedback(result)
    data = result["data"]
    labels = {"online": "在线", "inactive": "失效", "unknown": "无法核对"}
    lines = ["版本记录：" + "，".join(f"{labels[state]} {count}" for state, count in data["counts"].items())]
    if "checked_at" in data:
        lines.append(f"本次同步：{data['checked_at']} · {data['status']}")
    elif not data.get("registered", True):
        lines.append("尚未登记；执行 sync 会自动扫描并登记声明。")
    for row in data["items"]:
        lines.append(f"\n#{row['id']} {row['name']}  {row['version']}  {labels.get(row['status'], row['status'])}")
        lines.append(f"  {row['kind']} · {row['description']}\n  更新说明：{row['changes']}\n  核对时间：{row['checked_at']}")
        for source, state in sorted(row["sources"].items()):
            lines.append(f"  {labels.get(state, state)}：{source}")
    for issue in data.get("issues", []):
        lines.append(f"[声明读取失败] {issue['source']}：{issue['message']}")
    return "\n".join(lines)


def main():
    parser = parser_for("扫描并自动登记组件版本，或读取上次核对结果；不控制组件运行", project=False, commands=COMMANDS)
    parser.add_argument("action", nargs="?", default="sync", choices=["sync", "read"], help="默认 sync 会写入；read 仅读取")
    parser.add_argument("--root", dest="roots", action="append", help="sync 的扫描目录或 component.toml，可重复；省略时扫描基础声明和内置工具区")
    parser.add_argument("--name", help="read 按组件稳定名称精确筛选")
    parser.add_argument("--status", choices=["online", "inactive", "unknown"], help="read 按在线/失效/无法核对筛选")
    return run_cli(parser, lambda connection, args: manage_versions(connection, args.action, roots=args.roots,
                   name=args.name, status=args.status), formatter=format_versions)


COMMANDS = [{'name': 'manage_versions',
  'aliases': ['versions'],
  'summary': '自动登记组件声明并核对版本存在状态；查看上次同步记录与更新说明',
  'entrypoint': 'layerweave.tool.builtin.developer.versions.service:manage_versions',
  'cli': 'python -m layerweave.tool.builtin.developer.versions.cli',
  'read_only': False,
  'context': ['database'],
  'returns': '标准 operation/ok/data/checks；data 含 items、counts。sync 附 roots/checked_at/status/issues；读取失败可部分完成，ok '
             '表示数据库操作成功。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.developer.versions.cli DATABASE sync --json',
                'arguments': {'action': 'read'}},
               {'cli': 'python -m layerweave.tool.builtin.developer.versions.cli DATABASE sync --root ./my-tools '
                       '--json'},
               {'cli': 'python -m layerweave.tool.builtin.developer.versions.cli DATABASE read --name '
                       'layerweave.editing --json'}],
  'notes': ['声明使用 component.toml，name/version 必填字符串；kind 默认 tool，description/changes 默认空字符串。',
            'name + version 完全匹配；缺席的历史版本标为 inactive，不删除记录；未扫描范围不改变。',
            '在线只表示声明存在可读，不测试工具功能，不自动下载、升级或限制使用。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'action': {'type': 'string',
                                             'default': 'sync',
                                             'description': 'sync 会写入版本表及日志；read 只查询',
                                             'enum': ['sync', 'read']},
                                  'roots': {'type': ['array', 'null'],
                                            'description': 'sync 的目录或 component.toml 路径列表；替换默认扫描范围，CLI 重复 '
                                                           '--root；省略时基础声明加内置工具目录',
                                            'items': {}},
                                  'name': {'type': ['string', 'null'], 'description': 'read 按组件名精确筛选'},
                                  'status': {'type': ['string', 'null'],
                                             'description': 'read 按上次核对状态筛选',
                                             'enum': ['online', 'inactive', 'unknown']}},
                   'additionalProperties': False,
                   'required': ['database']},
  'mcp': {'route': 'edit',
          'group': 'developer',
          'database': 'connection',
          'paths': [],
          'route_by': 'action',
          'action_routes': {'sync': 'edit', 'read': 'query'},
          'path_arrays': ['roots']},
  'cli_only': ['json']}]


if __name__ == "__main__":
    raise SystemExit(main())

"""视图表（折叠、已读、共享布局与组合成员）的声明：检查现有表，旧声明显式升级。

折叠和已读表第一次使用时才建，布局表第一次编辑时才建。0.21.0 起声明多了逻辑引用（JSON 交换复制项目时，
折叠跟着层换号，已读不带过去，见 fold.py、notes/reads.py）。旧库里的表还是老声明，要显式登记一次，复制才按新规矩走：
不等下一次折叠才顺带升级（可能先导出了），也不在普通读取里偷偷写库。登记只改表的声明，不改数据、编号和改动日志。
库里还没有的表不建：等第一次用到时按现在的声明建。

python -X utf8 -m layerweave.tool.builtin.view.tables DATABASE [--upgrade]
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

from layerweave.support.api import open_database, register_tables, table_specs

from .data import open_readonly
from .fold import TABLE
from .notes.reads import READ_TABLE
from .layout_store import TABLES as LAYOUT_TABLES

DECLARED = {**TABLE, **READ_TABLE, **LAYOUT_TABLES}
NAMES = {"view_layer": "折叠", "view_note": "已读", "view_layout": "画板位置与尺寸", "view_layout_member": "画板组合成员"}
META = ("logical_references", "exchange")   # 0.21.0 加的元信息：旧库里缺的就是这些


def check_tables(database):
    """只读：每张视图表在库里的状态——absent（还没建）、current（和现在的声明一样）、stale（旧声明，差哪几项）。"""
    with closing(open_readonly(database)) as connection:
        specs = table_specs(connection)
    tables = []
    for kind, spec in DECLARED.items():
        if kind not in specs:
            tables.append({"kind": kind, "name": NAMES[kind], "state": "absent", "differs": []})
            continue
        differs = [key for key in META if key in spec and specs[kind].get(key) != spec[key]]
        tables.append({"kind": kind, "name": NAMES[kind], "state": "stale" if differs else "current", "differs": differs})
    return {"tables": tables, "upgrade_needed": any(t["state"] == "stale" for t in tables)}


def upgrade_tables(database):
    """把旧声明的视图表按现在的声明登记一遍（register_tables，在它自己的写会话里）。没有的表不建。"""
    stale = [t["kind"] for t in check_tables(database)["tables"] if t["state"] == "stale"]
    if stale:
        with closing(open_database(database)) as connection:
            register_tables(connection, {kind: DECLARED[kind] for kind in stale})
    return {**check_tables(database), "upgraded": stale}


def describe(result):
    state = {"absent": "还没有（第一次用到时按现在的声明建）", "current": "是现在的声明", "stale": "旧声明，缺 "}
    lines = [f"{t['kind']}（{t['name']}）：{state[t['state']]}" + ("、".join(t["differs"]) if t["state"] == "stale" else "")
             for t in result["tables"]]
    if result.get("upgraded"):
        lines.append("已经按现在的声明登记：" + "、".join(result["upgraded"]) + "（只改声明，不改数据）")
    elif result["upgrade_needed"]:
        lines.append("要用 JSON 交换复制这个库里的项目，先跑一次：python -X utf8 -m layerweave.tool.builtin.view.tables DATABASE --upgrade")
    return "\n".join(lines)


def tables(database, *, upgrade=False):
    result = upgrade_tables(database) if upgrade else check_tables(database)
    return {**result, "text": describe(result)}


COMMANDS = [{'name': 'view_tables',
  'summary': '视图自己的表（折叠、已读）在库里登记的声明：查是不是现在这份；--upgrade 把旧库显式升级（只改声明，不改数据）',
  'entrypoint': 'layerweave.tool.builtin.view.tables:tables',
  'cli': 'python -X utf8 -m layerweave.tool.builtin.view.tables',
  'read_only': False,
  'context': ['database'],
  'returns': 'tables（kind、name、state：absent / current / stale、differs）、upgrade_needed、upgraded（升级了哪些）、text。',
  'examples': [{'cli': 'python -X utf8 -m layerweave.tool.builtin.view.tables DATABASE'},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.view.tables DATABASE --upgrade'}],
  'notes': ['0.21.0 起，折叠表声明了逻辑引用（JSON 交换复制项目时折叠跟着层换号），已读表复制时不带过去（新项目里重新记）。',
            '旧库要跑一次 --upgrade，复制才按新规矩走；视图服务启动时发现旧声明会提示。',
            '库里还没有的表不建，第一次折叠、标已读时按现在的声明建。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'upgrade': {'type': 'boolean',
                                              'default': False,
                                              'description': '把旧声明的表按现在的声明登记一遍；不给就只查'}},
                   'additionalProperties': False,
                   'required': ['database']},
  'mcp': {'route': 'admin', 'group': 'view', 'database': 'path', 'paths': [], 'route_by': 'upgrade'},
  'cli_only': ['json']}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图自己的表的声明", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path)
    p.add_argument("--upgrade", action="store_true", help="把旧声明的表按现在的声明登记一遍")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    a = p.parse_args()
    try:
        result = tables(a.database, upgrade=a.upgrade)
    except (ValueError, OSError) as error:
        print(f"没有做成：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if a.json else result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

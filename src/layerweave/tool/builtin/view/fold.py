"""折叠：哪些层收起来了，记在业务库里视图自己的表（view_fold），网页和 AI 共用一份。
折叠一层 = 收起它自己和下面所有的层，画布上只剩一条带边框的细条，写明收着什么、谁收的。

一条记录的身份就是它挂着的层：（项目，层编号），不另外发号（id_source = provided）。
不声明引用：层被使用工具删掉时不受阻挡；编号不回收，留下的记录不会被新层误认，视图读的时候忽略。
写入走统一写会话，进改动日志、可以撤销；视图的"改动"面板不列它们（不是内容的改动）。

python -m layerweave.tool.builtin.view.fold DATABASE PROJECT_ID                       列出折叠的层
python -m layerweave.tool.builtin.view.fold DATABASE PROJECT_ID fold 5 7 --by Claude  折叠层 5、7
python -m layerweave.tool.builtin.view.fold DATABASE PROJECT_ID unfold 5               展开
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

from layerweave.support.api import open_database, read_record, register_tables, run_operation, table_specs

KIND = "view_fold"
TABLE = {KIND: {
    "id_source": "provided",
    "fields": {
        "folded": {"type": "INTEGER", "nullable": False, "default": 1},
        "by": {"type": "TEXT", "nullable": False, "default": ""},
    },
}}


def read_folds(connection, project_id):
    """{层编号: 谁折叠的}。从没折叠过的库里还没有这张表，返回空的；只读连接也能用。"""
    if KIND not in table_specs(connection):
        return {}
    return {row["id"]: row["by"] for row in read_record(connection, KIND, project_id=project_id) if row["folded"]}


def set_folds(database, project_id, layers, folded, *, by=""):
    """把这些层折叠（folded=True）或展开。折叠时层要存在；已经是这个状态的不重写，免得改动日志里多出空操作。"""
    layers = sorted({int(layer) for layer in layers})
    if not layers:
        raise ValueError("要给出层编号")
    by = (by or "").strip()
    with closing(open_database(database)) as connection:
        register_tables(connection, TABLE)   # 相同声明重复登记什么也不做

        def work(write):
            changed = []
            for layer in layers:
                if folded and write.read("layer", project_id=project_id, id=layer) is None:
                    raise ValueError(f"项目 {project_id} 里没有层 #{layer}")
                row = write.read(KIND, project_id=project_id, id=layer)
                if row is None:
                    if folded:
                        write.create(KIND, {"id": layer, "folded": 1, "by": by}, project_id=project_id)
                        changed.append(layer)
                elif bool(row["folded"]) != folded:
                    write.update(KIND, layer, {"folded": int(folded), "by": by}, project_id=project_id)
                    changed.append(layer)
            return {"changed": changed}

        result = run_operation(connection, work)
        if not result["ok"]:
            error = result.get("error") or {}
            raise ValueError(error.get("message") or str(error))
        return {**(result["data"] or {}), "operation_id": result["operation_id"], "folded": read_folds(connection, project_id)}


def describe(folds, names):
    if not folds:
        return "没有折叠的层。"
    return "折叠的层：" + "、".join(f"#{layer} {names.get(layer, '（已删除）')}" + (f"（{by} 折叠）" if by else "")
                                for layer, by in sorted(folds.items()))


def fold(database, project_id, action="list", *, layers=None, by=None):
    """list：列出折叠的层；fold / unfold：折叠或展开 layers（层编号列表）。返回 folded（层编号 → 谁折叠的）和 text。"""
    if action in ("fold", "unfold"):
        result = set_folds(database, project_id, layers or [], action == "fold", by=by or "")
    elif action == "list":
        with closing(open_database(database)) as connection:
            result = {"folded": read_folds(connection, project_id)}
    else:
        raise ValueError(f"不认识的动作：{action}（list、fold、unfold）")
    with closing(open_database(database)) as connection:
        names = {row["id"]: row["name"] or row["type"] for row in read_record(connection, "layer", project_id=project_id)}
    return {**result, "text": describe(result["folded"], names)}


COMMANDS = [{
    "name": "view_fold",
    "summary": "查看或改变视图里哪些层折叠了：折叠一层就收起它和下面所有的层；网页和 AI 共用一份，存在数据库里",
    "entrypoint": "layerweave.tool.builtin.view.fold:fold",
    "cli": "python -m layerweave.tool.builtin.view.fold",
    "read_only": False,
    "context": ["database", "project_id"],
    "parameters": {
        "action": {"type": "string", "description": "list（列出）、fold（折叠）或 unfold（展开）", "default": "list"},
        "layers": {"type": "array", "description": "fold / unfold 的层编号"},
        "by": {"type": "string", "description": "谁折叠的，画布上的细条会写出来，例如 Claude"},
    },
    "returns": "folded（层编号 → 谁折叠的）、text；改动时另有 changed、operation_id。",
    "examples": [{"cli": "python -m layerweave.tool.builtin.view.fold DATABASE 1"},
                 {"cli": "python -m layerweave.tool.builtin.view.fold DATABASE 1 fold 5 7 --by Claude"},
                 {"cli": "python -m layerweave.tool.builtin.view.fold DATABASE 1 unfold 5"}],
    "notes": ["和用户共用：折叠后用户的网页两秒内跟着收起，截图也照这份画。只为了看清楚而收起时，说明理由，看完记得展开。",
              "写入业务库里视图自己的表 view_fold（一层一行，身份就是层的编号），进改动日志、可以撤销。",
              "左右接续的画板上，同名层合成一条轨道；网页上折叠这条轨道会折叠它包含的每一个层。"],
}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图折叠", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int)
    p.add_argument("action", nargs="?", default="list", choices=("list", "fold", "unfold"))
    p.add_argument("layers", nargs="*", type=int, help="层编号")
    p.add_argument("--by", help="谁折叠的")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    a = p.parse_args()
    try:
        result = fold(a.database, a.project_id, a.action, layers=a.layers, by=a.by)
    except (ValueError, OSError) as error:
        print(f"没有做成：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if a.json else result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

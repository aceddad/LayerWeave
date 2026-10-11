"""折叠：人和 AI 各有各的折叠，互相看得见。记在业务库里视图自己的表（view_layer）。
折叠一层 = 收起它自己和下面所有的层。自己这边折叠的，画成一条带边框的细条；对方折叠的照常展开，标出"AI 折叠了""用户折叠了"
和说明（tips）。两边都能展开对方的折叠：人让 AI 看回来，AI 把人收起的东西展开给人看。

网页是人这边（按网页里的署名记），view_fold 命令和截图是 AI 这边。
一条记录的身份就是它挂着的层：（项目，层编号），不另外发号（id_source = provided）；以后挂在层上的别的视图状态也放这张表。
不声明引用：层被使用工具删掉时不受阻挡；编号不回收，留下的记录不会被新层误认，视图读的时候忽略。
写入走统一写会话，进改动日志、可以撤销；视图的"改动"面板不列它们（不是内容的改动）。

python -m layerweave.tool.builtin.view.fold DATABASE PROJECT_ID                                    两边的折叠
python -m layerweave.tool.builtin.view.fold DATABASE PROJECT_ID fold 5 7 --by Claude --why 先对字幕  AI 这边折叠
python -m layerweave.tool.builtin.view.fold DATABASE PROJECT_ID unfold 5                            展开 AI 这边的
python -m layerweave.tool.builtin.view.fold DATABASE PROJECT_ID unfold 5 --side user --by Claude --why 这里要你看一下
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

from layerweave.support.api import open_database, read_record, register_tables, run_operation, table_specs

KIND = "view_layer"
SIDES = ("user", "ai")
SIDE_NAME = {"user": "用户", "ai": "AI"}
TABLE = {KIND: {
    "id_source": "provided",
    "fields": {f"{side}_{field}": {"type": "TEXT", "nullable": False, "default": ""}
               for side in SIDES for field in ("fold", "tips")},
}}


def read_folds(connection, project_id):
    """[{layer, user, user_tips, ai, ai_tips}]：user / ai 是那一边谁折叠的，空着就是没折叠。
    从没折叠过的库里还没有这张表，返回空的；只读连接也能用。"""
    if KIND not in table_specs(connection):
        return []
    return [{"layer": row["id"], "user": row["user_fold"], "user_tips": row["user_tips"], "ai": row["ai_fold"], "ai_tips": row["ai_tips"]}
            for row in read_record(connection, KIND, project_id=project_id) if row["user_fold"] or row["ai_fold"]]


def set_folds(database, project_id, layers, side, action, *, by="", tips=None):
    """side 这一边：fold 折叠（可带 tips）、unfold 展开、tips 只改说明。已经是这个状态的不重写，免得日志里多出空操作。"""
    if side not in SIDES:
        raise ValueError(f"不认识的一边：{side}（user、ai）")
    if action not in ("fold", "unfold", "tips"):
        raise ValueError(f"不认识的动作：{action}（fold、unfold、tips）")
    layers = sorted({int(layer) for layer in layers})
    if not layers:
        raise ValueError("要给出层编号")
    by = (by or "").strip() or SIDE_NAME[side]
    with closing(open_database(database)) as connection:
        register_tables(connection, TABLE)   # 相同声明重复登记什么也不做

        def work(write):
            changed = []
            for layer in layers:
                if action == "fold" and write.read("layer", project_id=project_id, id=layer) is None:
                    raise ValueError(f"项目 {project_id} 里没有层 #{layer}")
                row = write.read(KIND, project_id=project_id, id=layer)
                now = {"fold": row[f"{side}_fold"], "tips": row[f"{side}_tips"]} if row else {"fold": "", "tips": ""}
                if action == "fold":
                    want = {"fold": now["fold"] or by, "tips": (tips if tips is not None else now["tips"] if now["fold"] else "").strip()}
                elif action == "unfold":
                    want = {"fold": "", "tips": ""}
                else:
                    if not now["fold"]:
                        raise ValueError(f"层 #{layer} 在{SIDE_NAME[side]}这边没有折叠，写不了说明")
                    want = {"fold": now["fold"], "tips": (tips or "").strip()}
                if want == now:
                    continue
                values = {f"{side}_fold": want["fold"], f"{side}_tips": want["tips"]}
                if row is None:
                    write.create(KIND, {"id": layer, **values}, project_id=project_id)
                else:
                    write.update(KIND, layer, values, project_id=project_id)
                changed.append(layer)
            return {"changed": changed}

        result = run_operation(connection, work)
        if not result["ok"]:
            error = result.get("error") or {}
            raise ValueError(error.get("message") or str(error))
        return {**(result["data"] or {}), "operation_id": result["operation_id"], "folds": read_folds(connection, project_id)}


def describe(folds, names):
    lines = []
    for side in SIDES:
        rows = [f for f in folds if f[side]]
        lines.append(f"{SIDE_NAME[side]}这边折叠的层：" + ("、".join(
            f"#{f['layer']} {names.get(f['layer'], '（已删除）')}（{f[side]}" + (f"：{f[side + '_tips']}" if f[side + "_tips"] else "") + "）"
            for f in rows) or "没有"))
    return "\n".join(lines)


def fold(database, project_id, action="list", *, layers=None, side="ai", by=None, why=None):
    """list：两边的折叠；fold / unfold：折叠或展开 layers（默认 AI 这边，side="user" 时展开用户的折叠）；
    tips：改折叠的说明。AI 展开用户的折叠并写了 why 时，在这一层上留一条批注告诉用户为什么。"""
    if action in ("fold", "unfold", "tips"):
        if side == "user" and action != "unfold":
            raise ValueError("AI 不替用户折叠、不改用户的备注；只能展开用户折叠的层给用户看")
        result = set_folds(database, project_id, layers or [], side, action, by=by or "", tips=why)
        if side == "user" and why and result["changed"]:
            from .note import add_note
            add_note(database, project_id, f"展开了你折叠的这一层：{why}",
                     targets=[("layer", project_id, layer) for layer in result["changed"]], author=by or "AI")
    elif action == "list":
        with closing(open_database(database)) as connection:
            result = {"folds": read_folds(connection, project_id)}
    else:
        raise ValueError(f"不认识的动作：{action}（list、fold、unfold、tips）")
    with closing(open_database(database)) as connection:
        names = {row["id"]: row["name"] or row["type"] for row in read_record(connection, "layer", project_id=project_id)}
    return {**result, "text": describe(result["folds"], names)}


COMMANDS = [{
    "name": "view_fold",
    "summary": "视图里的折叠：人和 AI 各有各的，互相看得见。查看两边的折叠，折叠或展开 AI 这边的层，或者把用户折叠的层展开给用户看",
    "entrypoint": "layerweave.tool.builtin.view.fold:fold",
    "cli": "python -m layerweave.tool.builtin.view.fold",
    "read_only": False,
    "context": ["database", "project_id"],
    "parameters": {
        "action": {"type": "string", "description": "list（两边的折叠）、fold、unfold 或 tips（改说明）", "default": "list"},
        "layers": {"type": "array", "description": "层编号；折叠一层会收起它和下面所有的层"},
        "side": {"type": "string", "description": "ai（默认，AI 这边）；user 只能用于 unfold：把用户折叠的层展开给用户看", "default": "ai"},
        "by": {"type": "string", "description": "谁，例如 Claude；画在细条和标签上"},
        "why": {"type": "string", "description": "折叠的原因（画在细条上）；展开用户的折叠时，写了就在那一层上留一条批注告诉用户"},
    },
    "returns": "folds（[{layer, user, user_tips, ai, ai_tips}]，空着的一边是没折叠）、text；改动时另有 changed、operation_id。",
    "examples": [{"cli": "python -m layerweave.tool.builtin.view.fold DATABASE 1"},
                 {"cli": "python -m layerweave.tool.builtin.view.fold DATABASE 1 fold 5 7 --by Claude --why 先对字幕"},
                 {"cli": "python -m layerweave.tool.builtin.view.fold DATABASE 1 unfold 5 --side user --by Claude --why 这一段的画面和字幕对不上"}],
    "notes": ["用户折叠了的层在截图里照常展开，标着\"用户折叠了\"：内容都在，判断时照常检查；那只说明用户现在不关注它。",
              "AI 这边折叠的层在截图里收成一条细条，内容没画出来；截图返回的 folded 列出两边的折叠。",
              "两边都能展开对方的：用户在网页上点标签上的 × 就展开了 AI 的折叠，开工时先用 list 看一眼。",
              "写入业务库里视图自己的表 view_layer（一层一行，身份就是层的编号），进改动日志、可以撤销。"],
}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图折叠（人和 AI 各一份）", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int)
    p.add_argument("action", nargs="?", default="list", choices=("list", "fold", "unfold", "tips"))
    p.add_argument("layers", nargs="*", type=int, help="层编号")
    p.add_argument("--side", choices=SIDES, default="ai", help="哪一边；user 只能用于 unfold")
    p.add_argument("--by", help="谁"); p.add_argument("--why", help="原因 / 说明")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    a = p.parse_args()
    try:
        result = fold(a.database, a.project_id, a.action, layers=a.layers, side=a.side, by=a.by, why=a.why)
    except (ValueError, OSError) as error:
        print(f"没有做成：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if a.json else result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

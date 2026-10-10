"""画布排版：每个根层连同它的子树是一块画板；单位相同的根默认拼在同一块画板里，上下排列，共用一把尺子和播放头。
排版只存在本机（~/.layerweave/view/<数据库路径的散列>.layout.json），不写业务数据库。
用户在网页里拖动、拼接、拆出，改的也是这份文件；用这个工具改了以后，打开着的网页两秒内跟着变。

python -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID                              查看画板
python -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID merge 根 --to 另一个根 [--side above|below]
python -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID split 根
python -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID move 根 --x 0 --y 600
python -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID reset
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

from .data import open_readonly, project_roots
from .state import state_path

LOCK = threading.Lock()


def layout_path(database, root=None):
    return state_path(database, root).with_suffix(".layout.json")


def layout_serial(database, root=None):
    """排版文件的修改时间，网页靠它发现排版被别人（AI 或另一个窗口）改过。"""
    path = layout_path(database, root)
    return path.stat().st_mtime_ns if path.is_file() else 0


def _read_file(database, root):
    path = layout_path(database, root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"projects": {}}
    return data if isinstance(data, dict) and isinstance(data.get("projects"), dict) else {"projects": {}}


def _number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def clean_boards(boards):
    """只留下认识的字段：roots（根层编号）、x / y（画布上的位置，None 表示自动排）、pps（每单位多少像素，None 表示自动）。"""
    out = []
    for board in boards if isinstance(boards, list) else []:
        if not isinstance(board, dict) or not isinstance(board.get("roots"), list):
            continue
        roots = [r for r in board["roots"] if isinstance(r, int) and not isinstance(r, bool)]
        pps = _number(board.get("pps"))
        out.append({"roots": roots, "x": _number(board.get("x")), "y": _number(board.get("y")),
                    "pps": pps if pps and pps > 0 else None})
    return out


def reconcile(roots, boards):
    """让排版和数据库里现有的根对上：删掉已经不存在的根；单位不同的根不能待在同一块画板里；
    新出现的根并进同单位的第一块画板，没有就单独成一块。boards 为 None 时全部按单位自动分组。"""
    keys = {root["id"]: root["key"] for root in roots}
    out, placed = [], set()
    for board in clean_boards(boards):
        members = [r for r in board["roots"] if r in keys and r not in placed]
        if not members:
            continue
        first = keys[members[0]]
        kept = [r for r in members if r == members[0] or (first is not None and keys[r] == first)]
        placed.update(kept)
        out.append({**board, "roots": kept})
    for root in roots:
        if root["id"] in placed:
            continue
        home = next((b for b in out if root["key"] is not None and keys[b["roots"][0]] == root["key"]), None)
        if home is None:
            out.append({"roots": [root["id"]], "x": None, "y": None, "pps": None})
        else:
            home["roots"].append(root["id"])
        placed.add(root["id"])
    return out


def load_layout(database, project_id, roots, root=None):
    saved = _read_file(database, root)["projects"].get(str(project_id))
    return reconcile(roots, saved.get("boards") if isinstance(saved, dict) else None)


def save_layout(database, project_id, boards, root=None):
    with LOCK:
        data = _read_file(database, root)
        data["database"] = str(Path(database).resolve())
        data["projects"][str(project_id)] = {"boards": boards,
                                             "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        path = layout_path(database, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False)
        os.replace(temp, path)
    return boards


def clear_layout(database, project_id, root=None):
    with LOCK:
        data = _read_file(database, root)
        if data["projects"].pop(str(project_id), None) is None:
            return
        path = layout_path(database, root)
        handle, temp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False)
        os.replace(temp, path)


def _board_of(boards, root_id):
    for board in boards:
        if root_id in board["roots"]:
            return board
    raise ValueError(f"{root_id} 不是这个项目的根层（只有根层才有自己的画板；子层跟着它的根走）")


def merge(boards, roots, root_id, target_id, side="below"):
    """把 root_id 所在的整块画板拼到 target_id 那一段的上方或下方。单位必须相同。"""
    if side not in ("above", "below"):
        raise ValueError("side 只能是 above 或 below")
    keys = {root["id"]: root for root in roots}
    moving, home = _board_of(boards, root_id), _board_of(boards, target_id)
    if moving is home:
        raise ValueError(f"根层 {root_id} 和 {target_id} 已经在同一块画板里")
    a, b = keys[moving["roots"][0]], keys[target_id]
    if a["key"] is None or a["key"] != b["key"]:
        raise ValueError(f"单位不同，不能拼在一起：{a['name']}（{a['unit'] or '没有单位'}）和 {b['name']}（{b['unit'] or '没有单位'}）")
    at = home["roots"].index(target_id) + (1 if side == "below" else 0)
    home["roots"][at:at] = moving["roots"]
    boards.remove(moving)
    return boards


def split(boards, root_id):
    """把 root_id 从它的画板里拆出来，单独成一块；位置留空，由网页自动摆在其他画板下方。"""
    board = _board_of(boards, root_id)
    if len(board["roots"]) == 1:
        raise ValueError(f"根层 {root_id} 已经单独占一块画板")
    board["roots"].remove(root_id)
    boards.insert(boards.index(board) + 1, {"roots": [root_id], "x": None, "y": None, "pps": board["pps"]})
    return boards


def move(boards, root_id, x, y):
    board = _board_of(boards, root_id)
    board["x"], board["y"] = float(x), float(y)
    return boards


def describe(boards, roots):
    names = {root["id"]: root for root in roots}
    lines = []
    for number, board in enumerate(boards, 1):
        unit = names[board["roots"][0]]["unit"] or "没有单位"
        where = "自动排" if board["x"] is None or board["y"] is None else f"位置 ({board['x']:g}, {board['y']:g})"
        members = "、".join(f"{names[r]['name'] or '层'}（{r}）" for r in board["roots"])
        lines.append(f"画板 {number}［{unit}］{where}：{members}")
    return "\n".join(lines) or "这个项目还没有层。"


def arrange(database, project_id, action="show", *, root=None, target=None, side="below", x=None, y=None, state_root=None):
    """查看或调整画板。action：show、merge（root 拼到 target 的 side 一侧）、split（拆出 root）、move（root 所在画板移到 x, y）、reset。"""
    with closing(open_readonly(database)) as connection:
        roots = project_roots(connection, project_id)
    if action == "reset":
        clear_layout(database, project_id, state_root)
    boards = load_layout(database, project_id, roots, state_root)
    if action in ("merge", "split", "move") and root is None:
        raise ValueError(f"{action} 需要指定根层编号")
    if action == "merge":
        if target is None:
            raise ValueError("merge 需要 --to 指定拼到哪个根层旁边")
        merge(boards, roots, root, target, side)
    elif action == "split":
        split(boards, root)
    elif action == "move":
        if x is None or y is None:
            raise ValueError("move 需要 --x 和 --y")
        move(boards, root, x, y)
    elif action not in ("show", "reset"):
        raise ValueError(f"不认识的动作：{action}")
    if action in ("merge", "split", "move"):
        save_layout(database, project_id, boards, state_root)
    names = {r["id"]: r for r in roots}
    return {"boards": [{"board": n, "unit": names[b["roots"][0]]["unit"], "x": b["x"], "y": b["y"],
                        "roots": [{"id": r, "name": names[r]["name"]} for r in b["roots"]]} for n, b in enumerate(boards, 1)],
            "text": describe(boards, roots)}


COMMANDS = [{
    "name": "view_layout",
    "summary": "查看或调整视图画布上的画板：同单位的根拼在一起或拆开、移动画板、恢复自动排版",
    "entrypoint": "layerweave.tool.builtin.view.layout:arrange",
    "cli": "python -m layerweave.tool.builtin.view.layout",
    "read_only": True,
    "context": ["database", "project_id"],
    "parameters": {
        "action": {"type": "string", "description": "show、merge、split、move 或 reset", "default": "show"},
        "root": {"type": "integer", "description": "要操作的根层编号（子层跟着它的根走）"},
        "target": {"type": "integer", "description": "merge 时拼到哪个根层旁边"},
        "side": {"type": "string", "description": "merge 时拼在 target 的上方（above）还是下方（below）", "default": "below"},
        "x": {"type": "number", "description": "move 时画板左上角在画布上的横坐标（像素）"},
        "y": {"type": "number", "description": "move 时画板左上角在画布上的纵坐标（像素）"},
    },
    "returns": "boards（每块画板的序号、单位、位置、包含的根层）和 text（给人看的摘要）。",
    "examples": [
        {"cli": "python -m layerweave.tool.builtin.view.layout DATABASE 1"},
        {"cli": "python -m layerweave.tool.builtin.view.layout DATABASE 1 split 19"},
        {"cli": "python -m layerweave.tool.builtin.view.layout DATABASE 1 merge 19 --to 1 --side above"},
    ],
    "notes": ["只改本机的视图排版文件，不写业务数据库，所以标为只读。",
              "单位相同（秒和 s 算同一种）才能拼；拼在一起的根共用时间刻度，同一个数值上下对齐。",
              "左右不拼接：左右摆放只是位置，不表示先后播放。"],
}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图画布上的画板排版", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int)
    p.add_argument("action", nargs="?", default="show", choices=("show", "merge", "split", "move", "reset"))
    p.add_argument("root", nargs="?", type=int)
    p.add_argument("--to", dest="target", type=int); p.add_argument("--side", choices=("above", "below"), default="below")
    p.add_argument("--x", type=float); p.add_argument("--y", type=float)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    try:
        result = arrange(a.database, a.project_id, a.action, root=a.root, target=a.target, side=a.side, x=a.x, y=a.y)
    except (ValueError, OSError) as error:
        print(f"排版失败：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if a.json else result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

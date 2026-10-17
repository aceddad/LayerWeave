"""画布排版：每个根层连同它的子树是一块画板。画板里的根排成几行：
- 上下 = 同时：不同行共用一把尺子，同一个数值上下对齐。单位相同的根默认各占一行、拼在同一块画板里。
- 左右 = 接续：同一行里后一个根的 0 接在前一个根的结尾（比如第二章接在第一章后面），名字相同的层合成同一条轨道。只能手动接。
排版只存在本机（~/.layerweave/view/<数据库路径的散列>.layout.json），不写业务数据库。
用户在网页里拖动、拼接、拆出，改的也是这份文件；用这个工具改了以后，打开着的网页两秒内跟着变。

python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID                              查看画板
python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID merge 根 --to 另一个根 [--side above|below|left|right]
python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID split 根
python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID move 根 --x 0 --y 600
python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID reset
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

from .data import open_readonly, project_view
from .state import state_path

LOCK = threading.Lock()
SIDES = ("above", "below", "left", "right")


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


def _is_id(value):
    return isinstance(value, int) and not isinstance(value, bool)


def clean_boards(boards):
    """只留下认识的字段：rows（每行是左右接续的根层编号）、x / y（画布上的位置，None 表示自动排）、
    pps（每单位多少像素，None 表示自动）。旧格式的 roots（一列根）按每个根一行读入。"""
    out = []
    for board in boards if isinstance(boards, list) else []:
        if not isinstance(board, dict):
            continue
        rows = board.get("rows")
        if not isinstance(rows, list):
            rows = [[r] for r in board["roots"]] if isinstance(board.get("roots"), list) else None
        if rows is None:
            continue
        rows = [[r for r in row if _is_id(r)] for row in rows if isinstance(row, list)]
        pps = _number(board.get("pps"))
        out.append({"rows": rows, "x": _number(board.get("x")), "y": _number(board.get("y")),
                    "pps": pps if pps and pps > 0 else None})
    return out


def board_roots(board):
    return [r for row in board["rows"] for r in row]


def reconcile(roots, boards):
    """让排版和数据库里现有的根对上：删掉已经不存在的根；单位不同的根不能待在同一块画板里；
    新出现的根作为新的一行并进同单位的第一块画板，没有就单独成一块。boards 为 None 时全部按单位自动分组。"""
    keys = {root["id"]: root["key"] for root in roots}
    out, placed = [], set()
    for board in clean_boards(boards):
        rows, first = [], None
        for row in board["rows"]:
            kept = []
            for r in row:
                if r not in keys or r in placed:
                    continue
                if first is not None and (keys[first] is None or keys[r] != keys[first]):
                    continue   # 单位不同：留给后面按新根处理
                first = first if first is not None else r
                kept.append(r)
                placed.add(r)
            if kept:
                rows.append(kept)
        if rows:
            out.append({**board, "rows": rows})
    for root in roots:
        if root["id"] in placed:
            continue
        home = next((b for b in out if root["key"] is not None and keys[b["rows"][0][0]] == root["key"]), None)
        if home is None:
            out.append({"rows": [[root["id"]]], "x": None, "y": None, "pps": None})
        else:
            home["rows"].append([root["id"]])
        placed.add(root["id"])
    return out


def chain_offsets(row, extents):
    """左右接续：第一段不动，后一段的本地 0 接在前一段的结尾。返回 {根: 偏移}，画板时间 = 本地时间 + 偏移。"""
    offsets, end = {}, None
    for r in row:
        begin, finish = extents.get(r, (0, 0))
        offset = 0 if end is None else end - min(0, begin)
        offsets[r] = offset
        end = offset + finish
    return offsets


def load_layout(database, project_id, roots, root=None):
    saved = _read_file(database, root)["projects"].get(str(project_id))
    return reconcile(roots, saved.get("boards") if isinstance(saved, dict) else None)


def _write(database, data, root):
    path = layout_path(database, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False)
    os.replace(temp, path)


def save_layout(database, project_id, boards, root=None):
    with LOCK:
        data = _read_file(database, root)
        data["database"] = str(Path(database).resolve())
        data["projects"][str(project_id)] = {"boards": boards,
                                             "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        _write(database, data, root)
    return boards


def clear_layout(database, project_id, root=None):
    with LOCK:
        data = _read_file(database, root)
        if data["projects"].pop(str(project_id), None) is not None:
            _write(database, data, root)


def _board_of(boards, root_id):
    for board in boards:
        if root_id in board_roots(board):
            return board
    raise ValueError(f"{root_id} 不是这个项目的根层（只有根层才有自己的画板；子层跟着它的根走）")


def merge(boards, roots, root_id, target_id, side="below"):
    """把 root_id 所在的整块画板拼到 target_id 旁边。above / below：作为新的行放在 target 那一行的上方或下方（同时）；
    left / right：接在 target 的前面或后面（接续），这时被拼的画板只能有一行。单位必须相同。"""
    if side not in SIDES:
        raise ValueError("side 只能是 above、below、left 或 right")
    info = {root["id"]: root for root in roots}
    moving, home = _board_of(boards, root_id), _board_of(boards, target_id)
    if moving is home:
        raise ValueError(f"根层 {root_id} 和 {target_id} 已经在同一块画板里；要换位置先拆出来")
    a, b = info[moving["rows"][0][0]], info[target_id]
    if a["key"] is None or a["key"] != b["key"]:
        raise ValueError(f"单位不同，不能拼在一起：{a['name']}（{a['unit'] or '没有单位'}）和 {b['name']}（{b['unit'] or '没有单位'}）")
    index = next(i for i, row in enumerate(home["rows"]) if target_id in row)
    if side in ("above", "below"):
        at = index + (side == "below")
        home["rows"][at:at] = moving["rows"]
    else:
        if len(moving["rows"]) != 1:
            raise ValueError(f"根层 {root_id} 所在的画板有好几行，不知道接哪一行：先把要接的根拆出来，再左右接")
        row = home["rows"][index]
        at = row.index(target_id) + (side == "right")
        row[at:at] = moving["rows"][0]
    boards.remove(moving)
    return boards


def split(boards, root_id):
    """把 root_id 从它的画板里拆出来，单独成一块；位置留空，由网页自动摆在其他画板下方。"""
    board = _board_of(boards, root_id)
    if len(board_roots(board)) == 1:
        raise ValueError(f"根层 {root_id} 已经单独占一块画板")
    for row in board["rows"]:
        if root_id in row:
            row.remove(root_id)
    board["rows"] = [row for row in board["rows"] if row]
    boards.insert(boards.index(board) + 1, {"rows": [[root_id]], "x": None, "y": None, "pps": board["pps"]})
    return boards


def move(boards, root_id, x, y):
    board = _board_of(boards, root_id)
    board["x"], board["y"] = float(x), float(y)
    return boards


def describe(boards, roots):
    info = {root["id"]: root for root in roots}
    extents = {r: tuple(info[r].get("extent") or (0, 0)) for r in info}
    lines = []
    for number, board in enumerate(boards, 1):
        unit = info[board["rows"][0][0]]["unit"] or "没有单位"
        where = "自动排" if board["x"] is None or board["y"] is None else f"位置 ({board['x']:g}, {board['y']:g})"
        rows = []
        for row in board["rows"]:
            offsets = chain_offsets(row, extents)
            rows.append(" → ".join(f"{info[r]['name'] or '层'}（{r}）" + (f"［从画板 {offsets[r]:g} 起］" if offsets[r] else "")
                                   for r in row))
        lines.append(f"画板 {number}［{unit}］{where}：" + "；".join(rows))
    return "\n".join(lines) or "这个项目还没有层。"


def arrange(database, project_id, action="show", *, root=None, target=None, side="below", x=None, y=None, state_root=None):
    """查看或调整画板。action：show、merge（root 拼到 target 的 side 一侧）、split（拆出 root）、move（root 所在画板移到 x, y）、reset。"""
    with closing(open_readonly(database)) as connection:
        view = project_view(connection, database, project_id)
    if view is None:
        raise ValueError(f"项目 {project_id} 不存在")
    roots = [r for r in view["roots"]]
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
    info = {r["id"]: r for r in roots}
    extents = {r: tuple(info[r]["extent"]) for r in info}
    out = []
    for number, board in enumerate(boards, 1):
        rows = []
        for row in board["rows"]:
            offsets = chain_offsets(row, extents)
            rows.append([{"id": r, "name": info[r]["name"], "offset": offsets[r]} for r in row])
        out.append({"board": number, "unit": info[board["rows"][0][0]]["unit"], "x": board["x"], "y": board["y"], "rows": rows})
    return {"boards": out, "text": describe(boards, roots)}


COMMANDS = [{'name': 'view_layout',
  'summary': '查看或调整视图画布上的画板：同单位的根上下拼（同时）、左右接（接续）或拆开，移动画板，恢复自动排版',
  'entrypoint': 'layerweave.tool.builtin.view.layout:arrange',
  'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout',
  'read_only': False,
  'context': ['database', 'project_id'],
  'returns': 'boards（每块画板的序号、单位、位置、各行的根层及接续偏移）和 text（给人看的摘要）。',
  'examples': [{'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE 1',
                'arguments': {'action': 'show'}},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE 1 split 19'},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE 1 merge 19 --to 1 --side above'},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE 1 merge 31 --to 1 --side right'}],
  'notes': ['show 只读取；merge/split/move/reset 修改本机排版文件。此复合命令按可写标记，不写业务数据库。',
            '单位相同（秒和 s 算同一种）才能拼。上下拼的根共用时间刻度，同一个数值上下对齐；',
            '左右接的根：后一个的 0 接在前一个的结尾，画板上用连续的时间，名字相同的层合成一条轨道；offset 是这一段在画板上的起点。',
            '左右接只能接单行的画板；多行的先 split 出要接的那个根。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'project_id': {'type': 'integer', 'description': '明确的项目编号'},
                                  'action': {'type': 'string',
                                             'description': 'show、merge、split、move 或 reset',
                                             'default': 'show',
                                             'enum': ['show', 'merge', 'split', 'move', 'reset']},
                                  'root': {'type': ['integer', 'null'], 'description': '要操作的根层编号（子层跟着它的根走）'},
                                  'target': {'type': ['integer', 'null'], 'description': 'merge 时拼到哪个根层旁边'},
                                  'side': {'type': 'string',
                                           'description': 'merge 时拼在 target 的上方、下方（above / below，同时），或前面、后面（left '
                                                          '/ right，接续）',
                                           'default': 'below'},
                                  'x': {'type': ['number', 'null'], 'description': 'move 时画板左上角在画布上的横坐标（像素）'},
                                  'y': {'type': ['number', 'null'], 'description': 'move 时画板左上角在画布上的纵坐标（像素）'}},
                   'additionalProperties': False,
                   'required': ['database', 'project_id']},
  'mcp': {'route': 'admin',
          'group': 'view',
          'database': 'path',
          'paths': [],
          'route_by': 'action',
          'action_routes': {'show': 'query',
                            'merge': 'admin',
                            'split': 'admin',
                            'move': 'admin',
                            'reset': 'admin'}},
  'cli_only': ['json']}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图画布上的画板排版", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int)
    p.add_argument("action", nargs="?", default="show", choices=("show", "merge", "split", "move", "reset"))
    p.add_argument("root", nargs="?", type=int)
    p.add_argument("--to", dest="target", type=int); p.add_argument("--side", choices=SIDES, default="below")
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

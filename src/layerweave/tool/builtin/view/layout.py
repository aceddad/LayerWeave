"""画布排版：每个根层连同它的子树是一块画板。画板里的根排成几行：
- 上下 = 同时：不同行共用一把尺子，同一个数值上下对齐。单位相同的根默认各占一行、拼在同一块画板里。
- 左右 = 接续：同一行里后一个根的 0 接在前一个根的结尾（比如第二章接在第一章后面），名字相同的层合成同一条轨道。只能手动接。
位置、尺寸和组合保存在项目库的视图工具表，写入有日志且可撤销。旧本机 layout.json 只读回退，首次编辑或 migrate 时迁入库，保留原文件。
网页与 AI 共用这份布局；普通读取不创建表，不把自动摆放写入数据库。

python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID                              查看画板
python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID merge 根 --to 另一个根 [--side above|below|left|right]
python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID split 根
python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID move 根 --x 0 --y 600
python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE PROJECT_ID reset
"""
import argparse
from contextlib import closing
import json
import math
from pathlib import Path
import sys
import threading

from .data import open_readonly, project_view
from .state import state_path
from layerweave.support.api import open_database, read_record, table_specs
from .layout_store import read_layout, write_layout, STYLE, MEMBER
from .layout_geometry import DEFAULTS, positions, resize as resize_board

LOCK = threading.Lock()
SIDES = ("above", "below", "left", "right")


def layout_path(database, root=None):
    return state_path(database, root).with_suffix(".layout.json")


def layout_serial(database, root=None):
    """Shared layout journal revision plus the optional legacy file revision."""
    path = layout_path(database, root)
    legacy = path.stat().st_mtime_ns if path.is_file() else 0
    with closing(open_readonly(database)) as connection:
        changes = [connection.execute("SELECT COALESCE(MAX(id), 0) FROM changes WHERE kind = ?", (kind,)).fetchone()[0]
                   for kind in (STYLE, MEMBER)]
    return f"{max(changes)}:{legacy}"


def _read_file(database, root):
    path = layout_path(database, root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"projects": {}}
    return data if isinstance(data, dict) and isinstance(data.get("projects"), dict) else {"projects": {}}


def _number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def _is_id(value):
    return isinstance(value, int) and not isinstance(value, bool)


def clean_boards(boards):
    """只留下认识的字段：rows（每行是左右接续的根层编号）、x / y（画布上的位置，None 表示自动排）、
    pps（每单位多少像素，None 表示默认）、styles（各根原有尺寸偏好）。旧格式 roots 按每根一行读入。"""
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
        rows = [row for row in rows if row]
        if not rows:
            continue
        pps = _number(board.get("pps"))
        value = {"rows": rows, "x": _number(board.get("x")), "y": _number(board.get("y")),
                 "pps": pps if pps and pps > 0 else None}
        if isinstance(board.get("styles"), dict):
            styles = {}
            for r in [r for row in rows for r in row]:
                if str(r) not in board["styles"]:
                    continue
                style = board["styles"].get(str(r), {})
                if not isinstance(style, dict):
                    continue
                ratio, lane = _number(style.get("pps")), _number(style.get("lane_height"))
                styles[str(r)] = {"pps": ratio if ratio and ratio > 0 else None,
                                  "lane_height": lane if lane and lane >= DEFAULTS["MIN_LANE"] else None}
            value["styles"] = styles
        out.append(value)
    return out


def board_roots(board):
    return [r for row in board["rows"] for r in row]


def reconcile(roots, boards):
    """让排版和数据库里现有的根对上：删掉已经不存在的根；单位不同的根不能待在同一块画板里；
    新出现的根作为新的一行并进同单位的第一块画板，没有就单独成一块。boards 为 None 时全部按单位自动分组。"""
    keys = {root["id"]: root["key"] for root in roots}
    cleaned = clean_boards(boards)
    preferences = {key: style for board in cleaned for key, style in board.get("styles", {}).items()}
    out, placed = [], set()
    for board in cleaned:
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
            new = {"rows": [[root["id"]]], "x": None, "y": None, "pps": None}
            if str(root["id"]) in preferences:
                style = preferences[str(root["id"])]
                new.update(pps=style["pps"], styles={str(root["id"]): style})
            out.append(new)
        else:
            home["rows"].append([root["id"]])
            if str(root["id"]) in preferences:
                home.setdefault("styles", {})[str(root["id"])] = preferences[str(root["id"])]
        placed.add(root["id"])
    return clean_boards(out)


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
    with closing(open_readonly(database)) as connection:
        saved = read_layout(connection, project_id, {r["id"] for r in roots})
    if saved is None:
        legacy = _read_file(database, root)["projects"].get(str(project_id))
        saved = legacy.get("boards") if isinstance(legacy, dict) else None
    return reconcile(roots, saved)


def save_layout(database, project_id, boards, root=None, *, with_result=False):
    with LOCK:
        boards = clean_boards(boards)
        with closing(open_database(database)) as connection:
            saved = {s["id"]: s for s in read_record(connection, STYLE, project_id=project_id)} if STYLE in table_specs(connection) else {}
            for board in boards:
                styles = board.setdefault("styles", {})
                for r in board_roots(board):
                    old = saved.get(r, {})
                    styles.setdefault(str(r), {"pps": old.get("pps", board.get("pps")), "lane_height": old.get("lane_height")})
                remember_styles(board)
            result = write_layout(connection, project_id, boards)
    return result if with_result else boards


def clear_layout(database, project_id, root=None):
    with closing(open_readonly(database)) as connection:
        view = project_view(connection, database, project_id)
    boards = reconcile(view["roots"], None)
    for b in boards:
        b["styles"] = {str(r): {"pps": None, "lane_height": None} for r in board_roots(b)}
    return save_layout(database, project_id, boards, root, with_result=True)


def remember_styles(board):
    styles = board.setdefault("styles", {})
    for r in board_roots(board):
        styles.setdefault(str(r), {"pps": board.get("pps"), "lane_height": None})
    if board["rows"]:
        styles[str(board["rows"][0][0])]["pps"] = board.get("pps")
    return board


def leader_style(board):
    if board["rows"]:
        board["pps"] = board.get("styles", {}).get(str(board["rows"][0][0]), {}).get("pps")


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
    remember_styles(home)
    remember_styles(moving)
    home["styles"].update(moving["styles"])
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
    leader_style(home)
    return boards


def split(boards, root_id):
    """把 root_id 从它的画板里拆出来，单独成一块；位置留空，由网页自动摆在其他画板下方。"""
    board = _board_of(boards, root_id)
    if len(board_roots(board)) == 1:
        raise ValueError(f"根层 {root_id} 已经单独占一块画板")
    remember_styles(board)
    style = board["styles"].pop(str(root_id))
    for row in board["rows"]:
        if root_id in row:
            row.remove(root_id)
    board["rows"] = [row for row in board["rows"] if row]
    leader_style(board)
    boards.insert(boards.index(board) + 1, {"rows": [[root_id]], "x": None, "y": None,
                                           "pps": style["pps"], "styles": {str(root_id): style}})
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


def arrange(database, project_id, action="show", *, root=None, target=None, side="below", x=None, y=None,
            width=None, height=None, pps=None, lane_height=None, gap=48, viewer="user", state_root=None):
    """查看几何边界，或在同一写入入口保存共享排版；show 不写库。"""
    with closing(open_readonly(database)) as connection:
        view = project_view(connection, database, project_id)
    if view is None:
        raise ValueError(f"项目 {project_id} 不存在")
    if viewer not in ("user", "ai"):
        raise ValueError("viewer 应为 user 或 ai")
    for name, value in (("x", x), ("y", y), ("width", width), ("height", height), ("pps", pps),
                        ("lane_height", lane_height), ("gap", gap)):
        if value is not None and _number(value) is None:
            raise ValueError(f"{name} 应为有限数值")
    roots = [r for r in view["roots"]]
    result = {}
    if action == "reset":
        result = clear_layout(database, project_id, state_root)
    boards = load_layout(database, project_id, roots, state_root)
    if action in ("merge", "split", "move", "resize", "place") and root is None:
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
    elif action == "resize":
        if all(v is None for v in (width, height, pps, lane_height)):
            raise ValueError("resize 至少提供 width、height、pps 或 lane_height 中的一项")
        resize_board(remember_styles(_board_of(boards, root)), view, width=width, height=height,
                     pps=pps, lane_height=lane_height, viewer=viewer)
    elif action == "place":
        if target is None or side not in SIDES:
            raise ValueError("place 需要 target 和 above/below/left/right")
        moving, home = _board_of(boards, root), _board_of(boards, target)
        if moving is home:
            raise ValueError("同一组合内的根请先拆开再放置")
        boxes = positions(view, boards, viewer=viewer)
        # Freeze the preview positions during an explicit placement. Otherwise
        # an automatic target would be re-positioned below the newly fixed board.
        for b, box in zip(boards, boxes):
            if box["automatic"] and box["visible"]:
                b["x"], b["y"] = box["x"], box["y"]
        me, other = boxes[boards.index(moving)], boxes[boards.index(home)]
        px = other["x"] + other["width"] + gap if side == "right" else other["x"] - me["width"] - gap if side == "left" else other["x"]
        py = other["y"] + other["height"] + gap if side == "below" else other["y"] - me["height"] - gap if side == "above" else other["y"]
        for _ in boards:
            hit = next((b for i, b in enumerate(boxes) if boards[i] is not moving and b["visible"] and
                        px < b["x"] + b["width"] and b["x"] < px + me["width"] and
                        py < b["y"] + b["height"] and b["y"] < py + me["height"]), None)
            if hit is None:
                break
            py = hit["y"] - me["height"] - max(0, gap) if side == "above" else hit["y"] + hit["height"] + max(0, gap)
        moving["x"], moving["y"] = px, py
    elif action not in ("show", "reset", "migrate"):
        raise ValueError(f"不认识的动作：{action}")
    if action in ("merge", "split", "move", "resize", "place", "migrate"):
        result = save_layout(database, project_id, boards, state_root, with_result=True)
        boards = result["boards"]
    info = {r["id"]: r for r in roots}
    extents = {r: tuple(info[r]["extent"]) for r in info}
    out = []
    for number, (board, box) in enumerate(zip(boards, positions(view, boards, viewer=viewer)), 1):
        rows = []
        for row in board["rows"]:
            offsets = chain_offsets(row, extents)
            rows.append([{"id": r, "name": info[r]["name"], "offset": offsets[r]} for r in row])
        out.append({"board": number, "roots": board_roots(board), "unit": info[board["rows"][0][0]]["unit"],
                    **{k: box[k] for k in ("x", "y", "width", "height", "automatic", "visible")},
                    "pps": box.get("pps"), "styles": board.get("styles", {}), "rows": rows})
    bounds = [f"画板 {b['board']} 边界：({b['x']:g}, {b['y']:g}) · {b['width']:g} × {b['height']:g}" +
              ("（自动位置预览）" if b["automatic"] else "") for b in out if b["visible"]]
    return {"boards": out, "text": "\n".join([describe(boards, roots), *bounds]), "viewer": viewer,
            **({"operation_id": result["operation_id"]} if result else {})}


COMMANDS = [{'name': 'view_layout',
  'summary': '查看或调整共享画板布局：位置、实际宽高、行高、合并拆分、邻接放置；保存到视图工具表',
  'entrypoint': 'layerweave.tool.builtin.view.layout:arrange',
  'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout',
  'read_only': False,
  'context': ['database', 'project_id'],
  'returns': 'boards（根编号、组合、世界坐标、宽高、尺寸偏好、automatic/visible）、text；写入另有 operation_id。',
  'examples': [{'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE 1',
                'arguments': {'action': 'show'}},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE 1 split 19'},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE 1 merge 19 --to 1 --side '
                       'above'},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE 1 merge 31 --to 1 --side '
                       'right'},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE 1 resize 4 --width 1800 '
                       '--lane-height 180',
                'arguments': {'action': 'resize', 'root': 4, 'width': 1800, 'lane_height': 180}},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE 1 place 7 --to 4 --side '
                       'right --gap 48',
                'arguments': {'action': 'place', 'root': 7, 'target': 4, 'side': 'right', 'gap': 48}},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.view.layout DATABASE 1 migrate',
                'arguments': {'action': 'migrate'}}],
  'notes': ['show 只读，宽高来自与前端一致的布局规则；自动坐标为预览，不写库。尺寸是画布世界坐标，不随镜头缩放改变。',
            '写入保存在项目库的视图工具表并记录日志，可撤销、复制。旧本机布局只读回退，migrate 或首次编辑时保存到库，原文件保留。',
            '上下合并时横向比例取最上方，左右接续取最左方；同轨道行高取最左侧来源。合并保留各根偏好，拆开恢复。',
            'resize 的 width/height 是整块画板目标大小；pps 是每轴单位像素，lane_height 是每条对象小行的高度。宽高只影响显示。',
            'place 放在 target 的 side 一侧并避让其他画板；move 采用明确坐标，允许有意叠放。默认 viewer=user，ai 按 AI 的折叠计算。',
            '组合仍要求单位相同，左右接续只能接单行画板。对象 begin/end 和轴单位不因布局改变。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'project_id': {'type': 'integer', 'description': '明确的项目编号'},
                                  'action': {'type': 'string',
                                             'description': 'show、merge、split、move、resize、place、reset、migrate',
                                             'default': 'show',
                                             'enum': ['show',
                                                      'merge',
                                                      'split',
                                                      'move',
                                                      'resize',
                                                      'place',
                                                      'reset',
                                                      'migrate']},
                                  'root': {'type': ['integer', 'null'], 'description': '要操作的根层编号（子层跟着它的根走）'},
                                  'target': {'type': ['integer', 'null'], 'description': 'merge/place 的目标根层编号'},
                                  'side': {'type': 'string',
                                           'description': 'merge/place 的方向：above、below、left、right',
                                           'default': 'below'},
                                  'x': {'type': ['number', 'null'], 'description': 'move 时画板左上角在画布上的横坐标（像素）'},
                                  'y': {'type': ['number', 'null'], 'description': 'move 时画板左上角在画布上的纵坐标（像素）'},
                                  'width': {'type': ['number', 'null'], 'description': 'resize：目标画板总宽度（含名字列）'},
                                  'height': {'type': ['number', 'null'], 'description': 'resize：目标画板总高度'},
                                  'pps': {'type': ['number', 'null'],
                                          'description': 'resize：每个轴单位的显示像素；与 width 二选一'},
                                  'lane_height': {'type': ['number', 'null'],
                                                  'description': 'resize：对象小行高度，至少 24；与 height 二选一'},
                                  'gap': {'type': 'number',
                                          'default': 48,
                                          'description': 'place 与相邻画板的间距（世界坐标像素）'},
                                  'viewer': {'type': 'string',
                                             'enum': ['user', 'ai'],
                                             'default': 'user',
                                             'description': '按谁的折叠状态计算显示边界'},
                                  'state_root': {'type': ['string', 'null'],
                                                 'description': '可选本机状态目录；用于读取旧布局与明确迁移，不决定共享布局保存位置'}},
                   'additionalProperties': False,
                   'required': ['database', 'project_id']},
  'mcp': {'route': 'edit',
          'group': 'view',
          'database': 'path',
          'paths': ['state_root'],
          'route_by': 'action',
          'action_routes': {'show': 'query',
                            'merge': 'edit',
                            'split': 'edit',
                            'move': 'edit',
                            'resize': 'edit',
                            'place': 'edit',
                            'reset': 'edit',
                            'migrate': 'edit'}},
  'cli_only': ['json']}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图画布上的画板排版", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int)
    p.add_argument("action", nargs="?", default="show", choices=("show", "merge", "split", "move", "resize", "place", "reset", "migrate"))
    p.add_argument("root", nargs="?", type=int)
    p.add_argument("--to", dest="target", type=int); p.add_argument("--side", choices=SIDES, default="below")
    p.add_argument("--x", type=float); p.add_argument("--y", type=float)
    p.add_argument("--width", type=float); p.add_argument("--height", type=float)
    p.add_argument("--pps", type=float); p.add_argument("--lane-height", type=float)
    p.add_argument("--gap", type=float, default=48)
    p.add_argument("--viewer", choices=("user", "ai"), default="user")
    p.add_argument("--state-root", type=Path)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    try:
        result = arrange(a.database, a.project_id, a.action, root=a.root, target=a.target, side=a.side, x=a.x, y=a.y,
                         width=a.width, height=a.height, pps=a.pps, lane_height=a.lane_height,
                         gap=a.gap, viewer=a.viewer, state_root=a.state_root)
    except (ValueError, OSError) as error:
        print(f"排版失败：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if a.json else result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

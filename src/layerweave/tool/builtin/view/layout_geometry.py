"""Deterministic board geometry for headless layout tools; parity-tested against the frontend model."""
from collections import defaultdict
import json
from pathlib import Path

DEFAULTS = json.loads(Path(__file__).with_name("layout-defaults.json").read_text(encoding="utf-8"))


def root_style(board, root):
    return board.get("styles", {}).get(str(root), {})


def geometry(view, board, *, viewer="user"):
    c = DEFAULTS
    roots = {r["id"]: r for r in view["roots"]}
    layers = view["layers"]
    by_id = {l["id"]: l for l in layers}
    own = {r["layer"] for r in view.get("folds", []) if r.get(viewer)}
    if all(by_id.get(r, {}).get("hidden") for row in board["rows"] for r in row):
        return {"width": 0, "height": 0, "visible": False, "tracks": [], "stretch_height": 0, "lanes": 0}
    begin, end = float("inf"), float("-inf")
    height, stretch, lane_total, sections, tracks_out = c["HEAD"] + c["RULER"], 0, 0, 0, []
    for row in board["rows"]:
        segments, finish = [], None
        for root in row:
            a, e = roots[root]["extent"]
            offset = 0 if finish is None else finish - min(0, a)
            finish = offset + e
            begin, end = min(begin, a + offset), max(end, e + offset)
            segments.append((root, offset))
        tracks, children, top = {}, defaultdict(list), []
        for root, offset in segments:
            paths, seen = {}, defaultdict(int)
            for layer in layers:
                if layer["root"] != root:
                    continue
                key, parent = "", None
                if layer["id"] != root:
                    parent = paths.get(layer["father"], "")
                    base = f"{parent}/{layer['name'] or layer['type']}"
                    seen[base] += 1
                    key = f"{base}#{seen[base]}" if seen[base] > 1 else base
                paths[layer["id"]] = key
                if key not in tracks:
                    tracks[key] = {"parent": parent, "parts": []}
                    (top if parent is None else children[parent]).append(key)
                tracks[key]["parts"].append((layer, root, offset))
        ordered = []
        def walk(key):
            ordered.append(key)
            for child in children[key]:
                walk(child)
        for key in top:
            walk(key)
        if "" not in tracks:
            for key in children[""]:
                walk(key)
        hidden, visible = set(), []
        for key in ordered:
            track = tracks[key]
            if track["parent"] in hidden:
                hidden.add(key)
                continue
            if all(p[0].get("hidden") for p in track["parts"]):
                continue
            folded = any(p[0]["id"] in own for p in track["parts"])
            if folded:
                hidden.add(key)
                visible.append({"layers": [p[0]["id"] for p in track["parts"]], "height": c["FOLD"],
                                "folded": True, "lanes": 0, "lane_height": 0})
                continue
            items = sorted([(o["begin"] + offset, o["end"] + offset, o["id"])
                            for layer, _, offset in track["parts"] for o in layer["objects"]])
            ends = []
            for b, e, _ in items:
                e = max(b, e)
                slot = next((i for i, x in enumerate(ends) if x <= b + 1e-9 and not (e == b and x == b)), None)
                if slot is None:
                    ends.append(e)
                else:
                    ends[slot] = e
            count = max(1, len(ends))
            h = root_style(board, track["parts"][0][1]).get("lane_height") or c["LANE"]
            h = max(c["MIN_LANE"], h)
            visible.append({"layers": [p[0]["id"] for p in track["parts"]],
                            "height": count * h + 2 * c["PAD"], "folded": False,
                            "lanes": count, "lane_height": h})
            stretch += count * h
            lane_total += count
        if visible:
            height += (2 if sections else 0) + (c["STRIP"] if len(row) > 1 else 0) + sum(t["height"] for t in visible)
            sections += 1
            tracks_out.extend(visible)
    if begin == float("inf"):
        begin, end = 0, 10
    if end <= begin:
        end = begin + 10
    pps = board.get("pps") or c["AUTO_TRACK_WIDTH"] / max(1e-6, end - begin)
    return {"width": c["NAMES"] + (end - begin) * pps + 42, "height": height + 2 if sections else 0,
            "visible": bool(sections), "begin": begin, "end": end, "pps": pps,
            "tracks": tracks_out, "stretch_height": stretch, "lanes": lane_total}


def positions(view, boards, *, viewer="user"):
    """Same initial placement as placeAuto; computed positions do not write a database."""
    sizes = [geometry(view, b, viewer=viewer) for b in boards]
    fixed = [(b, s) for b, s in zip(boards, sizes) if b["x"] is not None and b["y"] is not None and s["height"]]
    x = min((b["x"] for b, _ in fixed), default=0)
    y = max((b["y"] + s["height"] for b, s in fixed), default=-DEFAULTS["GAP"]) + DEFAULTS["GAP"]
    result = []
    for b, s in zip(boards, sizes):
        automatic = b["x"] is None or b["y"] is None
        bx, by = (x, y) if automatic else (b["x"], b["y"])
        result.append({**s, "x": bx, "y": by, "automatic": automatic})
        if automatic and s["height"]:
            y += s["height"] + DEFAULTS["GAP"]
    return result


def resize(board, view, *, width=None, height=None, pps=None, lane_height=None, viewer="user"):
    """Update preferences; data positions/durations remain untouched."""
    c = DEFAULTS
    before = geometry(view, board, viewer=viewer)
    if not before["visible"]:
        raise ValueError("隐藏的画板没有可调整的显示尺寸")
    if width is not None:
        if width <= c["NAMES"] + 42:
            raise ValueError("width 必须大于名字列及边距（242）")
        if pps is not None:
            raise ValueError("width 和 pps 只需提供一个")
        pps = (width - c["NAMES"] - 42) / (before["end"] - before["begin"])
    if height is not None and lane_height is not None:
        raise ValueError("height 和 lane_height 只需提供一个")
    styles = board.setdefault("styles", {})
    roots = [r for row in board["rows"] for r in row]
    for r in roots:
        styles.setdefault(str(r), {"pps": board.get("pps") if r == roots[0] else None, "lane_height": None})
    if pps is not None:
        if pps <= 0:
            raise ValueError("pps 必须大于零")
        board["pps"] = pps
        styles[str(roots[0])]["pps"] = pps
    if lane_height is not None:
        if lane_height < c["MIN_LANE"]:
            raise ValueError(f"lane_height 不能小于 {c['MIN_LANE']}")
        for s in styles.values():
            s["lane_height"] = lane_height
    elif height is not None:
        fixed = before["height"] - before["stretch_height"]
        minimum = fixed + before["lanes"] * c["MIN_LANE"]
        if not before["stretch_height"] or height < minimum:
            raise ValueError(f"height 不能小于当前轨道需要的 {minimum:g}")
        available = height - fixed
        low, high = 0, max(1, available / before["stretch_height"])
        for _ in range(40):
            middle = (low + high) / 2
            total = sum(t["lanes"] * max(c["MIN_LANE"], t["lane_height"] * middle)
                        for t in before["tracks"] if not t["folded"])
            if total < available:
                low = middle
            else:
                high = middle
        factor = (low + high) / 2
        for s in styles.values():
            s["lane_height"] = max(c["MIN_LANE"], (s.get("lane_height") or c["LANE"]) * factor)
    return board

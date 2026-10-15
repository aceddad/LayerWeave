"""按时刻读：某个根的某一刻（或一段时间）上，每层是什么、这些东西之间怎么连着、有哪些待处理的批注指着它们。
截图是给眼睛看的，这个给推理用（对口型、对字幕、查衔接）。和"沿读"（walk.py）是一对：一个沿着关联读，一个沿着时间读，每个对象的写法共用。

- 每层一行，按层的树顺序。这一刻有东西就写出来；没有就写是哪种空（两个对象之间空着、还没开始、已经结束），和网页"此刻"面板一样。
- 不给根和时间时，读用户此刻在视图里看的地方：圈出了一段就读那一段，否则读播放头那一刻（view_state 的 selection、playhead_at）。
- 时间用这个根自己的单位；左右接续的画板上，按每一段自己的时间。

python -m layerweave.tool.builtin.view.at DATABASE PROJECT_ID                       用户正在看的地方
python -m layerweave.tool.builtin.view.at DATABASE PROJECT_ID --root 1 --at 12.5     根层 1 的第 12.5
python -m layerweave.tool.builtin.view.at DATABASE PROJECT_ID --root 1 --range 10 15
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

from layerweave.support.api import read_bindings, read_record, read_snapshot

from .data import open_readonly, order_layers
from .note import list_notes
from .notes import LAYER_REF as NOTE_LAYER_REF, OBJECT_REF as NOTE_OBJECT_REF
from .state import read_state
from .walk import LINE_LIMIT, Layers, facts, label, num, object_step


def _gap(objects, a, b, unit):
    """这一刻（或这一段）没有对象时，是哪种空。"""
    u = f" {unit}" if unit else ""
    timed = sorted(objects, key=lambda o: (o["begin"], o["end"]))
    before = [o for o in timed if o["end"] <= a]
    after = [o for o in timed if o["begin"] >= b]
    if before and after:
        start, stop = max(o["end"] for o in before), min(o["begin"] for o in after)
        return {"kind": "between", "from": start, "to": stop, "text": f"空着：{num(start)}–{num(stop)}{u}（{num(stop - start)}{u}）"}
    if after:
        first = min(o["begin"] for o in after)
        return {"kind": "before", "next": first, "text": f"还没开始：{num(first)}{u} 才有"}
    last = max(o["end"] for o in before)
    return {"kind": "after", "last": last, "text": f"已经结束：最后一个在 {num(last)}{u} 结束"}


def moment(connection, project_id, root, a, b, layers=None):
    """根 root 上 [a, b] 这一段（a == b 是一刻）：每层的对象或空当、它们之间的关联、指着它们的待处理批注。"""
    layers = layers or Layers(connection, project_id)
    top = layers.rows.get(root)
    if top is None or layers.root.get(root) != root:
        raise ValueError(f"#{root} 不是这个项目里的根层")
    if b < a:
        a, b = b, a
    axis = top["axis"] if isinstance(top["axis"], dict) else {}
    eps = max(float(axis.get("precision") or 0), 1e-9) / 2
    unit = layers.unit(root)
    rows, hits = [], {}
    tree = [l for l in order_layers(list(layers.rows.values())) if layers.root.get(l["id"]) == root and l["config_ref"] != NOTE_LAYER_REF]
    for layer in tree:
        objects = read_record(connection, "object", project_id=project_id, filters={"layer": layer["id"]})
        timed = [o for o in objects if isinstance(o["begin"], (int, float)) and isinstance(o["end"], (int, float))]

        def inside(o):
            if o["end"] <= o["begin"]:                       # 瞬间：落在这一刻（段）上
                return a - eps <= o["begin"] <= b + eps
            return o["begin"] <= a < o["end"] if a == b else o["begin"] < b and o["end"] > a

        here = sorted((o for o in timed if inside(o)), key=lambda o: (o["begin"], o["end"], o["id"]))
        steps = [object_step(o, layers, project_id, connection) for o in here]
        for step in steps:
            hits[step["id"]] = step
        rows.append({"layer": {"id": layer["id"], "name": layer["name"], "type": layer["type"], "depth": layer["depth"]},
                     "objects": steps, "gap": None if steps or not timed else _gap(timed, a, b, unit)})
    # 这些东西之间的关联；连到这一刻以外的，只数个数（用 view_walk 接着读）
    relations, outside = [], {}
    for number in hits:
        for bind in read_bindings(connection, "object", project_id, number, direction="both"):
            source = (bind["source_kind"], bind["source_project_id"], bind["source_id"])
            target = (bind["target_kind"], bind["target_project_id"], bind["target_id"])
            other = target if source == ("object", project_id, number) else source
            if other[0] == "object" and other[1] == project_id and other[2] in hits:
                if source[2] == number:                           # 两头都在：从发出的那头记一次
                    relations.append({"source": source[2], "target": target[2], "tips": bind["tips"] or ""})
                continue
            if other[0] == "object" and other[1] == project_id:  # 批注另外列，不算在"这里没有的东西"里
                row = read_record(connection, "object", project_id=project_id, id=other[2])
                if row is not None and row["config_ref"] == NOTE_OBJECT_REF:
                    continue
            outside[number] = outside.get(number, 0) + 1
    # 指着这一刻的待处理批注：指着这些对象的；指着这些层、没圈时间或圈的时间和这一段重叠的
    layer_ids = {r["layer"]["id"] for r in rows}
    notes = []
    for n in list_notes(connection, project_id, status="open"):
        if n["reply_to"] is not None:
            continue
        span = n["span"] if isinstance(n["span"], dict) else None
        aimed = [t for t in n["targets"] if t["project"] == project_id and (
            (t["kind"] == "object" and t["id"] in hits) or (t["kind"] == "layer" and t["id"] in layer_ids and (
                span is None or (span["begin"] <= b + eps and span["end"] >= a - eps))))]
        if aimed:
            notes.append({"id": n["id"], "author": n["author"], "text": n["text"], "span": span,
                          "targets": [f"{t['kind']}:{t['id']}" for t in aimed]})
    noted = {t for n in notes for t in n["targets"]}
    for step in hits.values():
        step["outside"] = outside.get(step["id"], 0)
        step["noted"] = f"object:{step['id']}" in noted
    return {"root": root, "name": top["name"], "unit": unit, "begin": a, "end": b, "layers": rows,
            "relations": relations, "notes": notes}


def where_user_is(database, project_id, state_root=None):
    """视图里用户此刻在看的地方：圈出的一段，否则播放头（左右接续时每一段各一刻）。"""
    state = read_state(database, state_root)
    if not state or state.get("project") != project_id:
        raise ValueError("没给 --root，视图里也没有这个项目的播放头：用户可能还没打开这个项目，或者还没点过画板")
    if isinstance(state.get("selection"), dict):
        s = state["selection"]
        return [(s["root"], s["begin"], s["end"])]
    if state.get("playhead_at"):
        return [(p["root"], p["local"], p["local"]) for p in state["playhead_at"]]
    raise ValueError("视图里没有播放头：请用户在画板上点一下，或者用 --root 和 --at 指定")


def read_at(database, project_id, *, root=None, at=None, range=None, state_root=None):
    if root is None:
        if at is not None or range is not None:
            raise ValueError("给了时间，也要用 --root 说是哪个根")
        spans = where_user_is(database, project_id, state_root)
    elif at is not None:
        spans = [(root, float(at), float(at))]
    elif range is not None:
        spans = [(root, float(range[0]), float(range[1]))]
    else:
        raise ValueError("给了 --root，还要 --at 某一刻或 --range 一段")
    with closing(open_readonly(database)) as connection, read_snapshot(connection):
        layers = Layers(connection, project_id)
        moments = [moment(connection, project_id, r, a, b, layers) for r, a, b in spans]
    return {"moments": moments, "from_view": root is None, "text": "\n\n".join(describe(m) for m in moments)}


def read_spans(connection, project_id, spans):
    """网页"复制文字版"用：spans 是 [(根, 起点, 终点)]，和 read_at 一样的结果。"""
    with read_snapshot(connection):
        layers = Layers(connection, project_id)
        moments = [moment(connection, project_id, r, a, b, layers) for r, a, b in spans]
    return {"moments": moments, "from_view": False, "text": "\n\n".join(describe(m) for m in moments)}


def describe(m):
    u = f" {m['unit']}" if m["unit"] else ""
    when = f"在 {num(m['begin'])}{u} 这一刻" if m["begin"] == m["end"] else f"在 {num(m['begin'])}–{num(m['end'])}{u} 这一段"
    lines = [f"根层 #{m['root']}「{m['name']}」{when}："]
    for row in m["layers"]:
        layer, pad = row["layer"], "  " * (1 + (row["layer"]["depth"] or 0))
        head = f"{pad}{layer['name'] or '层'}（{layer['type']}，#{layer['id']}）"
        if not row["objects"]:
            if row["gap"]:
                lines.append(f"{head}  {row['gap']['text']}")
            continue
        lines.append(head)
        for step in row["objects"]:
            more = []
            if step["noted"]:
                more.append("有待处理的批注")
            if step["outside"]:
                more.append(f"还连着 {step['outside']} 个这里没有的东西（view_walk object:{step['id']}）")
            shown = [f for f in facts(step) if not f.startswith("层「")]                      # 层名已经在上一行
            lines.append(f"{pad}  " + " · ".join([label(step)] + shown + more))
            if step["text"]:
                text = " ".join(step["text"].split())
                lines.append(f"{pad}    " + (text if len(text) <= LINE_LIMIT else text[:LINE_LIMIT] + f"…（共 {len(text)} 字）"))
    if m["relations"]:
        lines.append("这些东西之间的关联：")
        lines += [f"  #{r['source']} → #{r['target']}" + (f"（{r['tips']}）" if r["tips"] else "") for r in m["relations"]]
    if m["notes"]:
        lines.append("指着这里的待处理批注：")
        for n in m["notes"]:
            text = " ".join(n["text"].split())
            lines.append(f"  批注 #{n['id']}（{n['author'] or '没署名'}，指着 {'、'.join(n['targets'])}）：{text[:LINE_LIMIT]}")
    return "\n".join(lines)


COMMANDS = [{
    "name": "view_at",
    "summary": "按时刻读：某个根的某一刻（或一段）上每层是什么、彼此怎么连着、有哪些待处理批注；不给参数就读用户此刻在视图里看的地方",
    "entrypoint": "layerweave.tool.builtin.view.at:read_at",
    "cli": "python -m layerweave.tool.builtin.view.at",
    "read_only": True,
    "context": ["database", "project_id"],
    "parameters": {
        "root": {"type": "integer", "description": "根层编号；不给时读视图里用户圈出的一段或播放头那一刻"},
        "at": {"type": "number", "description": "某一刻，用这个根自己的单位"},
        "range": {"type": "array", "description": "一段 [起点, 终点]，用这个根自己的单位"},
    },
    "returns": "moments（每个：root、name、unit、begin、end、layers[{layer, objects, gap}]、relations、notes）、from_view、text。",
    "examples": [{"cli": "python -m layerweave.tool.builtin.view.at DATABASE 1"},
                 {"cli": "python -m layerweave.tool.builtin.view.at DATABASE 1 --root 1 --at 12.5"},
                 {"cli": "python -m layerweave.tool.builtin.view.at DATABASE 1 --root 1 --range 10 15"}],
    "notes": ["用户说\"这里\"\"这一刻\"\"这段\"时，不给参数直接读：圈出了一段读那一段，否则读播放头；左右接续的画板上每一段各读一刻。",
              "每个对象的写法和 view_walk 一样；连到这一刻以外的东西只数个数，要看就用 view_walk。",
              "截图是给眼睛看的，这个给推理用；两个一起用最稳。"],
}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="按时刻读", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int)
    p.add_argument("--root", type=int); p.add_argument("--at", type=float)
    p.add_argument("--range", type=float, nargs=2, metavar=("起点", "终点"))
    p.add_argument("--json", action="store_true", help="输出 JSON")
    a = p.parse_args()
    try:
        result = read_at(a.database, a.project_id, root=a.root, at=a.at, range=a.range)
    except (ValueError, OSError) as error:
        print(f"没有读成：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if a.json else result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

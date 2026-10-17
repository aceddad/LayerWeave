"""沿着关联读：从一个对象或层出发，顺着关联（bind）一步步往外走，把每一步是什么按顺序读出来（A → B → C）。
批注指着对象、回复指着批注，也都是关联：从一条批注出发，读得到它指的东西和整楼回复；从一个对象出发，读得到挂在它上面的批注、和它连着的对象。

- 只走标准关联（bind）；同一个东西只列一次，遇到环不再往回走。
- 步数和数量有上限。到了上限会写明：最后一步的东西还连着几条关联没走、有几个因为数量上限没列出。
- 别的项目里的东西只列出来，不接着走。
- 核心的 walk_relations（usage/query）做的是同一件事；这里不引用它，因为视图是可以单独装卸的工具包，只用 support 的读取接口。

python -m layerweave.tool.builtin.view.walk DATABASE PROJECT_ID object:16                  两个方向走 3 步
python -m layerweave.tool.builtin.view.walk DATABASE PROJECT_ID layer:5 --depth 2 --direction out
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

from layerweave.support.api import read_bindings, read_record, read_snapshot

from .i18n import translate
from .data import open_readonly, order_layers
from .notes import LAYER_REF as NOTE_LAYER_REF, OBJECT_REF as NOTE_OBJECT_REF

DIRECTIONS = {"both": "both", "out": "outgoing", "in": "incoming"}
DIRECTION_TEXT = {"both": "两个方向", "out": "顺着关联的方向（它指着谁）", "in": "逆着关联的方向（谁指着它）"}
TEXT_LIMIT = 2000       # 返回里每一步的文字最多这么长
LINE_LIMIT = 300        # 文字版里每一步的文字最多这么长


def parse_start(text, project_id):
    """object:16、layer:5，或带项目的 object:2:16。"""
    parts = str(text).split(":")
    if len(parts) not in (2, 3) or parts[0] not in ("object", "layer") or not all(p.isdigit() for p in parts[1:]):
        raise ValueError(f"起点写成 object:编号、layer:编号，或 object:项目:编号；收到 {text!r}")
    return parts[0], int(parts[1]) if len(parts) == 3 else project_id, int(parts[-1])


def num(value):
    return f"{value:.3f}".rstrip("0").rstrip(".") if isinstance(value, (int, float)) else "?"


def _ref(kind, owner, number, project_id):
    return f"{kind}:{number}" if owner == project_id else f"{kind}:{owner}:{number}"


class Layers:
    """项目里的层：名字、类型、所在的根和根的单位（写位置时用）。"""

    def __init__(self, connection, project_id):
        rows = read_record(connection, "layer", project_id=project_id)
        self.rows = {row["id"]: row for row in rows}
        self.root = {}
        for layer in order_layers(rows):
            if layer["depth"] is not None:
                self.root[layer["id"]] = layer["id"] if layer["depth"] == 0 else self.root.get(layer["father"])

    def unit(self, layer_id):
        root = self.rows.get(self.root.get(layer_id))
        axis = root["axis"] if root and isinstance(root["axis"], dict) else {}
        unit = axis.get("unit")
        return unit if isinstance(unit, str) else ""


def _step(kind, owner, number, depth, project_id, layers, connection):
    step = {"ref": _ref(kind, owner, number, project_id), "kind": kind, "project": owner, "id": number, "depth": depth,
            "status": "found", "name": "", "type": "", "layer": None, "root": None, "unit": "", "begin": None, "end": None,
            "text": None, "source": None, "note": None, "via": []}
    if owner != project_id:
        step["status"] = "other_project"
        return step
    row = layers.rows.get(number) if kind == "layer" else read_record(connection, "object", project_id=owner, id=number)
    if row is None:
        step["status"] = "missing"
        return step
    if kind == "layer":
        step.update(name=row["name"], type="note" if row["config_ref"] == NOTE_LAYER_REF else row["type"],
                    root=layers.root.get(number), unit=layers.unit(number))
        return step
    return object_step(row, layers, project_id, connection, depth)


def object_step(row, layers, project_id, connection, depth=0):
    """一个对象怎么写：名字、类型、所在层、位置（按根的单位）、文字或文件；批注另记署名、状态、是不是回复。按时刻读（at.py）也用它。"""
    owner, number = project_id, row["id"]
    step = {"ref": _ref("object", owner, number, project_id), "kind": "object", "project": owner, "id": number, "depth": depth,
            "status": "found", "name": "", "type": "", "layer": None, "root": None, "unit": "", "begin": None, "end": None,
            "text": None, "source": None, "note": None, "via": []}
    info = row["information"] if isinstance(row["information"], dict) else {}
    layer = layers.rows.get(row["layer"])
    text = info.get("text") if isinstance(info.get("text"), str) else None
    step.update(name=row["name"], type=row["config_ref"].rsplit("/", 1)[-1].removesuffix(".toml"),
                layer={"id": row["layer"], "name": layer["name"] if layer else "", "type": layer["type"] if layer else ""},
                root=layers.root.get(row["layer"]), unit=layers.unit(row["layer"]), begin=row["begin"], end=row["end"],
                text=text if text is None or len(text) <= TEXT_LIMIT else text[:TEXT_LIMIT] + "…",
                source=info.get("source") if isinstance(info.get("source"), str) else None)
    if row["config_ref"] == NOTE_OBJECT_REF:
        span = info.get("span") if isinstance(info.get("span"), dict) else None
        # 指着另一条批注的是回复：整楼的状态记在楼主上，回复自己的不算
        reply = any(b["target_kind"] == "object" and b["target_project_id"] == owner
                    and (r := read_record(connection, "object", project_id=owner, id=b["target_id"])) is not None
                    and r["config_ref"] == NOTE_OBJECT_REF for b in read_bindings(connection, "object", owner, number, direction="outgoing"))
        step["note"] = {"author": info.get("author") or "", "reply": reply, "span": span,
                        "status": None if reply else "done" if info.get("status") == "done" else "open"}
    return step


def walk_from(connection, project_id, start, *, direction="both", depth=3, max_nodes=60):
    """广度优先：先列第 1 步能到的，再列第 2 步……每一步写明是从哪一个、顺着哪条关联到的（via）。"""
    if direction not in DIRECTIONS:
        raise ValueError(f"方向写 both、out 或 in；收到 {direction!r}")
    if type(depth) is not int or not 0 <= depth <= 10:
        raise ValueError("步数要在 0 到 10 之间")
    if type(max_nodes) is not int or max_nodes < 1:
        raise ValueError("数量上限至少是 1")
    kind, owner, number = parse_start(start, project_id)
    with read_snapshot(connection):
        layers = Layers(connection, project_id)
        first = _step(kind, owner, number, 0, project_id, layers, connection)
        if first["status"] != "found":
            raise ValueError(f"起点 {start} {'在别的项目里' if first['status'] == 'other_project' else '不存在'}")
        nodes = {(kind, owner, number): first}
        order, queue, edges, used, skipped, beyond = [first], [(kind, owner, number)], {}, set(), 0, 0
        while queue:
            current = queue.pop(0)
            here = nodes[current]
            if here["status"] != "found":
                continue
            for bind in read_bindings(connection, *current, direction=DIRECTIONS[direction]):
                source = (bind["source_kind"], bind["source_project_id"], bind["source_id"])
                target = (bind["target_kind"], bind["target_project_id"], bind["target_id"])
                other = target if source == current else source
                if other[0] not in ("layer", "object"):
                    continue
                if here["depth"] >= depth:                      # 最后一步：不再往外走，只数还有几条没走
                    if other not in nodes:
                        beyond += 1
                    continue
                if bind["id"] in edges:
                    continue
                if other not in nodes:
                    if len(nodes) >= max_nodes:
                        skipped += 1
                        continue
                    nodes[other] = _step(*other, here["depth"] + 1, project_id, layers, connection)
                    order.append(nodes[other])
                    queue.append(other)
                edges[bind["id"]] = {"id": bind["id"], "source": _ref(*source, project_id), "target": _ref(*target, project_id),
                                     "tips": bind["tips"] or ""}
                there = nodes[other]
                if there["depth"] == here["depth"] + 1:          # 第一次走到它的那一步：记下怎么来的
                    there["via"].append({"bind": bind["id"], "other": here["ref"], "arrow": "from" if source == current else "to",
                                         "tips": bind["tips"] or ""})
                    used.add(bind["id"])
    result = {"start": first["ref"], "direction": direction, "depth": depth, "max_nodes": max_nodes, "steps": order,
              "edges": list(edges.values()), "loops": len(edges) - len(used), "beyond": beyond, "skipped": skipped}
    result["text"] = describe(result)
    return result


def label(step, *, lang="zh"):
    def tr(key, **values):
        return translate(key, values, lang=lang)
    number = f"#{step['id']}"
    kind = tr("common.layer" if step["kind"] == "layer" else "common.object")
    if step["status"] == "other_project":
        return tr("walk.otherProject", project=step["project"], kind=kind, id=step["id"])
    if step["status"] == "missing":
        return tr("walk.missing", kind=kind, id=step["id"])
    if step["kind"] == "layer":
        return tr("walk.layer", id=number, name=step["name"])
    if step["note"]:
        return tr("walk.note", id=number)
    name = step["name"] or (Path(step["source"]).name if step["source"] else "")
    return f"{number}「{name}」" if name else number


def facts(step, *, include_layer=True, lang="zh"):
    def tr(key, **values):
        return translate(key, values, lang=lang)
    if step["status"] != "found":
        return []
    if step["kind"] == "layer":
        return [step["type"]] + ([tr("walk.unit", unit=step["unit"])] if step["unit"] else [])
    facts = []
    if step["note"]:
        note = step["note"]
        facts += [note["author"] or tr("notes.anonymous"), tr("notes.reply" if note["reply"] else "notes.resolved" if note["status"] == "done" else "notes.open")]
        if note.get("span"):
            facts.append(tr("walk.span", begin=num(note["span"].get("begin")), end=num(note["span"].get("end"))))
    else:
        facts.append(step["type"])
        if include_layer and step["layer"]:
            facts.append(tr("walk.parent", name=step["layer"]["name"]))
        facts.append(f"{num(step['begin'])}–{num(step['end'])}{' ' + step['unit'] if step['unit'] else ''}")
        if step["source"]:
            facts.append(tr("walk.file", source=step["source"]))
    return facts


def _via(via):
    tips = f"（关联说明：{via['tips']}）" if via["tips"] else ""
    other = f"#{via['other'].split(':')[-1]}"
    return (f"← {other} 指着它" if via["arrow"] == "from" else f"→ 它指着 {other}") + tips


def describe(result):
    steps = result["steps"]
    lines = [f"从 {label(steps[0])} 出发，{DIRECTION_TEXT[result['direction']]}走 {result['depth']} 步：列出 {len(steps)} 个"
             + (f"；另有 {result['loops']} 条关联连在已经列出的东西之间（成环，没有重复列）" if result["loops"] else "") + "。"]
    for depth in range(result["depth"] + 1):
        here = [s for s in steps if s["depth"] == depth]
        if not here:
            break
        lines.append(f"第 {depth} 步")
        for step in here:
            lines.append("  " + " · ".join([label(step)] + facts(step)))
            if step["text"]:
                text = " ".join(step["text"].split())
                lines.append("    " + (text if len(text) <= LINE_LIMIT else text[:LINE_LIMIT] + f"…（共 {len(text)} 字，--json 看全文）"))
            for via in step["via"]:
                lines.append("    " + _via(via))
    if result["beyond"]:
        lines.append(f"第 {result['depth']} 步的东西还连着 {result['beyond']} 条关联没走（--depth 调大可以接着走）。")
    if result["skipped"]:
        lines.append(f"到了数量上限 {result['max_nodes']} 个，还有 {result['skipped']} 个没列出（--max 调大）。")
    return "\n".join(lines)


def read_along(database, project_id, start, *, direction="both", depth=3, max_nodes=60):
    with closing(open_readonly(database)) as connection:
        return walk_from(connection, project_id, start, direction=direction, depth=depth, max_nodes=max_nodes)


COMMANDS = [{'name': 'view_walk',
  'summary': '沿着关联读：从一个对象或层出发，顺着关联一步步往外走，按顺序读出每一步是什么（名字、所在层、位置、文字或文件、怎么连过来的）',
  'entrypoint': 'layerweave.tool.builtin.view.walk:read_along',
  'cli': 'python -m layerweave.tool.builtin.view.walk',
  'read_only': True,
  'context': ['database', 'project_id'],
  'returns': 'steps（按步数排好：ref、depth、名字、层、位置、文字、文件、批注的署名和状态、via 怎么连过来的）、edges、loops、beyond、skipped、text。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.view.walk DATABASE 1 object:16',
                'arguments': {'start': 'object:16'}},
               {'cli': 'python -m layerweave.tool.builtin.view.walk DATABASE 1 object:1306 --direction out '
                       '--depth 2'}],
  'notes': ['批注指着对象、回复指着批注都是关联：从批注出发读得到它指的东西和整楼；从对象出发读得到挂在上面的批注。',
            '同一个东西只列一次；beyond 是最后一步还连着、没走的关联数，skipped 是因为数量上限没列出的个数。',
            '网页上楼主卡片和对象详情里的「沿读」用的是同一份结果，侧栏「沿读」里按步列出，点一步镜头就过去。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'project_id': {'type': 'integer', 'description': '明确的项目编号'},
                                  'start': {'type': 'string', 'description': '起点：object:16、layer:5'},
                                  'direction': {'type': 'string',
                                                'default': 'both',
                                                'description': 'both 两个方向；out 只顺着关联的方向（它指着谁）；in 只逆着走（谁指着它）',
                                                'enum': ['both', 'out', 'in']},
                                  'depth': {'type': 'integer', 'default': 3, 'description': '走几步，0 只读起点'},
                                  'max_nodes': {'type': 'integer', 'default': 60, 'description': '最多列出几个（含起点）'}},
                   'additionalProperties': False,
                   'required': ['database', 'project_id', 'start']},
  'mcp': {'route': 'query', 'group': 'view', 'database': 'path', 'paths': []},
  'cli_only': ['json']}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="沿着关联读", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int)
    p.add_argument("start", help="起点：object:16、layer:5")
    p.add_argument("--direction", choices=tuple(DIRECTIONS), default="both")
    p.add_argument("--depth", type=int, default=3); p.add_argument("--max", type=int, default=60, dest="max_nodes")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    a = p.parse_args()
    try:
        result = read_along(a.database, a.project_id, a.start, direction=a.direction, depth=a.depth, max_nodes=a.max_nodes)
    except (ValueError, OSError) as error:
        print(f"没有读成：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if a.json else result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

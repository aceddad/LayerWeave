"""Shared view layout: per-root preferences and normalized membership, copied through logical references."""
from layerweave.support.api import read_record, register_tables, run_operation, table_specs

STYLE = "view_layout"
MEMBER = "view_layout_member"
TABLES = {
    STYLE: {
        "id_source": "provided",
        "fields": {name: {"type": "REAL", "nullable": True} for name in ("x", "y", "pps", "lane_height")},
        "logical_references": [{"fields": ["project_id", "id"], "kind": "layer"}],
    },
    MEMBER: {
        "id_source": "provided",
        "fields": {name: {"type": "INTEGER", "nullable": False} for name in
                   ("anchor_id", "board_index", "row_index", "column_index")},
        "logical_references": [
            {"fields": ["project_id", "id"], "kind": "layer"},
            {"fields": ["project_id", "anchor_id"], "kind": "layer"},
        ],
    },
}


def read_layout(connection, project_id, root_ids):
    specs = table_specs(connection)
    styles = read_record(connection, STYLE, project_id=project_id) if STYLE in specs else []
    members = read_record(connection, MEMBER, project_id=project_id) if MEMBER in specs else []
    if not styles and not members:
        return None
    styles = {s["id"]: s for s in styles if s["id"] in root_ids}
    groups = {}
    for member in members:
        if member["id"] in root_ids:
            groups.setdefault(member["anchor_id"], []).append(member)
    boards, assigned = [], set()
    for _, group in sorted(groups.items(), key=lambda pair: (min(m["board_index"] for m in pair[1]), pair[0])):
        rows = {}
        for m in sorted(group, key=lambda m: (m["row_index"], m["column_index"], m["id"])):
            rows.setdefault(m["row_index"], []).append(m["id"])
            assigned.add(m["id"])
        rows = list(rows.values())
        leader = styles.get(rows[0][0], {})
        preferences = {str(r): {k: styles[r].get(k) for k in ("pps", "lane_height")}
                       for row in rows for r in row if r in styles}
        boards.append({"rows": rows, "x": leader.get("x"), "y": leader.get("y"),
                       "pps": leader.get("pps"), "styles": preferences})
    # A partial copy can omit membership whose anchor was outside the selection.
    # Its own position/preferences still survive and form an independent board.
    for r, style in styles.items():
        if r not in assigned:
            boards.append({"rows": [[r]], "x": style["x"], "y": style["y"], "pps": style["pps"],
                           "styles": {str(r): {k: style[k] for k in ("pps", "lane_height")}}})
    return boards


def write_layout(connection, project_id, boards):
    register_tables(connection, TABLES)

    def work(write):
        existing = {kind: {r["id"]: r for r in write.read(kind, project_id=project_id)} for kind in TABLES}
        desired = {kind: {} for kind in TABLES}
        changed = 0
        for order, board in enumerate(boards):
            anchor = board["rows"][0][0]
            for ri, row in enumerate(board["rows"]):
                for ci, root in enumerate(row):
                    previous = existing[STYLE].get(root, {})
                    prefs = board.get("styles", {}).get(str(root), {})
                    desired[STYLE][root] = {
                        "x": board["x"] if root == anchor else previous.get("x"),
                        "y": board["y"] if root == anchor else previous.get("y"),
                        "pps": board["pps"] if root == anchor else prefs.get("pps"),
                        "lane_height": prefs.get("lane_height"),
                    }
                    desired[MEMBER][root] = {"anchor_id": anchor, "board_index": order,
                                             "row_index": ri, "column_index": ci}
        for kind in TABLES:
            for root, values in desired[kind].items():
                if root not in existing[kind]:
                    write.create(kind, {"id": root, **values}, project_id=project_id)
                    changed += 1
                elif any(existing[kind][root][k] != v for k, v in values.items()):
                    write.update(kind, root, values, project_id=project_id)
                    changed += 1
            # Keep settings attached to deleted/non-root layers, like fold state.
            # Reads ignore them; restoring the original layer can recover its layout.
        return {"boards": boards, "changed": changed}

    result = run_operation(connection, work)
    if not result["ok"]:
        raise ValueError(result.get("error", {}).get("message") or "无法保存视图布局")
    changed = result["data"]["changed"]
    return {"boards": boards, "operation_id": result["operation_id"] if changed else None,
            "changed": changed, "recorded": True}

"""视图的快照与日志投影：页内只使用日志值，不混入较晚的业务记录。"""
from layerweave.support.api import change_cursor, read_changes, read_snapshot
from layerweave.support.feedback import InputError

from .data import bind_view, object_views, project_view
from .notes.reads import parse_reads


def project_snapshot(connection, database, project_id):
    """完整画面（含工具表）与游标来自同一个读取快照。"""
    with read_snapshot(connection):
        data = project_view(connection, database, project_id)
        cursor = change_cursor(connection)
    return {"mode": "snapshot", "data": data, "next_cursor": cursor, "has_more": False}


def _belongs(kind, record, project_id):
    if record is None:
        return False
    if kind == "bind":
        return project_id in (record["source_project_id"], record["target_project_id"])
    return record.get("id" if kind == "project" else "project_id") == project_id


def project_delta(connection, database, project_id, *, after, limit=100):
    """完整操作页；复杂层结构变化回退快照，普通对象/关联/视图状态逐条投影。"""
    with read_snapshot(connection):
        try:
            page = read_changes(connection, after=after, limit=limit)
        except InputError as error:
            if error.details.get("code") not in {"cursor_ahead", "cursor_inside_operation"}:
                raise
            return project_snapshot(connection, database, project_id)
        selected = [row for row in page["changes"] if row["kind"] in {"project", "layer", "object", "bind", "view_layer", "view_note"}
                    and any(_belongs(row["kind"], row[field], project_id) for field in ("before_data", "after_data"))]
        # 层的名称也参与轨道合并；结构变化先取准确快照，不猜局部重排范围。
        if any(row["kind"] == "layer" or (row["kind"] == "project" and
               (row["before_data"] is None or row["after_data"] is None)) for row in selected):
            return project_snapshot(connection, database, project_id)
        objects = [row["after_data"] for row in selected if row["kind"] == "object" and row["after_data"] is not None]
        projected = iter(object_views(database, project_id, objects))
        changes = []
        for row in selected:
            kind, before, current = row["kind"], row["before_data"], row["after_data"]
            event = {"kind": kind, "id": row["target_id"], "operation_id": row["operation_id"],
                     "change_id": row["id"], "undo_of": row["undo_of"], "after": None}
            if kind == "object":
                event.update(before_layer=before["layer"] if before else None,
                             after_layer=current["layer"] if current else None,
                             after=next(projected) if current else None)
            elif kind == "bind":
                event["after"] = bind_view(current) if _belongs(kind, current, project_id) else None
            elif kind == "project":
                event["after"] = {k: current[k] for k in ("id", "name", "tips")}
            elif kind == "view_layer" and current:
                event["after"] = {"layer": current["id"], "user": current["user_fold"], "user_tips": current["user_tips"],
                                  "ai": current["ai_fold"], "ai_tips": current["ai_tips"]} if current["user_fold"] or current["ai_fold"] else None
            elif kind == "view_note" and current:
                event["after"] = parse_reads(current["reads"]) or None
            changes.append(event)
        # 即使没有相关记录也推进全库游标，不从过滤后的事件重新计算页尾。
        return {"mode": "delta", "changes": changes, "next_cursor": page["next_cursor"], "has_more": page["has_more"]}

"""保存一次目标记录的前后值；调用方管理事务。"""

from datetime import datetime, timezone
import json

from ..values import same_value


def json_text(value):
    """输出标准 JSON，保留中文和扩展内容。"""
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def append_change(connection, operation_id, kind, before, after, *, undo_of=None):
    """只记录实际发生的变化，返回供检测通道使用的变更描述。"""
    if same_value(before, after):
        return None
    record = after if after is not None else before
    if kind == "project":
        project_id = record["id"]
    elif kind == "bind":
        project_id = record["source_project_id"]
    else:
        project_id = record["project_id"]
    action = "create" if before is None else "delete" if after is None else "update"
    cursor = connection.execute(
        "INSERT INTO changes (operation_id, created_at, kind, project_id, target_id, "
        "action, before_data, after_data, undo_of) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (operation_id, datetime.now(timezone.utc).isoformat(), kind, project_id,
         record["id"], action,
         None if before is None else json_text(before),
         None if after is None else json_text(after), undo_of),
    )
    return {
        "change_id": cursor.lastrowid,
        "operation_id": operation_id,
        "action": action,
        "kind": kind,
        "project_id": project_id,
        "id": record["id"],
        "before": before,
        "after": after,
    }

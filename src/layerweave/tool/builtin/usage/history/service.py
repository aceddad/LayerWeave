"""按操作查看历史与字段差异；查询已删除实体也不依赖实体仍存在。"""

from layerweave.support.storage.log_reader import content, operation_rows, operation_page
from layerweave.support.feedback import InputError, target
from layerweave.support.values import same_value
from layerweave.support.api import read_snapshot
from layerweave.support.storage.tables import historical_specs


def differences(before, after, path=()):
    """字典递归到内容字段，列表整体比较；明确区分未提供、null 和不同数值类型。"""
    if same_value(before, after):
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(before.keys() | after.keys()):
            if key in before and key in after:
                result.extend(differences(before[key], after[key], (*path, key)))
            else:
                result.append({"path": [*path, key], "before_present": key in before, "after_present": key in after,
                               "before": before.get(key), "after": after.get(key)})
        return result
    return [{"path": list(path), "before_present": before is not None if not path else True,
             "after_present": after is not None if not path else True, "before": before, "after": after}]


def _project_ids(row):
    if row["kind"] == "bind":
        return {value[key] for value in (row["before_data"], row["after_data"]) if value is not None
                for key in ("source_project_id", "target_project_id")}
    return {row["project_id"]} if row["project_id"] is not None else set()


def _operation(rows, *, detail=False, matched_count=None, connection=None):
    changes = []
    for row in rows:
        before, after, kind = row["before_data"], row["after_data"], row["kind"]
        item = {"change_id": row["id"], "action": row["action"],
                "target": target(kind, row["project_id"], row["target_id"]),
                "name": (after or before).get("name", "")}
        if row.get("undo_of") is not None:
            item["undo_of"] = row["undo_of"]
        if row["action"] == "update":
            item["fields"] = differences(content(kind, before, connection), content(kind, after, connection))
        if detail:
            item.update(before=before, after=after)
        changes.append(item)
    origins = {row.get("undo_of") for row in rows}
    undo_of = next(iter(origins)) if len(origins) == 1 else None
    mixed = {"undo_of_operations": sorted(origin for origin in origins if origin is not None)} if len(origins) > 1 else {}
    return {"operation_id": rows[0]["operation_id"], "undo_of": undo_of, **mixed,
            "started_at": rows[0]["created_at"], "ended_at": rows[-1]["created_at"],
            "project_ids": sorted(set().union(*(_project_ids(row) for row in rows))),
            "change_count": len(rows), "matched_change_count": len(rows) if matched_count is None else matched_count,
            "changes": changes}


def read_history(connection, project_id=None, *, kind=None, id=None, operation_id=None,
                 limit=20, before=None, detail=False):
    """过滤用于选操作；每项仍展示该操作完整批次，跨项目不截断。before 是日志游标。"""
    with read_snapshot(connection):
        if operation_id is not None:
            if project_id is not None or kind is not None or id is not None or before is not None:
                raise ValueError("按 operation_id 展开完整操作时不再提供项目、实体或分页范围")
            rows = operation_rows(connection, operation_id)
            return {"scope": {"operation_id": operation_id}, "operation_count": int(bool(rows)),
                    "change_count": len(rows), "items": [_operation(rows, detail=True, connection=connection)] if rows else [], "next_cursor": None}
        if type(limit) is not int or limit < 1:
            raise ValueError("limit 应为正整数")
        if before is not None and (type(before) is not int or before < 1):
            raise ValueError("before 应为上一页返回的正整数游标")
        specs = historical_specs(connection)
        if kind is not None and (kind not in specs or kind == "change"):
            raise InputError(f"未知历史目标：{kind}", field="kind", allowed=[name for name in specs if name != "change"])
        if id is not None and kind is None:
            raise ValueError("指定实体 id 时需要同时提供 kind")
        if id is not None and specs[kind]["scoped"] and project_id is None:
            raise ValueError("按项目管理的记录历史需要 project_id")
        counts, page = operation_page(connection, project_id, kind=kind, id=id, limit=limit, before=before)
        items = [_operation(operation_rows(connection, row["operation_id"]), detail=detail, matched_count=row["matched"], connection=connection)
                 for row in page[:limit]]
        return {"scope": {"project_id": project_id, "kind": kind, "id": id},
                "operation_count": counts[0], "change_count": counts[1], "items": items,
                "next_cursor": page[limit - 1]["cursor"] if len(page) > limit else None}

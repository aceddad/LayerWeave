"""按操作原子恢复历史快照；冲突比较与恢复在同一写事务中完成。"""

from copy import deepcopy
from functools import partial

from . import crud
from .history import content, operation_rows
from .journal import append_change, json_text
from ..configuration.loader import DEFAULT_ROOT
from ..feedback import InputError, target
from ..operation import DEFAULT_CHECKER, run_operation
from ..values import same_value


def _key(kind, row):
    return kind, row.get("project_id") if kind in {"layer", "object"} else None, row["id"]


def _target(key):
    return target(*key)


def _read(connection, key):
    kind, project_id, id = key
    return crud.read(connection, kind, project_id=project_id, id=id)


def _plan(connection, rows):
    plan = {}
    for row in rows:
        kind, first, last = row["kind"], row["before_data"], row["after_data"]
        key = _key(kind, last or first)
        if key not in plan:
            plan[key] = {"restore": first, "lifecycle": False}
        plan[key]["expected"] = last
        plan[key]["lifecycle"] |= row["action"] != "update"
    conflicts = []
    for key, item in plan.items():
        before, expected = content(key[0], item["restore"]), content(key[0], item["expected"])
        if same_value(before, expected):
            item["skip"] = True
            continue
        item["current"] = _read(connection, key)
        current = content(key[0], item["current"])
        if not item["lifecycle"] and before is not None and expected is not None:
            changed = [name for name in sorted(before.keys() | expected.keys())
                       if (name in before) != (name in expected) or not same_value(before.get(name), expected.get(name))]
            item["fields"] = changed
            mismatched = [name for name in changed if current is None or
                          (name in current) != (name in expected) or not same_value(current.get(name), expected.get(name))]
            if current is not None:
                desired = deepcopy(item["current"])
                for name in changed:
                    if name in before:
                        desired[name] = deepcopy(before[name])
                    else:
                        desired.pop(name, None)
                item["restore"] = desired
        else:
            mismatched = [name for name in sorted((expected or {}).keys() | (current or {}).keys())
                          if (name in (expected or {})) != (name in (current or {}))
                          or not same_value((expected or {}).get(name), (current or {}).get(name))]
        if mismatched:
            fields = [{"path": [name], "before_present": name in (expected or {}),
                       "after_present": name in (current or {}), "before": (expected or {}).get(name),
                       "after": (current or {}).get(name)} for name in mismatched]
            conflicts.append({"code": "undo_conflict", "target": _target(key),
                              "message": "原操作修改的顶层字段已有后续变化" if "fields" in item else "创建或删除涉及的整条记录已有后续变化",
                              "expected": item["expected"], "current": item["current"], "restore": item["restore"],
                              "comparison": "fields" if "fields" in item else "record", "fields": fields})
    if conflicts:
        raise InputError("存在撤销冲突，本批未写入", code="undo_conflict", conflicts=conflicts)
    # 操作中的中间变化已抵消时，没有需要回退的最终效果。
    return {key: item for key, item in plan.items()
            if not item.get("skip")}


def _dependencies(connection, plan):
    """只检查恢复会改变的真实引用，不替当前配置执行语义检查。"""
    conflicts = []
    def final(key):
        return plan[key]["restore"] if key in plan else _read(connection, key)

    def missing(owner, field, ref):
        conflicts.append({"code": "undo_dependency", "target": _target(owner), "field": field,
                          "message": "恢复需要的项目或层不存在于本批最终状态", "related": [_target(ref)]})

    for key, item in plan.items():
        kind, project_id, id = key
        restored = item["restore"]
        if restored is not None and kind in {"layer", "object"}:
            parent = ("project", None, project_id)
            if final(parent) is None:
                missing(key, "project_id", parent)
            field = "father" if kind == "layer" else "layer"
            if restored[field] is not None:
                parent = ("layer", project_id, restored[field])
                if final(parent) is None:
                    missing(key, field, parent)
            other = ("object" if kind == "layer" else "layer", project_id, id)
            if item["current"] is None and final(other) is not None:
                conflicts.append({"code": "undo_id_conflict", "target": _target(key),
                                  "message": "原编号已被同项目的另一种实体占用", "related": [_target(other)]})
        if restored is not None or kind not in {"project", "layer"}:
            continue
        owner_project = id if kind == "project" else project_id
        for dependent, field in (("layer", "father"), ("object", "layer")):
            filters = None if kind == "project" else {field: id}
            for row in crud.read(connection, dependent, project_id=owner_project, filters=filters):
                child_key = _key(dependent, row)
                child = final(child_key)
                if child is not None and (kind == "project" or child[field] == id):
                    conflicts.append({"code": "undo_dependency", "target": _target(key),
                                      "message": "仍有本批不会移走或删除的记录引用此目标", "related": [_target(child_key)]})
    if conflicts:
        raise InputError("存在引用或编号冲突，本批未写入", code="undo_conflict", conflicts=conflicts)


def _project_high_water(connection, id, *records):
    values = [row.get("max_id", 0) for row in records if row is not None]
    query = ("SELECT MAX(n) FROM (SELECT MAX(id) n FROM layers WHERE project_id=? UNION ALL "
             "SELECT MAX(id) FROM objects WHERE project_id=? UNION ALL "
             "SELECT MAX(target_id) FROM changes WHERE project_id=? AND kind IN ('layer','object') UNION ALL "
             "SELECT MAX(json_extract(before_data,'$.max_id')) FROM changes WHERE kind='project' AND target_id=? UNION ALL "
             "SELECT MAX(json_extract(after_data,'$.max_id')) FROM changes WHERE kind='project' AND target_id=?)")
    values.append(connection.execute(query, (id,) * 5).fetchone()[0] or 0)
    return max(values, default=0)


def _restore(connection, key, item, operation_id, undo_of):
    """私有恢复入口：原编号、原始坐标和内容，不重发号或按当前轴归一。"""
    kind, project_id, id = key
    current, desired = item["current"], deepcopy(item["restore"])
    spec = crud.SPECS[kind]
    where, identity = crud._where(spec, project_id, id, None)
    if desired is None:
        connection.execute(f'DELETE FROM "{spec["table"]}"{where}', identity)
    else:
        if kind == "project":
            desired["max_id"] = _project_high_water(connection, id, current, desired)
        columns = ["id", *spec["fields"], *(("project_id",) if spec["scoped"] else ())]
        if kind == "project":
            columns.append("max_id")
        values = {name: json_text(desired[name]) if name in spec["json"] and not (name == "axis" and desired[name] is None)
                  else desired[name] for name in columns}
        if current is None:
            names = ", ".join(f'"{name}"' for name in columns)
            connection.execute(f'INSERT INTO "{spec["table"]}" ({names}) VALUES ({", ".join("?" for _ in columns)})', list(values.values()))
        else:
            writable = [name for name in columns if name not in {"id", "project_id"}
                        and ("fields" not in item or name in item["fields"])]
            if kind == "project" and "max_id" not in writable and desired["max_id"] != current["max_id"]:
                writable.append("max_id")
            assignments = ", ".join(f'"{name}"=?' for name in writable)
            connection.execute(f'UPDATE "{spec["table"]}" SET {assignments}{where}', [*[values[name] for name in writable], *identity])
        if spec["scoped"]:
            connection.execute("UPDATE projects SET max_id=MAX(max_id, ?) WHERE id=?", (id, project_id))
    after = _read(connection, key)
    return append_change(connection, operation_id, kind, current, after, undo_of=undo_of)


def undo_operation(connection, operation_id, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """撤销整个 operation_id，不提供强制覆盖或部分撤销；重复调用仍作冲突比较。"""
    def work(new_operation_id):
        rows = operation_rows(connection, operation_id)
        if not rows:
            raise InputError(f"未找到有改动日志的操作：{operation_id}", code="operation_not_found", field="operation_id")
        plan = _plan(connection, rows)
        _dependencies(connection, plan)
        # 按最终状态恢复，外键在同一事务提交时检查，允许整批恢复父子或既有环。
        connection.execute("PRAGMA defer_foreign_keys = ON")
        keys = sorted(plan, key=lambda key: 0 if key[0] == "project" and plan[key]["restore"] is not None else 2 if key[0] == "project" else 1)
        changes = []
        for key in keys:
            try:
                change = _restore(connection, key, plan[key], new_operation_id, operation_id)
            except Exception as error:
                error.details = {"target": _target(key), **getattr(error, "details", {})}
                raise
            if change is not None:
                changes.append(change)
        return {"undone_operation_id": operation_id, "restored_records": len(changes)}, changes

    if checker is DEFAULT_CHECKER:
        from ..validation.runner import check_changes
        checker = partial(check_changes, config_root=config_root)
    return {**run_operation(connection, work, checker=checker), "undo_of": operation_id}

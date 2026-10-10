"""按操作原子恢复历史快照；冲突比较与恢复在同一写事务中完成。"""

from copy import deepcopy
from layerweave.core.identity import identity_key

from layerweave.support import records as crud
from layerweave.support.storage.log_reader import content, operation_rows
from layerweave.support.configuration.loader import DEFAULT_ROOT
from layerweave.support.feedback import InputError, target
from layerweave.support.operation import run_operation
from layerweave.support.providers import DEFAULT_CHECKER, optional_checker
from layerweave.support.values import same_value


def _key(kind, row):
    return identity_key(kind, row.get("project_id"), row["id"])


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


def undo_operation(connection, operation_id, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """撤销整个 operation_id，不提供强制覆盖或部分撤销；重复调用仍作冲突比较。"""
    def work(write):
        new_operation_id = write.operation_id
        rows = operation_rows(connection, operation_id)
        if not rows:
            raise InputError(f"未找到有改动日志的操作：{operation_id}", code="operation_not_found", field="operation_id")
        plan = _plan(connection, rows)
        _dependencies(connection, plan)
        # 按最终状态恢复，外键在同一事务提交时检查，允许整批恢复父子；成环仍由写入入口拒绝。
        crud.defer_references(connection)
        keys = sorted(plan, key=lambda key: 0 if key[0] == "project" and plan[key]["restore"] is not None else 2 if key[0] == "project" else 1)
        changes = []
        for key in keys:
            try:
                change = crud.restore(connection, key[0], key[2], plan[key]["restore"], project_id=key[1],
                                      operation_id=new_operation_id, undo_of=operation_id, fields=plan[key].get("fields"))[1]
            except Exception as error:
                error.details = {"target": _target(key), **getattr(error, "details", {})}
                raise
            if change is not None:
                changes.append(change)
        return {"undone_operation_id": operation_id, "restored_records": len(changes)}

    checker = optional_checker(checker, config_root=config_root)
    return {**run_operation(connection, work, checker=checker), "undo_of": operation_id}

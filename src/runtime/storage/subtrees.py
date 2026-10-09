"""子树批量操作：写事务内读取范围，复用 CRUD 发号、日志和提交后检查。"""

from collections import defaultdict
from copy import deepcopy
from functools import partial

from . import crud
from .details import read_project_details
from ..configuration.loader import DEFAULT_ROOT
from ..feedback import InputError, target
from ..operation import DEFAULT_CHECKER, run_operation
from ..positions import PositionMath


def _source(connection, project_id, layer_id):
    if layer_id is None:
        raise InputError("子树操作需要明确的起始层编号", field="layer_id", code="target")
    data = read_project_details(connection, project_id, layer_id=layer_id)
    if data is None:
        raise InputError(f"起始层不存在：layer ({project_id}, {layer_id})", code="target_not_found",
                         field="layer_id", target=target("layer", project_id, layer_id))
    layers = data["layers"]
    objects = [obj for layer in layers for obj in layer["objects"]]
    bindings = [bind for entity in [*layers, *objects] for bind in entity["bind"]]
    return data["project"]["id"], data["scope"]["layer_id"], layers, objects, bindings


def _ordered_layers(layers, root_id):
    """父层在前，迭代遍历避免深树递归；已有父链环也只访问一次。"""
    children = defaultdict(list)
    by_id = {layer["id"]: layer for layer in layers}
    for layer in layers:
        children[layer["father"]].append(layer["id"])
    pending, visited, ordered = [root_id], set(), []
    while pending:
        id = pending.pop()
        if id in visited:
            continue
        visited.add(id)
        ordered.append(by_id[id])
        pending.extend(reversed(children[id]))
    return ordered


def _checker(checker, config_root):
    if checker is DEFAULT_CHECKER:
        from ..validation.runner import check_changes
        return partial(check_changes, config_root=config_root)
    return checker


def _payload(kind, row):
    return {key: deepcopy(row[key]) for key in crud.SPECS[kind]["fields"]}


def delete_subtree(connection, project_id, layer_id, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """删除整棵子树及其出向关联；外部入向关联保留并由提交后检查诊断。"""
    def work(operation_id):
        owner_id, root_id, layers, objects, bindings = _source(connection, project_id, layer_id)
        ordered = _ordered_layers(layers, root_id)
        # 正常树按子层在前删除；既有环在事务最终状态统一验证外键。
        connection.execute("PRAGMA defer_foreign_keys = ON")
        changes = []
        for kind, rows in (("bind", bindings), ("object", objects), ("layer", reversed(ordered))):
            for row in rows:
                _, change = crud.delete(connection, kind, row["id"], operation_id=operation_id,
                                        project_id=owner_id if kind != "bind" else None)
                if change is not None:
                    changes.append(change)
        return {"project_id": owner_id, "layer_id": root_id,
                "counts": {"layers": len(layers), "objects": len(objects), "binds": len(bindings)}}, changes

    return {**run_operation(connection, work, checker=_checker(checker, config_root)), "tool": "delete_subtree"}


def copy_subtree(connection, project_id, layer_id, *, name=None, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """在同项目、同父层复制子树，重映射明确的结构引用，保持自由内容与外部引用。"""
    def work(operation_id):
        owner_id, root_id, layers, objects, bindings = _source(connection, project_id, layer_id)
        ordered = _ordered_layers(layers, root_id)
        mapping = {kind: {} for kind in ("layer", "object", "bind")}
        changes, created_layers = [], {}

        def create(kind, old, data, **extra):
            row, change = crud.create(connection, kind, data, operation_id=operation_id,
                                      project_id=owner_id if kind != "bind" else None, **extra)
            mapping[kind][old["id"]] = row["id"]
            changes.append(change)
            return row

        for old in ordered:
            data = _payload("layer", old)
            data["father"] = mapping["layer"].get(old["father"], old["father"])
            if old["id"] == root_id and name is not None:
                data["name"] = name
            created_layers[old["id"]] = create("layer", old, data)
        # 正常树的父层已先创建；已有父链环的内部引用在所有新编号可用后补齐。
        for old in ordered:
            father = mapping["layer"].get(old["father"], old["father"])
            row = created_layers[old["id"]]
            if row["father"] != father:
                _, change = crud.update(connection, "layer", row["id"], {"father": father},
                                        project_id=owner_id, operation_id=operation_id)
                changes.append(change)
        positions = PositionMath(partial(crud.read, connection), owner_id)
        for old in objects:
            data = _payload("object", old)
            data["layer"] = mapping["layer"][old["layer"]]
            create("object", old, data, position_math=positions)
        for old in bindings:
            data = _payload("bind", old)
            data["source_id"] = mapping[old["source_kind"]][old["source_id"]]
            if old["target_project_id"] == owner_id and old["target_kind"] in {"layer", "object"}:
                data["target_id"] = mapping.get(old["target_kind"], {}).get(old["target_id"], old["target_id"])
            create("bind", old, data)
        return {"project_id": owner_id, "source_layer_id": root_id, "layer_id": mapping["layer"][root_id],
                "counts": {"layers": len(layers), "objects": len(objects), "binds": len(bindings)},
                "id_map": {kind: [{"old_id": old, "new_id": new} for old, new in ids.items()]
                           for kind, ids in mapping.items()}}, changes

    return {**run_operation(connection, work, checker=_checker(checker, config_root)), "tool": "copy_subtree"}

"""子树批量操作：写事务内读取范围，复用 CRUD 发号、日志和提交后检查。"""

from collections import defaultdict
from copy import deepcopy
from functools import partial

from layerweave.support import records as crud
from layerweave.support.storage.details import read_project_details
from layerweave.support.configuration.loader import DEFAULT_ROOT
from layerweave.support.feedback import InputError, target
from layerweave.support.operation import run_operation
from layerweave.support.providers import DEFAULT_CHECKER, optional_checker
from layerweave.support.positions import PositionMath


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
    if not layers:
        return []
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
    checker = optional_checker(checker, config_root=config_root)
    return checker


def _payload(kind, row):
    return {key: deepcopy(row[key]) for key in crud.writable_fields(kind)}


def _delete_records(connection, source, operation_id):
    owner_id, root_id, layers, objects, bindings = source
    ordered = _ordered_layers(layers, root_id)
    crud.defer_references(connection)
    for kind, rows in (("bind", bindings), ("object", objects), ("layer", reversed(ordered))):
        for row in rows:
            crud.delete(connection, kind, row["id"], operation_id=operation_id,
                                    project_id=owner_id if kind != "bind" else None)


def _counts(source):
    return {"layers": len(source[2]), "objects": len(source[3]), "binds": len(source[4])}


def _mapping_result(mapping):
    return {kind: [{"old_id": old, "new_id": new} for old, new in ids.items()] for kind, ids in mapping.items()}


def _copy_records(connection, source, destination, operation_id, *, name=None, cross_project=False, target_layer_id=None):
    owner, root, layers, objects, bindings = source
    ordered = _ordered_layers(layers, root)
    mapping = {kind: {} for kind in ("layer", "object", "bind")}
    created_layers = {}

    def create(kind, old, data, **extra):
        if kind == "object" and cross_project:
            row, _ = crud.create_exact(connection, kind, data,
                                       operation_id=operation_id, project_id=destination)
        else:
            row, _ = crud.create(connection, kind, data, operation_id=operation_id,
                                      project_id=destination if kind != "bind" else None, **extra)
        mapping[kind][old["id"]] = row["id"]
        return row

    def parent(old):
        if cross_project and old["id"] == root:
            return None  # 目标根层不继续引用源项目的父层，也不补造继承的轴。
        return mapping["layer"].get(old["father"], None if cross_project else old["father"])

    for old in ordered:
        data = _payload("layer", old)
        data["father"] = parent(old)
        if old["id"] == root and name is not None:
            data["name"] = name
        created_layers[old["id"]] = create("layer", old, data)
    for old in ordered:
        father, row = parent(old), created_layers[old["id"]]
        if row["father"] != father:
            crud.update(connection, "layer", row["id"], {"father": father},
                                    project_id=destination, operation_id=operation_id)
    positions = PositionMath(partial(crud.read, connection), destination)
    for old in objects:
        data = _payload("object", old)
        data["layer"] = target_layer_id if target_layer_id is not None else mapping["layer"][old["layer"]]
        create("object", old, data, position_math=positions)
    for old in bindings:
        data = _payload("bind", old)
        data.update(source_project_id=destination, source_id=mapping[old["source_kind"]][old["source_id"]])
        if old["target_project_id"] == owner and old["target_kind"] in {"layer", "object"}:
            id = mapping[old["target_kind"]].get(old["target_id"])
            if id is not None:
                data.update(target_project_id=destination, target_id=id)
        create("bind", old, data)
    return mapping


def delete_subtree(connection, project_id, layer_id, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """删除子树及出向关联；外部入向关联保留，由提交后检查诊断。"""
    def work(write):
        operation_id = write.operation_id
        source = _source(connection, project_id, layer_id)
        _delete_records(connection, source, operation_id)
        return {"project_id": source[0], "layer_id": source[1], "counts": _counts(source)}
    return {**run_operation(connection, work, checker=_checker(checker, config_root)), "tool": "delete_subtree"}


def copy_subtree(connection, project_id, layer_id, *, name=None, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """同项目、同父层复制子树，保留原有普通写入刻度规则。"""
    def work(write):
        operation_id = write.operation_id
        source = _source(connection, project_id, layer_id)
        mapping = _copy_records(connection, source, source[0], operation_id, name=name)
        return {"project_id": source[0], "source_layer_id": source[1], "layer_id": mapping["layer"][source[1]],
                "counts": _counts(source), "id_map": _mapping_result(mapping)}
    return {**run_operation(connection, work, checker=_checker(checker, config_root)), "tool": "copy_subtree"}


def transfer_subtree(connection, project_id, layer_id, target_project_id, *, mode="copy", name=None,
                     config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """同库跨项目复制或剪切；剪切的外部入向引用跟随新身份，整个过程可撤销。"""
    def work(write):
        operation_id = write.operation_id
        if mode not in {"copy", "cut"}:
            raise InputError("迁移模式应为 copy 或 cut", field="mode", allowed=["copy", "cut"])
        source = _source(connection, project_id, layer_id)
        destination = crud.read(connection, "project", id=target_project_id) if target_project_id is not None else None
        if destination is None:
            raise InputError("目标项目不存在", code="missing_reference", field="target_project_id",
                             target=target("project", None, target_project_id))
        destination = destination["id"]
        if destination == source[0]:
            raise InputError("跨项目操作需要不同的目标项目；同项目复制使用 copy_subtree", field="target_project_id")
        mapping, incoming = _transfer_records(connection, source, destination, operation_id, mode=mode, name=name)
        return {"mode": mode, "source_project_id": source[0], "project_id": destination,
                "source_layer_id": source[1], "layer_id": mapping["layer"][source[1]],
                "counts": _counts(source), "id_map": _mapping_result(mapping),
                "redirected_bind_ids": list(incoming)}
    return {**run_operation(connection, work, checker=_checker(checker, config_root)), "tool": "transfer_subtree"}


def _transfer_records(connection, source, destination, operation_id, *, mode, name=None, target_layer_id=None):
    """子树和对象选择共用的迁移、入向改指与删除；由外层管理单次事务。"""
    from layerweave.support.storage.queries import read_bindings
    incoming = {}
    if mode == "cut":
        owned = {row["id"] for row in source[4]}
        for kind, rows in (("layer", source[2]), ("object", source[3])):
            for row in rows:
                for bind in read_bindings(connection, kind, source[0], row["id"], direction="incoming"):
                    if bind["id"] not in owned:
                        incoming[bind["id"]] = bind
    mapping = _copy_records(connection, source, destination, operation_id, name=name,
                                     cross_project=True, target_layer_id=target_layer_id)
    for bind in incoming.values():
        crud.update(connection, "bind", bind["id"], {
            "target_project_id": destination, "target_id": mapping[bind["target_kind"]][bind["target_id"]]},
            operation_id=operation_id)
    if mode == "cut":
        _delete_records(connection, source, operation_id)
    return mapping, incoming


def transfer_objects(connection, project_id, object_ids, target_project_id, target_layer_id, *, mode="copy",
                     config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """同库跨项目复制/剪切选中对象及出向关联，放入明确的已有目标层。"""
    from layerweave.support.storage.assembly import read_object

    def work(write):
        operation_id = write.operation_id
        if mode not in {"copy", "cut"}:
            raise InputError("迁移模式应为 copy 或 cut", field="mode", allowed=["copy", "cut"])
        projects = []
        for field, id in (("project_id", project_id), ("target_project_id", target_project_id)):
            row = crud.read(connection, "project", id=id) if id is not None else None
            if row is None:
                raise InputError(f"项目 {id} 不存在", code="missing_reference", field=field,
                                 target=target("project", None, id))
            projects.append(row["id"])
        owner, destination = projects
        if owner == destination:
            raise InputError("跨项目操作需要不同的目标项目；同项目复制使用 copy_object，换层使用 update",
                             field="target_project_id")
        layer = crud.read(connection, "layer", project_id=destination, id=target_layer_id) if target_layer_id is not None else None
        if layer is None:
            raise InputError(f"目标层 ({destination}, {target_layer_id}) 不存在", code="missing_reference",
                             field="target_layer_id", target=target("layer", destination, target_layer_id))
        if object_ids is None or isinstance(object_ids, (str, bytes)):
            raise InputError("object_ids 需要编号列表，单个对象也使用 [id]", field="object_ids")
        objects = {}
        for id in dict.fromkeys(object_ids):
            obj = read_object(connection, owner, id) if id is not None else None
            if obj is None:
                raise InputError(f"对象 ({owner}, {id}) 不存在", code="target_not_found", field="object_ids",
                                 target=target("object", owner, id))
            objects.setdefault(obj["id"], obj)
        source = (owner, None, [], list(objects.values()), [bind for obj in objects.values() for bind in obj["bind"]])
        mapping, incoming = _transfer_records(connection, source, destination, operation_id,
                                                       mode=mode, target_layer_id=layer["id"])
        return {"mode": mode, "source_project_id": owner, "source_object_ids": list(objects), "project_id": destination,
                "layer_id": layer["id"], "counts": _counts(source), "id_map": _mapping_result(mapping),
                "redirected_bind_ids": list(incoming)}
    return {**run_operation(connection, work, checker=_checker(checker, config_root)), "tool": "transfer_objects"}

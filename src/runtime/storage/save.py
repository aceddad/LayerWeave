"""完整层/对象保存：传入记录字典或 Python 实例，显式项新增/更新，不隐式删除。"""

from copy import deepcopy

from ..configuration.loader import DEFAULT_ROOT, Loader
from ..feedback import target
from ..positions import PositionMath
from functools import partial
from ..operation import DEFAULT_CHECKER, run_operation
from . import crud
from .assembly import read_layer, read_object
from .models import infer_config, model_fields


def _get(value, name, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _parts(value, kind, project_id):
    if isinstance(value, dict):
        if "project_id" in value and value["project_id"] != project_id:
            raise ValueError("记录的 project_id 与调用项目不同；跨项目搬移需要显式处理编号")
        metadata = {"id", "project_id", "config_ref", "bind"}
        if kind == "layer":
            metadata.add("objects")
        return {name: deepcopy(item) for name, item in value.items() if name not in metadata}
    return model_fields(value, kind)


def _upsert(connection, kind, project_id, entity_id, data, operation_id, changes, positions=None):
    extra = {"position_math": positions} if kind == "object" else {}
    if entity_id is None:
        row, change = crud.create(connection, kind, data, project_id=project_id, operation_id=operation_id, **extra)
    else:
        row, change = crud.update(connection, kind, entity_id, data, project_id=project_id, operation_id=operation_id, **extra)
        if row is None:
            raise KeyError(f"{kind} ({project_id}, {entity_id}) 不存在；创建新记录时省略 id")
    if change is not None:
        changes.append(change)
        if kind == "layer" and positions is not None:
            positions.cache.clear()
    return row


def _save_bindings(connection, entries, kind, project_id, entity_id, operation_id, changes, updates):
    owner = {"source_kind": kind, "source_project_id": project_id, "source_id": entity_id}
    for entry in entries:
        payload = {name: deepcopy(value) for name, value in entry.items() if name != "id"}
        for name, value in owner.items():
            if name in payload and payload[name] != value:
                raise ValueError(f"bind 的 {name} 与所属实体不同")
        payload.update(owner)
        bind_id = entry.get("id")
        if bind_id is not None:
            previous = crud.read(connection, "bind", id=bind_id)
            if previous is None or any(previous[name] != value for name, value in owner.items()):
                raise ValueError(f"bind {bind_id} 不属于当前实体；新建关联时省略 id")
        row = _upsert(connection, "bind", None, bind_id, payload, operation_id, changes)
        updates.append((entry, row))


def _save_entity(connection, kind, project_id, value, loader, operation_id, changes, updates, *, layer_id=None, positions=None):
    entity_id = _get(value, "id")
    data = _parts(value, kind, project_id)
    if kind == "object" and layer_id is not None:
        # 保存整层明确表达装载关系；只在提交成功后回填 Python 对象的归属。
        data["layer"] = layer_id
    ref = value.get("config_ref") if isinstance(value, dict) else infer_config(value, kind, loader)
    if ref is None and entity_id is not None:
        previous = crud.read(connection, kind, project_id=project_id, id=entity_id)
        if previous is None:
            raise KeyError(f"{kind} ({project_id}, {entity_id}) 不存在")
        ref = previous["config_ref"]
    if ref is None:
        raise ValueError("新字典记录必须提供 config_ref")
    config = loader.load(ref, kind)
    if kind == "layer":
        if "type" in data and data["type"] != config["type"]:
            raise ValueError(f"type 由配置提供：传入 {data['type']!r} 与 {ref} 的 {config['type']!r} 不一致")
        data["type"] = config["type"]
    data["config_ref"] = ref
    row = _upsert(connection, kind, project_id, entity_id, data, operation_id, changes, positions)
    saved = {"id": row["id"]}
    if kind == "object":
        saved.update({name: row[name] for name in ("layer", "begin", "end")})
    if isinstance(value, dict):
        saved.update(project_id=project_id, config_ref=ref)
        if kind == "layer":
            saved["type"] = row["type"]
    updates.append((value, saved))
    _save_bindings(connection, _get(value, "bind", []), kind, project_id, row["id"], operation_id, changes, updates)
    return row


def _save(connection, kind, project_id, value, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    updates = []

    def work(operation_id):
        changes = []
        loader = Loader(config_root)
        positions = PositionMath(partial(crud.read, connection), project_id)

        def save_entity(entity_kind, entity, **context):
            try:
                return _save_entity(connection, entity_kind, project_id, entity, loader, operation_id, changes, updates,
                                    positions=positions, **context)
            except Exception as error:
                error.details = {"target": target(entity_kind, project_id, _get(entity, "id")),
                                 **getattr(error, "details", {})}
                raise

        row = save_entity(kind, value)
        if kind == "layer":
            for obj in _get(value, "objects", []):
                save_entity("object", obj, layer_id=row["id"])
            data = read_layer(connection, project_id, row["id"])
        else:
            data = read_object(connection, project_id, row["id"])
        return data, changes

    if checker is DEFAULT_CHECKER:
        def configured_checker(changes, read_record):
            from ..validation.runner import check_changes
            return check_changes(changes, read_record, config_root=config_root)
        checker = configured_checker
    result = run_operation(connection, work, checker=checker)
    if result["ok"]:
        # 事务失败不会留下已回滚的编号；检测失败不影响已成功保存的编号。
        for instance, fields in updates:
            if isinstance(instance, dict):
                instance.update(deepcopy(fields))
            else:
                for name, field in fields.items():
                    setattr(instance, name, deepcopy(field))
    return {**result, "kind": kind, "project_id": project_id}


def save_object(connection, project_id, obj, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """保存对象及传入的发出关联；实例按实际类确定配置，字典按 config_ref。"""
    return _save(connection, "object", project_id, obj, config_root=config_root, checker=checker)


def save_layer(connection, project_id, layer, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """同一事务保存层、传入 objects 和它们的 bind；type 来自层配置。"""
    return _save(connection, "layer", project_id, layer, config_root=config_root, checker=checker)

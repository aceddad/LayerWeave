"""配置与 Python 模型的适配；存储元数据保持在记录中，不加入基础类。"""

from copy import deepcopy
from importlib import import_module

from ..configuration.loader import DEFAULT_ROOT, Loader
from . import crud
from .assembly import read_layer, read_object


def _base(kind):
    module = import_module(f"models.{kind}s.base")
    return getattr(module, "Layer" if kind == "layer" else "Object")


def model_fields(value, kind):
    """只序列化已定义的存储字段；information/axis 原样深拷贝。"""
    if not isinstance(value, _base(kind)):
        raise TypeError(f"需要 {kind} 对应的基础类或派生实例")
    return {name: deepcopy(getattr(value, name)) for name in crud.SPECS[kind]["fields"] if name not in {"config_ref", "type"}}


def infer_config(value, kind, loader):
    """每个实例使用明确绑定其实际 Python 类的唯一配置。"""
    class_path = f"{type(value).__module__}:{type(value).__qualname__}"
    return loader.class_config(class_path, kind)


def restore_model(record, kind, loader):
    """还原完整记录；无法装载时明确报错，完整原始记录仍可用 read_* 读取。"""
    try:
        config = loader.load(record["config_ref"], kind)
        module_name, class_name = config["class"].split(":", 1)
        cls = import_module(module_name)
        for part in class_name.split("."):
            cls = getattr(cls, part)
        if not isinstance(cls, type) or not issubclass(cls, _base(kind)):
            raise TypeError(f"{config['class']} 必须继承 {_base(kind).__name__}")
        if f"{cls.__module__}:{cls.__qualname__}" != config["class"]:
            raise ValueError("class 必须指向类的定义位置，不能通过导入别名重复绑定")
        if kind == "layer" and config["type"] != record["type"]:
            raise ValueError(f"存储 type={record['type']!r} 与配置 type={config['type']!r} 不一致")
        names = [name for name in crud.SPECS[kind]["fields"] if name not in {"config_ref", "type"}]
        values = {name: deepcopy(record[name]) for name in names}
        values.update(id=record["id"], bind=deepcopy(record.get("bind", [])))
        instance = cls(**values)
    except Exception as error:
        raise ValueError(f"无法装载 {kind} ({record.get('project_id')}, {record.get('id')})，"
                         f"配置 {record.get('config_ref')!r}：{error}") from error
    if kind == "layer":
        instance.objects = [restore_model(obj, "object", loader) for obj in record.get("objects", [])]
    return instance


def load_object(connection, project_id, id, *, config_root=DEFAULT_ROOT):
    """按配置还原 Object 派生实例；不存在返回 None。"""
    record = read_object(connection, project_id, id)
    return None if record is None else restore_model(record, "object", Loader(config_root))


def load_layer(connection, project_id, id, *, config_root=DEFAULT_ROOT):
    """按配置还原 Layer 及它直接装载的对象，关联保持完整引用字典。"""
    record = read_layer(connection, project_id, id)
    return None if record is None else restore_model(record, "layer", Loader(config_root))

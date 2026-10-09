"""抽象核心：模型与封装语义，不依赖存储、配置文件或工具。"""
from .encapsulation import DefinitionError, merge_definition
from .identity import identity_key, reference

__all__ = ["Layer", "Object", "DefinitionError", "merge_definition", "identity_key", "reference"]


def __getattr__(name):
    if name == "Layer":
        from models.layers.base import Layer
        return Layer
    if name == "Object":
        from models.objects.base import Object
        return Object
    raise AttributeError(name)

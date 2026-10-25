"""兼容统一导入入口，只加载实际请求的类。"""

from importlib import import_module


_MODULES = {'Object': 'base', 'Text': 'text', 'Title': 'title', 'Data': 'data', 'Image': 'image', 'Audio': 'audio', 'Movie': 'movie', 'Model': 'model', 'Active': 'active'}
__all__ = list(_MODULES)


def __getattr__(name):
    if name not in _MODULES:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{_MODULES[name]}"), name)
    globals()[name] = value
    return value

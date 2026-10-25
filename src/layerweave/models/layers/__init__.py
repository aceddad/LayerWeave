"""兼容统一导入入口，只加载实际请求的类。"""

from importlib import import_module


_MODULES = {'Layer': 'base', 'TextLayer': 'text', 'DataLayer': 'data', 'ImageLayer': 'image', 'AudioLayer': 'audio', 'MovieLayer': 'movie', 'ModelLayer': 'model', 'ActiveLayer': 'active'}
__all__ = list(_MODULES)


def __getattr__(name):
    if name not in _MODULES:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{_MODULES[name]}"), name)
    globals()[name] = value
    return value

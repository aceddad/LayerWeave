"""层与对象的按需导入入口；导入 models 不加载全部封装。"""

from importlib import import_module


_LAYERS = {"Layer", "TextLayer", "DataLayer", "ImageLayer", "AudioLayer", "MovieLayer", "ModelLayer", "ActiveLayer"}
_OBJECTS = {"Object", "Text", "Title", "Data", "Image", "Audio", "Movie", "Model", "Active"}
__all__ = sorted(_LAYERS | _OBJECTS)


def __getattr__(name):
    if name not in _LAYERS | _OBJECTS:
        raise AttributeError(name)
    module = import_module(f"{__name__}.{'layers' if name in _LAYERS else 'objects'}")
    value = getattr(module, name)
    globals()[name] = value
    return value

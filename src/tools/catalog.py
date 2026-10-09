"""兼容旧路径；实现已迁至 tools.shared.catalog。新增代码使用新路径。"""

from tools.shared.catalog import *
from tools.shared.catalog import __dict__ as _exports


def __getattr__(name):
    try:
        return _exports[name]
    except KeyError:
        raise AttributeError(name) from None

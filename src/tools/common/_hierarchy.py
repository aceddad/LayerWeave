"""兼容旧路径；实现已迁至 tools.usage.common._hierarchy。新增代码使用新路径。"""

from tools.usage.common._hierarchy import *
from tools.usage.common._hierarchy import __dict__ as _exports


def __getattr__(name):
    try:
        return _exports[name]
    except KeyError:
        raise AttributeError(name) from None

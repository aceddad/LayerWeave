"""兼容旧路径；实现已迁至 tools.shared._cli。新增代码使用新路径。"""

from tools.shared._cli import *
from tools.shared._cli import __dict__ as _exports


def __getattr__(name):
    try:
        return _exports[name]
    except KeyError:
        raise AttributeError(name) from None

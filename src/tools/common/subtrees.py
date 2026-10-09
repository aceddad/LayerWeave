"""兼容旧路径；实现已迁至 tools.usage.common.subtrees。新增代码使用新路径。"""

from tools.usage.common.subtrees import *
from tools.usage.common.subtrees import __dict__ as _exports


def __getattr__(name):
    try:
        return _exports[name]
    except KeyError:
        raise AttributeError(name) from None


if __name__ == "__main__":
    raise SystemExit(main())

"""兼容旧路径；实现已迁至 tools.shared.config_help。新增代码使用新路径。"""

from tools.shared.config_help import *
from tools.shared.config_help import __dict__ as _exports


def __getattr__(name):
    try:
        return _exports[name]
    except KeyError:
        raise AttributeError(name) from None


if __name__ == "__main__":
    raise SystemExit(main())

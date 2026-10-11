"""可独立增减的组件版本登记工具；声明存在即可登记，不控制工具运行。"""
from .service import manage_versions, read_versions, sync_versions

__all__ = ["manage_versions", "read_versions", "sync_versions"]

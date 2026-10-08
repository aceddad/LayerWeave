"""LayerWeave 的工具开发入口；完整用法见同目录 API.md。"""

from .configuration.loader import Loader
from .dispatch import dispatch
from .storage.assembly import read_layer, read_object, read_project_index
from .storage.assembly import _snapshot as read_snapshot
from .storage.crud import read as read_record
from .storage.database import initialize_database, open_database
from .storage.models import load_layer, load_object
from .storage.save import save_layer, save_object
from .storage.queries import query_objects, read_bindings


def validate(*args, **kwargs):
    """主动复查，按需加载检测器。"""
    from .validation.runner import validate as check
    return check(*args, **kwargs)


__all__ = ["Loader", "dispatch", "initialize_database", "open_database", "read_layer", "read_object", "read_project_index",
           "load_layer", "load_object", "save_layer", "save_object", "validate",
           "read_record", "read_snapshot", "query_objects", "read_bindings"]

"""LayerWeave 的工具开发入口；完整用法见同目录 API.md。"""

from .configuration.loader import Loader
from .dispatch import dispatch
from .operation import DEFAULT_CHECKER
from .feedback import format_feedback, format_issue
from .positions import PositionMath, decimal_value
from .storage.assembly import read_layer, read_object, read_project_index
from .storage.assembly import _snapshot as read_snapshot
from .storage.crud import read as read_record
from .storage.database import initialize_database, open_database
from .storage.models import load_layer, load_object
from .storage.save import save_layer, save_object
from .storage.queries import query_objects, read_bindings, read_layer_positions
from .storage.details import read_project_details


def validate(*args, **kwargs):
    """主动复查，按需加载检测器。"""
    from .validation.runner import validate as check
    return check(*args, **kwargs)


def diagnostic_report(issues, *, config_root=None):
    """只读工具共用的汇报配置、同因合并与静音处理。"""
    from .validation.diagnostics import prepare_diagnostics
    from .validation.channel import report
    return report(prepare_diagnostics(issues, **({"config_root": config_root} if config_root is not None else {})))


def read_support(*args, **kwargs):
    """动态读取层/对象封装的 help，不需要项目或数据库，不导入封装类。"""
    from .configuration.catalog import read_support as read
    return read(*args, **kwargs)


def recheck(*args, **kwargs):
    """按项目、子树或对象范围主动复查。"""
    from .validation.recheck import recheck as check
    return check(*args, **kwargs)


def read_history(*args, **kwargs):
    """按操作分页查看历史，或展开指定操作。"""
    from .storage.history import read_history as read
    return read(*args, **kwargs)


def undo_operation(*args, **kwargs):
    """原子撤销完整操作；对撤销操作再调用即可重做。"""
    from .storage.undo import undo_operation as undo
    return undo(*args, **kwargs)


def delete_subtree(*args, **kwargs):
    """原子删除起始层、子孙层、装载对象及它们发出的关联。"""
    from .storage.subtrees import delete_subtree as delete
    return delete(*args, **kwargs)


def copy_subtree(*args, **kwargs):
    """同项目、同父层复制子树，返回新旧编号映射。"""
    from .storage.subtrees import copy_subtree as copy
    return copy(*args, **kwargs)


def split_object(*args, **kwargs):
    """显式切点和内容分割；第一段保留编号与关联。"""
    from .storage.timeline import split_object as split
    return split(*args, **kwargs)


def shift_objects(*args, **kwargs):
    """批量平移，支持对象/层/子树选择与 begin 下限。"""
    from .storage.timeline import shift_objects as shift
    return shift(*args, **kwargs)


def insert_gap(*args, **kwargs):
    """跨界分割与后移共用一个事务。"""
    from .storage.timeline import insert_gap as insert
    return insert(*args, **kwargs)


def transfer_subtree(*args, **kwargs):
    """跨项目复制或剪切；剪切让外部入向关联跟随新身份。"""
    from .storage.subtrees import transfer_subtree as transfer
    return transfer(*args, **kwargs)


def command_help(*args, **kwargs):
    """只读发现所有命令及参数/示例，不执行命令或导入被发现的模块。"""
    from tools.catalog import command_help as describe
    return describe(*args, **kwargs)


def transfer_objects(*args, **kwargs):
    """将选中对象及出向关联复制/剪切到另一项目的已有层。"""
    from .storage.subtrees import transfer_objects as transfer
    return transfer(*args, **kwargs)


def find_gaps(*args, **kwargs):
    """查询指定层在有限区间内的空档，不改写位置。"""
    from tools.common.free_ranges import find_gaps as find
    return find(*args, **kwargs)


__all__ = ["Loader", "dispatch", "initialize_database", "open_database", "read_layer", "read_object", "read_project_index",
           "load_layer", "load_object", "save_layer", "save_object", "validate",
           "read_record", "read_snapshot", "query_objects", "read_bindings", "read_project_details", "DEFAULT_CHECKER",
           "format_feedback", "format_issue", "diagnostic_report", "PositionMath", "decimal_value", "read_support",
           "recheck", "read_history", "undo_operation", "delete_subtree", "copy_subtree",
           "split_object", "shift_objects", "insert_gap", "transfer_subtree", "command_help",
           "transfer_objects", "find_gaps", "read_layer_positions"]

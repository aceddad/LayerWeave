"""基础支撑的公共入口；没有内置工具也能读写和还原 Python 实例。"""
from .configuration.loader import Loader
from .providers import DEFAULT_CHECKER
from .operation import run_operation
from .transaction import transaction, WriteSession
from .feedback import format_feedback, format_issue
from .positions import PositionMath, decimal_value
from .storage.assembly import read_layer, read_object, read_project_index
from .storage.snapshot import read_snapshot
from .records import read as read_record
from .storage.database import initialize_database, open_database
from .storage.models import load_layer, load_object
from .storage.save import save_layer, save_object, save_layer_in_session, save_object_in_session
from .storage.queries import query_objects, read_bindings, read_layer_positions
from .storage.details import read_project_details
from .storage.change_feed import change_cursor, read_changes
from .storage.tables import register_tables, table_specs
from .numbering import allocate, register_numbering, numbering_entries, register_numbering_rule, increment


def diagnostic_report(issues, *, config_root=None):
    """通用汇报配置、同因合并与静音处理，不执行内容检测。"""
    from .diagnostics import prepare_diagnostics
    from .channel import report
    return report(prepare_diagnostics(issues, **({"config_root": config_root} if config_root is not None else {})))


__all__ = [
    'Loader',
    'DEFAULT_CHECKER',
    'run_operation',
    'transaction',
    'WriteSession',
    'format_feedback',
    'format_issue',
    'PositionMath',
    'decimal_value',
    'read_layer',
    'read_object',
    'read_project_index',
    'read_snapshot',
    'read_record',
    'initialize_database',
    'open_database',
    'load_layer',
    'load_object',
    'save_layer',
    'save_object',
    'save_layer_in_session',
    'save_object_in_session',
    'query_objects',
    'read_bindings',
    'read_layer_positions',
    'read_project_details',
    'change_cursor',
    'read_changes',
    'register_tables',
    'table_specs',
    'allocate',
    'register_numbering',
    'numbering_entries',
    'register_numbering_rule',
    'increment',
    'diagnostic_report',
]

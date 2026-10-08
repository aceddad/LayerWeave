"""记录 CRUD 与完整模型保存共用一次事务、操作编号和提交后检测。"""

from functools import partial
from uuid import uuid4

from .storage import crud
from .validation.channel import run_checks


DEFAULT_CHECKER = object()


class RequestError(Exception):
    """为批次中的原始异常保留请求位置。"""

    def __init__(self, error, index):
        self.error, self.index = error, index


def _builtin_checker(changes, read_record):
    from .validation.runner import check_changes
    return check_changes(changes, read_record)


def run_operation(connection, work, *, writing=True, checker=DEFAULT_CHECKER):
    """work(operation_id) 返回 (data, changes)；本函数拥有整个事务。"""
    operation_id = uuid4().hex
    try:
        if connection.in_transaction:
            raise ValueError("操作入口需要没有待提交操作的连接；组合低层操作可直接使用 CRUD 方法")
        with connection:
            connection.execute("BEGIN IMMEDIATE" if writing else "BEGIN")
            data, changes = work(operation_id)
    except Exception as error:
        index = None
        if isinstance(error, RequestError):
            index, error = error.index, error.error
        detail = {"type": type(error).__name__, "message": str(error)}
        if index is not None:
            detail["request_index"] = index
        return {"operation_id": operation_id, "ok": False, "applied": False, "error": detail,
                "checks": {"status": "not_run", "reason": "operation_failed", "issues": []}}
    if checker is DEFAULT_CHECKER:
        checker = _builtin_checker
    checks = run_checks(changes, partial(crud.read, connection), checker)
    return {"operation_id": operation_id, "ok": True, "applied": bool(changes), "data": data, "checks": checks}

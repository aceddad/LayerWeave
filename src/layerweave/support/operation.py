"""记录 CRUD 与完整模型保存共用一次事务、操作编号和提交后检测。"""

from functools import partial
from uuid import uuid4

from layerweave.support.storage import crud
from layerweave.support.channel import run_checks
from layerweave.support.feedback import error_detail, operation_result


from .transaction import transaction, reject_nested_operation


def run_operation(connection, work, *, writing=True, checker=None):
    """work(write_session) 返回业务结果；实际变更由支撑层收集，本函数拥有事务。"""
    reject_nested_operation(connection)
    operation_id = uuid4().hex
    try:
        with transaction(connection, writing=writing, _operation_id=operation_id) as session:
            data = work(session)
        changes = session.changes
        numbering = session.numbering
    except Exception as error:
        detail = error_detail(error)
        return {"operation_id": operation_id, "operation": operation_result("failed"),
                "ok": False, "applied": False, "error": detail,
                "checks": {"status": "not_run", "reason": "operation_failed", "issues": []}}
    checks = run_checks(changes, partial(crud.read, connection), checker)
    applied = bool(changes or numbering)
    status = "committed" if applied else "unchanged" if writing else "read"
    return {"operation_id": operation_id, "operation": operation_result(status, changes, numbering=numbering),
            "ok": True, "applied": applied, "data": data, "checks": checks}

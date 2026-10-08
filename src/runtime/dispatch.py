"""一次请求或一批请求：统一事务、操作编号，提交后调用独立检测通道。"""

from functools import partial
from uuid import uuid4

from .storage import crud
from .validation.channel import run_checks


WRITES = {"create": crud.create, "update": crud.update, "delete": crud.delete}
_DEFAULT_CHECKER = object()


def _builtin_checker(changes, read_record):
    # 导入也属于检测阶段；即使执行器导入失败，channel 仍能保留写入成功的反馈。
    from .validation.runner import check_changes
    return check_changes(changes, read_record)


def _error(operation_id, error, index=None):
    detail = {"type": type(error).__name__, "message": str(error)}
    if index is not None:
        detail["request_index"] = index
    return {
        "operation_id": operation_id, "ok": False, "applied": False,
        "error": detail,
        "checks": {"status": "not_run", "reason": "operation_failed", "issues": []},
    }


def dispatch(connection, request, *, checker=_DEFAULT_CHECKER):
    """接收一份请求字典或请求列表；列表按一个事务提交，检测在提交后统一运行。"""
    operation_id = uuid4().hex
    if connection.in_transaction:
        return _error(operation_id, ValueError(
            "dispatch 管理完整事务，请使用没有待提交操作的连接；组合低层操作可直接使用 CRUD 方法"
        ))
    batch = isinstance(request, list)
    requests = request if batch else [request]
    results, changes = [], []
    index = None
    try:
        with connection:
            writing = any(isinstance(item, dict) and item.get("action") in WRITES for item in requests)
            # 在读取修改前快照之前开始事务，保证数据与日志描述同一次修改。
            connection.execute("BEGIN IMMEDIATE" if writing else "BEGIN")
            for index, item in enumerate(requests):
                if not isinstance(item, dict):
                    raise TypeError("每条请求必须是对象")
                args = dict(item)
                action = args.pop("action")
                kind = args.pop("kind")
                if action == "read":
                    data = crud.read(connection, kind, **args)
                    change = None
                elif action in WRITES:
                    data, change = WRITES[action](
                        connection, kind, operation_id=operation_id, **args,
                    )
                else:
                    raise ValueError(f"未知 action：{action}")
                result = {
                    "action": action, "kind": kind,
                    "project_id": args.get("project_id"),
                    "id": data["id"] if isinstance(data, dict) else args.get("id"),
                    "applied": change is not None, "data": data,
                }
                results.append(result)
                if change is not None:
                    changes.append(change)
    except Exception as error:
        return _error(operation_id, error, index)

    # 只有在事务成功提交后才会到这里；检查失败不会改写操作的成功状态。
    if checker is _DEFAULT_CHECKER:
        checker = _builtin_checker
    checks = run_checks(changes, partial(crud.read, connection), checker)
    common = {"operation_id": operation_id, "ok": True, "checks": checks}
    if batch:
        return {**common, "applied": bool(changes), "results": results}
    return {**common, **results[0]}

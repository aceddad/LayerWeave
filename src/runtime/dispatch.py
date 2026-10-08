"""一次请求或一批请求：统一事务、操作编号，提交后调用独立检测通道。"""

from .storage import crud
from .operation import DEFAULT_CHECKER, RequestError, run_operation


WRITES = {"create": crud.create, "update": crud.update, "delete": crud.delete}


def dispatch(connection, request, *, checker=DEFAULT_CHECKER):
    """接收一份请求字典或请求列表；列表按一个事务提交，检测在提交后统一运行。"""
    batch = isinstance(request, list)
    requests = request if batch else [request]

    def work(operation_id):
        results, changes = [], []
        for index, item in enumerate(requests):
            try:
                if not isinstance(item, dict):
                    raise TypeError("每条请求必须是对象")
                args = dict(item)
                action = args.pop("action")
                kind = args.pop("kind")
                if action == "read":
                    full = args.pop("full", False)
                    if full:
                        if kind not in {"layer", "object"} or args.get("id") is None:
                            raise ValueError("完整读取需要明确的 layer/object 及 id")
                        from .storage.assembly import read_layer, read_object
                        reader = read_layer if kind == "layer" else read_object
                        data = reader(connection, **args)
                    else:
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
                raise RequestError(error, index) from error
        return results, changes

    writing = any(isinstance(item, dict) and item.get("action") in WRITES for item in requests)
    result = run_operation(connection, work, writing=writing, checker=checker)
    if not result["ok"]:
        return result
    results = result.pop("data")
    if batch:
        return {**result, "results": results}
    return {**result, **results[0]}

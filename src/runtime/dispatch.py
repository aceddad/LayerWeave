"""一次请求或一批请求：统一事务、操作编号，提交后调用独立检测通道。"""

from functools import partial

from .storage import crud
from .operation import DEFAULT_CHECKER, RequestError, run_operation
from .configuration.loader import DEFAULT_ROOT, Loader


WRITES = {"create": crud.create, "update": crud.update, "delete": crud.delete}


def dispatch(connection, request, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """接收请求或 request(read_record) 工厂；工厂在写事务内计算请求，提交后统一检测。"""
    batch = isinstance(request, list)
    dynamic = callable(request)

    def work(operation_id):
        nonlocal batch
        resolved = request(partial(crud.read, connection)) if dynamic else request
        batch = isinstance(resolved, list)
        requests = resolved if batch else [resolved]
        results, changes = [], []
        loader = Loader(config_root)
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
                    # 原始请求仍可显式保存 type；省略时从本次指定的配置补齐。
                    payload = args.get("data")
                    if kind == "layer" and action in {"create", "update"} and isinstance(payload, dict):
                        if "type" not in payload and "config_ref" in payload:
                            args["data"] = {**payload, "type": loader.load(payload["config_ref"], "layer")["type"]}
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

    static_requests = request if batch else [request]
    writing = dynamic or any(isinstance(item, dict) and item.get("action") in WRITES for item in static_requests)
    if checker is DEFAULT_CHECKER:
        def configured_checker(changes, read_record):
            from .validation.runner import check_changes
            return check_changes(changes, read_record, config_root=config_root)
        checker = configured_checker
    result = run_operation(connection, work, writing=writing, checker=checker)
    if not result["ok"]:
        return result
    results = result.pop("data")
    if batch:
        return {**result, "results": results}
    return {**result, **results[0]}

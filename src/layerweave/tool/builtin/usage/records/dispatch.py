"""一次请求或一批请求：统一事务、操作编号，提交后调用独立检测通道。"""

from functools import partial

from layerweave.support import records as crud
from layerweave.support.operation import run_operation
from layerweave.support.providers import DEFAULT_CHECKER, optional_checker
from layerweave.support.configuration.loader import DEFAULT_ROOT, Loader
from layerweave.support.feedback import InputError, target
from layerweave.support.positions import PositionMath


WRITES = {"create": crud.create, "update": crud.update, "delete": crud.delete}


def dispatch(connection, request, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """接收请求或 request(read_record) 工厂；工厂在写事务内计算请求，提交后统一检测。"""
    batch = isinstance(request, list)
    dynamic = callable(request)

    def work(write):
        operation_id = write.operation_id
        nonlocal batch
        resolved = request(partial(crud.read, connection)) if dynamic else request
        batch = isinstance(resolved, list)
        requests = resolved if batch else [resolved]
        results = []
        loader = Loader(config_root)
        positions = {}
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
                        from layerweave.support.storage.assembly import read_layer, read_object
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
                    if kind == "object" and action in {"create", "update"}:
                        project_id = args.get("project_id")
                        if project_id not in positions:
                            positions[project_id] = PositionMath(partial(crud.read, connection), project_id)
                        args["position_math"] = positions[project_id]
                    data, change = WRITES[action](
                        connection, kind, operation_id=operation_id, **args,
                    )
                    if kind == "layer" and change is not None:
                        for math in positions.values():
                            math.cache.clear()
                else:
                    raise InputError(f"未知 action：{action}", code="unknown_action", field="action",
                                     allowed=["create", "read", "update", "delete"])
                result = {
                    "action": action, "kind": kind,
                    "project_id": args.get("project_id"),
                    "id": data["id"] if isinstance(data, dict) else args.get("id"),
                    "applied": change is not None, "data": data,
                }
                results.append(result)
            except Exception as error:
                error.details = {**getattr(error, "details", {}), "request_index": index}
                if isinstance(item, dict) and isinstance(item.get("kind"), str) and item["kind"] in {"project", "layer", "object", "bind", "change"}:
                    error.details.setdefault("target", target(item["kind"], item.get("project_id"), item.get("id")))
                raise
        return results

    static_requests = request if batch else [request]
    writing = dynamic or any(isinstance(item, dict) and item.get("action") in WRITES for item in static_requests)
    checker = optional_checker(checker, config_root=config_root)
    result = run_operation(connection, work, writing=writing, checker=checker)
    if not result["ok"]:
        return result
    results = result.pop("data")
    if batch:
        return {**result, "results": results}
    return {**result, **results[0]}

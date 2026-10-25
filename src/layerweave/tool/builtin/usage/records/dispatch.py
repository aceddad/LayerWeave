"""一次请求或一批请求：统一事务、操作编号，提交后调用独立检测通道。"""

from functools import partial

from layerweave.support import records as crud
from layerweave.support.operation import run_operation
from layerweave.support.transaction import require_write_session
from layerweave.support.providers import DEFAULT_CHECKER, optional_checker
from layerweave.support.configuration.loader import DEFAULT_ROOT, Loader
from layerweave.support.feedback import InputError, target
from layerweave.support.positions import PositionMath
from layerweave.support.storage.tables import get_spec
from layerweave.support.storage.binary import decode_binary


WRITES = {"create": crud.create, "update": crud.update, "delete": crud.delete}


def _execute(write, request, *, config_root=DEFAULT_ROOT):
    connection = write.connection
    operation_id = write.operation_id
    resolved = request(partial(crud.read, connection)) if callable(request) else request
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
                if action in {"create", "update"} and isinstance(args.get("data"), dict):
                    args["data"] = decode_binary(get_spec(connection, kind, writing=True), args["data"])
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
            if isinstance(item, dict) and isinstance(item.get("kind"), str) and item["kind"] in crud.table_specs(connection):
                error.details.setdefault("target", target(item["kind"], item.get("project_id"), item.get("id")))
            raise
    return batch, results


def dispatch_in_session(write, request, *, config_root=DEFAULT_ROOT):
    """在已有写会话执行请求；返回单条数据或按请求顺序的数据列表，失败抛出。"""
    require_write_session(write)
    batch, results = _execute(write, request, config_root=config_root)
    return [item["data"] for item in results] if batch else results[0]["data"]


def dispatch(connection, request, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """独立执行一次请求或批次，统一事务并在提交后运行可选检测。"""
    requests = request if isinstance(request, list) else [request]
    writing = callable(request) or any(isinstance(item, dict) and item.get("action") in WRITES for item in requests)
    result = run_operation(connection, lambda write: _execute(write, request, config_root=config_root),
                           writing=writing, checker=optional_checker(checker, config_root=config_root))
    if not result["ok"]:
        return result
    batch, results = result.pop("data")
    return {**result, "results": results} if batch else {**result, **results[0], "applied": result["applied"]}

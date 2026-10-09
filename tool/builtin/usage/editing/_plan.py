"""编辑包内部的变更计划执行；只翻译本包生成的步骤，不依赖 CDUR 工具包。"""
from functools import partial

from support import records
from support.operation import run_operation
from support.feedback import target
from support.configuration.loader import DEFAULT_ROOT
from support.providers import DEFAULT_CHECKER, optional_checker
from support.positions import PositionMath


def dispatch(connection, plan, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    def work(write):
        operation_id = write.operation_id
        requests = plan(partial(records.read, connection))
        batch = isinstance(requests, list)
        results = []
        positions = {}
        for index, item in enumerate(requests if batch else [requests]):
            try:
                args = dict(item)
                action, kind = args.pop("action"), args.pop("kind")
                if action == "read":
                    data, change = records.read(connection, kind, **args), None
                else:
                    if action not in {"create", "update", "delete"}:
                        raise ValueError(f"编辑步骤不支持 {action}")
                    if kind == "object" and action != "delete":
                        owner = args.get("project_id")
                        if owner not in positions:
                            positions[owner] = PositionMath(partial(records.read, connection), owner)
                        args["position_math"] = positions[owner]
                    data, change = getattr(records, action)(connection, kind, operation_id=operation_id, **args)
                    if kind == "layer" and change:
                        positions.clear()
                results.append({"action": action, "kind": kind, "project_id": args.get("project_id"),
                                "id": data["id"] if isinstance(data, dict) else args.get("id"),
                                "applied": change is not None, "data": data})
            except Exception as error:
                error.details = {**getattr(error, "details", {}), "request_index": index}
                if isinstance(item, dict) and isinstance(item.get("kind"), str) and item["kind"] in {"project", "layer", "object", "bind"}:
                    error.details.setdefault("target", target(item["kind"], item.get("project_id"), item.get("id")))
                raise
        return (batch, results)
    result = run_operation(connection, work, checker=optional_checker(checker, config_root=config_root))
    if not result["ok"]:
        return result
    batch, results = result.pop("data")
    return {**result, "results": results} if batch else {**result, **results[0]}

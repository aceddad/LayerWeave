"""版本登记业务：一张普通工具表，所有记录写入复用公共写会话。"""
from layerweave.support.api import read_record, register_tables, run_operation, table_specs
from layerweave.support.feedback import InputError

from .discovery import scan_components, within


KIND = "component_version"
TABLES = {KIND: {"scoped": False, "fields": {
    "name": {"type": "TEXT", "nullable": False},
    "version": {"type": "TEXT", "nullable": False},
    "kind": {"type": "TEXT", "default": "tool"},
    "description": {"type": "TEXT", "default": ""},
    "changes": {"type": "TEXT", "default": ""},
    "status": {"type": "TEXT", "nullable": False},
    "sources": {"type": "JSON", "default": {}},
    "checked_at": {"type": "TEXT", "nullable": False},
}}}
STATES = ("online", "inactive", "unknown")


def _result(items, **extra):
    return {"items": sorted(items, key=lambda row: (row["name"], row["version"], row["id"])),
            "counts": {state: sum(row["status"] == state for row in items) for state in STATES}, **extra}


def read_versions(connection, *, name=None, status=None):
    """读取上次同步结果，不建表、不扫描文件、不写入。"""
    if status is not None and status not in STATES:
        raise InputError("未知版本状态", field="status", allowed=list(STATES))
    filters = {key: value for key, value in (("name", name), ("status", status)) if value is not None}
    registered = KIND in table_specs(connection)
    items = read_record(connection, KIND, filters=filters) if registered else []
    return _result(items, registered=registered)


def sync_versions(connection, *, roots=None):
    """自动登记本次扫描的声明，并更新该范围内历史版本的存在状态。"""
    scan = scan_components(roots)
    register_tables(connection, TABLES)

    def work(write):
        previous = write.read(KIND)
        found = {}
        for item in scan["items"]:
            found.setdefault((item["name"], item["version"]), []).append(item)
        existing = {(row["name"], row["version"]) for row in previous}
        touched = []

        def values(row, declarations):
            sources = dict(row.get("sources", {}))
            affected = bool(declarations)
            for source in sources:
                if any(within(source, root) for root in scan["roots"]):
                    affected = True
                    sources[source] = "unknown" if any(within(source, failed) for failed in scan["failed"]) else "inactive"
            for item in declarations:
                sources[item["source"]] = "online"
            if not affected:
                return None
            status = next((state for state in ("online", "unknown") if state in sources.values()), "inactive")
            result = {"sources": sources, "status": status, "checked_at": scan["checked_at"]}
            if declarations:
                # 同名同版本多份声明共用一条记录；按路径排序的首份提供说明。
                result.update({key: declarations[0][key] for key in ("name", "version", "kind", "description", "changes")})
            return result

        for row in previous:
            data = values(row, found.get((row["name"], row["version"]), []))
            if data is not None:
                touched.append(write.update(KIND, row["id"], data))
        for key, declarations in found.items():
            if key not in existing:
                touched.append(write.create(KIND, values({}, declarations)))
        return _result(touched, roots=scan["roots"], checked_at=scan["checked_at"],
                       status=scan["status"], issues=scan["issues"])

    return run_operation(connection, work)


def manage_versions(connection, action="sync", *, roots=None, name=None, status=None):
    """单一分流入口；sync 写入，read 仅读取上次同步结果。"""
    if action == "sync":
        if name is not None or status is not None:
            raise InputError("name/status 筛选只用于 read；sync 用 roots 确定扫描范围", field="action")
        return sync_versions(connection, roots=roots)
    if action == "read":
        if roots is not None:
            raise InputError("roots 只用于 sync", field="roots")
        return run_operation(connection, lambda _: read_versions(connection, name=name, status=status), writing=False)
    raise InputError("未知版本操作", field="action", allowed=["sync", "read"])

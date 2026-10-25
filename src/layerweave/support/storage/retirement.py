"""退出托管仅迁移登记元数据；物理表、数据及外键由外部工具管理。"""
from datetime import datetime, timezone
from copy import deepcopy
import json

from layerweave.support.feedback import InputError
from .tables import CATALOG, SPECS, _complete_spec, _exists, quote, table_specs
from ._metadata import cached, invalidate


RETIRED_CATALOG = "_layerweave_retired_tables"


def retired_tables(connection):
    """只读退役目录，返回 kind -> {definition, retired_at}；旧库返回空字典。"""
    return deepcopy(_retired_tables(connection))


def _retired_tables(connection):
    return cached(connection, "retired", _load_retired_tables)


def _load_retired_tables(connection):
    if connection is None or not _exists(connection, RETIRED_CATALOG):
        return {}
    return {row[0]: {"definition": _complete_spec(json.loads(row[1])), "retired_at": row[2]}
            for row in connection.execute(
                f"SELECT kind, definition, retired_at FROM {quote(RETIRED_CATALOG)} ORDER BY kind")}


def unregister_tables(connection, kinds):
    """原子注销指定工具 kind；不删物理表、不回退计数、不进入业务撤销。"""
    from layerweave.support.transaction import transaction
    from layerweave.support.numbering.registry import numbering_entries, persist_entries

    if not isinstance(kinds, (list, tuple)) or not all(isinstance(kind, str) for kind in kinds):
        raise InputError("kinds 需要工具 kind 的列表", code="table_definition", field="kinds")
    requested = list(dict.fromkeys(kinds))
    if any(kind.lower() in SPECS for kind in requested):
        raise InputError("不能注销内置种类", code="builtin_kind", field="kinds")
    with transaction(connection):
        active, retired = table_specs(connection), retired_tables(connection)
        leaving = set(requested) & active.keys()
        dependencies = []
        for kind, spec in active.items():
            if kind in leaving:
                continue
            for category in ("references", "logical_references"):
                for ref in spec.get(category, []):
                    if ref["kind"] in leaving:
                        dependencies.append({"kind": kind, "field": category, "reference": ref})
        entries = numbering_entries(connection)
        for name, entry in entries.items():
            if entry["counter"]["kind"] in leaving:
                dependencies.append({"entry": name, "field": "counter", "counter": entry["counter"]})
        if dependencies:
            raise InputError("仍有活动声明或发号计数来源依赖，本批未注销；请先处理依赖或一起注销引用表",
                             code="table_dependencies", dependencies=dependencies)
        result = {"retired": [], "already_retired": [k for k in requested if k in retired],
                  "not_registered": [k for k in requested if k not in active and k not in retired]}
        if leaving:
            connection.execute(f"CREATE TABLE IF NOT EXISTS {quote(RETIRED_CATALOG)} "
                               "(kind TEXT PRIMARY KEY, definition TEXT NOT NULL, retired_at TEXT NOT NULL)")
            timestamp = datetime.now(timezone.utc).isoformat()
            for kind in requested:
                if kind not in leaving:
                    continue
                connection.execute(f"INSERT INTO {quote(RETIRED_CATALOG)} (kind, definition, retired_at) "
                                   f"SELECT kind, definition, ? FROM {quote(CATALOG)} WHERE kind=?", (timestamp, kind))
                connection.execute(f"DELETE FROM {quote(CATALOG)} WHERE kind=?", (kind,))
                result["retired"].append({"kind": kind, "table": active[kind]["table"], "retired_at": timestamp})
            for entry in entries.values():
                entry["members"] = [kind for kind in entry["members"] if kind not in leaving]
            invalidate(connection)
            persist_entries(connection, entries)
    return result

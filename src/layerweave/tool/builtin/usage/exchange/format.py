"""交换格式的小型公共约定；不执行数据库写入。"""
from copy import deepcopy
from hashlib import sha256
import json

from layerweave.support.feedback import InputError
from layerweave.support.numbering.state import counter_fields


VERSION = 1
OPS = ("add", "update", "delete")
CORE = {"project", "layer", "object", "bind", "change"}


def fail(message, path="", **details):
    raise InputError(message, pointer=path, **details)


def document_value(document):
    if not isinstance(document, dict) or document.get("format_version") != VERSION or type(document.get("format_version")) is not int:
        fail("交换文档需要 format_version=1", "/format_version", code="exchange_format")
    for field in ("items", "records"):
        if not isinstance(document.get(field, []), list):
            fail(f"{field} 需要节点列表", "/" + field)
    if not isinstance(document.get("tables", {}), dict) or not isinstance(document.get("project", {}), dict):
        fail("tables 和 project 需要字典")
    return deepcopy(document)


def fingerprint(connection, kind, row, spec):
    ignored = counter_fields(connection, kind, row)
    fields = {name: row[name] for name in spec["fields"] if name not in ignored}
    encoded = json.dumps(fields, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return "sha256:" + sha256(encoded.encode("utf-8")).hexdigest()


def table_definition(spec):
    return {"table": spec["table"], "fields": deepcopy(spec["columns"]), "scoped": spec["scoped"],
            "references": deepcopy(spec["references"]), "id_source": spec["id_source"],
            "logical_references": deepcopy(spec.get("logical_references", [])),
            "exchange": deepcopy(spec.get("exchange", {"on_copy": "include"}))}


def relation_definitions(spec):
    """交换同时理解硬/逻辑引用；数据库约束与恢复依赖仍仅使用硬引用。"""
    result = list(spec["references"])
    for ref in spec.get("logical_references", []):
        if ref not in result:
            result.append(ref)
    return result


def identity(kind, project_id, id, specs):
    return kind, project_id if specs[kind]["scoped"] else None, id


def address(key):
    return {"kind": key[0], "project_id": key[1], "id": key[2]}


def references(kind, row, specs):
    """(引用名称, 目标身份, 实际列)；不解释 information 内部的数据。"""
    if kind == "bind":
        return [(side, (row.get(side + "_kind"), row.get(side + "_project_id"), row.get(side + "_id")),
                 (side + "_project_id", side + "_id")) for side in ("source", "target")]
    result = []
    for ref in relation_definitions(specs[kind]):
        values = [row.get(field) for field in ref["fields"]]
        if any(value is None for value in values):
            continue
        target = identity(ref["kind"], values[0] if specs[ref["kind"]]["scoped"] else None, values[-1], specs)
        result.append((ref["fields"][-1], target, tuple(ref["fields"])))
    return result

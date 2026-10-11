"""库内发号词条；计数仍保存在词条指定的业务表列中。"""
from copy import deepcopy
import json

from layerweave.core.values import same_value
from layerweave.support.feedback import InputError
from layerweave.support.storage.tables import table_specs, quote, _exists


CATALOG = "_layerweave_numbering"
PROJECT_ENTRY = "project_entities"
DEFAULT = {"rule": "project_entity", "counter": {
    "kind": "project", "field": "max_id", "key": {"id": "project_id"}},
    "members": ["layer", "object"]}


def numbering_entries(connection):
    """只读统一目录；旧库及尚未登记的默认表从原有声明取得默认成员。"""
    result = {}
    if _exists(connection, CATALOG):
        result = {row[0]: json.loads(row[1]) for row in connection.execute(
            f"SELECT name, definition FROM {quote(CATALOG)} ORDER BY name")}
    result.setdefault(PROJECT_ENTRY, deepcopy(DEFAULT))
    assigned = {kind for entry in result.values() for kind in entry["members"]}
    for kind, spec in table_specs(connection).items():
        if spec["scoped"] and spec.get("id_source", "auto") == "auto" and kind not in assigned:
            result[PROJECT_ENTRY]["members"].append(kind)
    return result


def persist_entries(connection, entries):
    from layerweave.support.transaction import require_session
    require_session(connection)
    connection.execute(f"CREATE TABLE IF NOT EXISTS {quote(CATALOG)} (name TEXT PRIMARY KEY, definition TEXT NOT NULL)")
    for name, entry in entries.items():
        connection.execute(f"INSERT INTO {quote(CATALOG)} (name, definition) VALUES (?, ?) "
                           "ON CONFLICT(name) DO UPDATE SET definition=excluded.definition WHERE definition != excluded.definition",
                           (name, json.dumps(entry, ensure_ascii=False, allow_nan=False)))


def entry_for(connection, kind, entries=None):
    entries = numbering_entries(connection) if entries is None else entries
    return next(((name, entry) for name, entry in entries.items() if kind in entry["members"]), None)


def counter_key(entry, data):
    """key 中的字符串表示参数名，正整数表示固定的计数行主键值。"""
    result = {}
    for field, binding in entry["counter"]["key"].items():
        value = data.get(binding) if isinstance(binding, str) else binding
        if type(value) is not int or value < 1:
            raise InputError(f"发号参数 {binding} 需要正整数", code="numbering_parameter", field=str(binding))
        result[field] = value
    return result


def scope_token(entry, data):
    counter = entry["counter"]
    return counter["kind"], counter["field"], tuple(sorted(counter_key(entry, data).items()))


def _has_history(connection, kind, specs):
    return (connection.execute(f'SELECT 1 FROM {quote(specs[kind]["table"])} LIMIT 1').fetchone() is not None
            or connection.execute("SELECT 1 FROM changes WHERE kind=? LIMIT 1", (kind,)).fetchone() is not None)


def _definition(raw, specs):
    if set(raw) != {"rule", "counter", "members"}:
        raise InputError("发号词条需要 rule、counter、members", code="numbering_definition")
    entry = deepcopy(raw)
    if not isinstance(entry["rule"], str) or not entry["rule"]:
        raise InputError("rule 需要规则名称", code="numbering_definition", field="rule")
    counter = entry["counter"]
    if not isinstance(counter, dict) or set(counter) != {"kind", "field", "key"}:
        raise InputError("counter 需要 kind、field、key", code="numbering_definition", field="counter")
    source = specs.get(counter["kind"])
    if source is None or counter["kind"] == "change":
        raise InputError("计数来源需要已登记的业务表", code="numbering_definition", field="counter.kind")
    field = counter["field"]
    valid_column = ((counter["kind"] == "project" and field == "max_id") or
                    source.get("columns", {}).get(field, {}).get("type") == "INTEGER")
    if not valid_column:
        raise InputError("计数列需要声明为 INTEGER 的业务列，或 project.max_id", code="numbering_definition", field="counter.field")
    keys = {"id", "project_id"} if source["scoped"] else {"id"}
    if not isinstance(counter["key"], dict) or set(counter["key"]) != keys:
        raise InputError("counter.key 需要完整的计数行主键", code="numbering_definition", field="counter.key")
    for binding in counter["key"].values():
        if not ((isinstance(binding, str) and binding and binding != "id") or (type(binding) is int and binding > 0)):
            raise InputError("计数定位使用参数名或固定正整数；不能依赖尚未发放的 id", code="numbering_definition")
    if not isinstance(entry["members"], (list, tuple)) or not all(isinstance(kind, str) for kind in entry["members"]):
        raise InputError("members 需要表种类名称列表", code="numbering_definition", field="members")
    entry["members"] = sorted(set(entry["members"]))
    parameters = {binding for binding in counter["key"].values() if isinstance(binding, str)}
    for kind in entry["members"]:
        spec = specs.get(kind)
        if spec is None or kind in {"project", "change"}:
            raise InputError(f"不可加入发号簇的成员：{kind}", code="numbering_definition", field="members")
        fields = set(spec["fields"]) | ({"project_id"} if spec["scoped"] else set())
        if not parameters <= fields:
            raise InputError(f"成员 {kind} 需要保存发号范围字段：{sorted(parameters - fields)}",
                             code="numbering_definition", field="members")
    return entry


def register_numbering(connection, definitions):
    """登记词条及其成员；结构维护不作为普通内容撤销，调用时无待提交事务。"""
    from layerweave.support.transaction import transaction
    with transaction(connection):
        specs = table_specs(connection)
        old = numbering_entries(connection)
        entries = deepcopy(old)
        proposed = {}
        for name, raw in definitions.items():
            if not isinstance(name, str) or not name:
                raise InputError("发号词条名称需要非空字符串", code="numbering_definition")
            proposed[name] = _definition(raw, specs)
        claimed = {}
        for name, entry in proposed.items():
            for kind in entry["members"]:
                if kind in claimed:
                    raise InputError(f"成员 {kind} 同时登记到多个词条", code="numbering_membership")
                claimed[kind] = name
        # 新表可从默认簇改投其他词条；已有身份或历史的归属必须显式迁移。
        for name, entry in entries.items():
            entry["members"] = [kind for kind in entry["members"] if claimed.get(kind, name) == name]
        entries.update(proposed)
        for kind in specs:
            before = entry_for(connection, kind, old)
            after = entry_for(connection, kind, entries)
            if before != after and _has_history(connection, kind, specs):
                # 追加其他成员不改变既有成员的编号含义。
                unchanged = (before is not None and after is not None and before[0] == after[0]
                             and all(same_value(before[1][key], after[1][key]) for key in ("rule", "counter")))
                if not unchanged:
                    raise InputError(f"{kind} 已有记录或历史；更换发号归属需要明确迁移", code="numbering_migration")
            if specs[kind]["scoped"] and specs[kind].get("id_source", "auto") == "auto" and after is None:
                raise InputError(f"按项目自动发号的表 {kind} 需要所属词条", code="numbering_membership")
        persist_entries(connection, entries)
    return deepcopy(proposed)

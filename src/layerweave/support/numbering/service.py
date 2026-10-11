"""薄发号入口：使用当前写会话，调度普通规则函数，不创建业务记录。"""
from layerweave.support.feedback import InputError, target
from layerweave.support.storage.tables import table_specs, quote, _exists
from layerweave.support.transaction import current_write_session

from .registry import CATALOG, counter_key, numbering_entries, persist_entries


def increment(entry, data):
    """规则共用的原子递增；计数行由词条中的 key 定位。"""
    session = current_write_session()
    connection = session.connection
    counter = entry["counter"]
    spec = table_specs(connection)[counter["kind"]]
    key = counter_key(entry, data)
    column = quote(counter["field"])
    where = " AND ".join(f"{quote(field)}=?" for field in key)
    row = connection.execute(f'UPDATE {quote(spec["table"])} SET {column}={column}+1 WHERE {where} RETURNING {column}',
                             list(key.values())).fetchone()
    if row is None:
        message = f"项目 {key['id']} 不存在" if counter["kind"] == "project" else f"计数记录 {counter['kind']} {key} 不存在"
        raise InputError(message, code="missing_reference",
                         field="project_id" if counter["kind"] == "project" else "counter",
                         reference=target(counter["kind"], key.get("project_id"), key["id"]))
    if type(row[0]) is not int or row[0] < 1:
        raise InputError("计数列需要非负整数，递增后得到正整数", code="numbering_counter", field=counter["field"])
    session._numbering.append({
        "counter": {**target(counter["kind"], key.get("project_id"), key["id"]), "field": counter["field"]},
        "before": row[0] - 1, "after": row[0],
        **({"entry": entry["name"], "rule": entry["rule"]} if "name" in entry else {}),
    })
    return row[0]


def project_entity(entry, data):
    return {"project_id": data["project_id"], "id": increment(entry, data)}


def number_only(entry, data):
    return {"id": increment(entry, data)}


RULES = {"project_entity": project_entity, "number_only": number_only}


def register_numbering_rule(name, function):
    """登记/替换本进程的规则函数 function(entry, data)，不导入外部模块。"""
    if not isinstance(name, str) or not name or not callable(function):
        raise ValueError("规则需要名称和可调用函数")
    RULES[name] = function


def allocate(name, *, data=None):
    """当前事务中调度规则；连接由写会话隐式提供，返回身份字段字典。"""
    session = current_write_session()
    entries = numbering_entries(session.connection)
    if name not in entries:
        raise InputError(f"未知发号词条：{name}", field="numbering", allowed=sorted(entries))
    entry = {**entries[name], "name": name}
    if entry["rule"] not in RULES:
        raise InputError(f"发号规则未加载：{entry['rule']}", field="rule", allowed=sorted(RULES))
    if not _exists(session.connection, CATALOG):
        persist_entries(session.connection, entries)
    first = len(session._numbering)
    identity = RULES[entry["rule"]](entry, {} if data is None else data)
    if not isinstance(identity, dict) or type(identity.get("id")) is not int or identity["id"] < 1:
        raise InputError("发号规则应返回包含正整数 id 的身份字典", code="numbering_result")
    from copy import deepcopy
    for item in session._numbering[first:]:
        item.setdefault("identity", deepcopy(identity))
    return identity

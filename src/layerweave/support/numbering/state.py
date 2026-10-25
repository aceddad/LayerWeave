"""编号状态与簇占用：恢复读取登记信息，不调用发号规则、不重新领号。"""
from layerweave.support.feedback import InputError
from layerweave.support.storage.tables import quote, _table_specs

from .registry import counter_key, entry_for, _numbering_entries, scope_token


def identity(kind, row):
    return kind, row.get("project_id"), row["id"]


def cluster_identity(connection, kind, row, entries=None):
    member = entry_for(connection, kind, entries)
    return (*scope_token(member[1], row), row["id"]) if member and row is not None else None


def _member_where(entry, key, *, snapshot=None):
    """将已定位的计数行反解成成员范围；查询当前行或历史 JSON 快照。"""
    terms, values = [], []
    for column, binding in entry["counter"]["key"].items():
        if isinstance(binding, str):
            field = f"json_extract({snapshot}, '$.{binding}')" if snapshot else quote(binding)
            terms.append(f"{field}=?")
            values.append(key[column])
        elif binding != key[column]:
            return None
    return terms, values


def cluster_occupants(connection, kind, record, *, entries=None, specs=None):
    """同一计数位置和范围中占用该编号的其他记录，不检查无关工具表。"""
    from layerweave.support.storage.crud import _decode
    entries = _numbering_entries(connection) if entries is None else entries
    member = entry_for(connection, kind, entries)
    if member is None:
        return []
    spec_counter = member[1]["counter"]
    key = counter_key(member[1], record)
    specs = _table_specs(connection) if specs is None else specs
    result = []
    for entry in entries.values():
        counter = entry["counter"]
        if (counter["kind"], counter["field"]) != (spec_counter["kind"], spec_counter["field"]):
            continue
        where = _member_where(entry, key)
        if where is None:
            continue
        terms, values = where
        for other in entry["members"]:
            spec = specs[other]
            conditions = '"id"=?' + (" AND " + " AND ".join(terms) if terms else "")
            rows = connection.execute(f'SELECT * FROM {quote(spec["table"])} WHERE {conditions}', [record["id"], *values])
            for row in rows:
                item = _decode(spec, row)
                if identity(other, item) != identity(kind, record):
                    result.append((other, item))
    return result


def check_cluster(connection, kind, record):
    occupied = cluster_occupants(connection, kind, record)
    if occupied:
        owners = ", ".join(f"{other} ({row.get('project_id')}, {row['id']})" for other, row in occupied)
        raise InputError(f"编号已被同簇记录占用：{owners}", code="id_conflict",
                         target={"kind": kind, "project_id": record.get("project_id"), "id": record["id"]},
                         occupants=[{"kind": other, "project_id": row.get("project_id"), "id": row["id"]}
                                    for other, row in occupied])


def advance_member_counter(connection, kind, record):
    """保留手动写回身份的计数上界；计数行尚未恢复时由其自身恢复流程补齐。"""
    member = entry_for(connection, kind)
    if member is None:
        return
    entry = member[1]
    counter = entry["counter"]
    spec = _table_specs(connection)[counter["kind"]]
    key = counter_key(entry, record)
    field = quote(counter["field"])
    where = " AND ".join(f"{quote(column)}=?" for column in key)
    connection.execute(f'UPDATE {quote(spec["table"])} SET {field}=MAX({field}, ?) WHERE {where}',
                       [record["id"], *key.values()])


def _counter_entries(connection, kind, row, entries=None):
    if row is None:
        return []
    entries = _numbering_entries(connection) if entries is None else entries
    return [entry for entry in entries.values() if entry["counter"]["kind"] == kind and
            all(isinstance(binding, str) or row.get(field) == binding for field, binding in entry["counter"]["key"].items())]


def counter_fields(connection, kind, row):
    return {entry["counter"]["field"] for entry in _counter_entries(connection, kind, row)}


def check_counter_update(connection, kind, before, values):
    for field in counter_fields(connection, kind, before) & values.keys():
        value = values[field]
        if type(value) is not int or value < before[field]:
            raise InputError(f"发号计数列 {field} 只能保持或提高，不能回退", code="counter_rewind", field=field)


def preserve_counters(connection, kind, desired, current=None):
    """恢复计数行时，保留现有计数、成员编号以及历史快照中的最高值。"""
    entries = _counter_entries(connection, kind, desired)
    if not entries:
        return desired
    specs = _table_specs(connection)
    result = dict(desired)
    for entry in entries:
        counter = entry["counter"]
        field = counter["field"]
        key = {column: desired[column] for column in counter["key"]}
        highest = max(result.get(field, 0), (current or {}).get(field, 0))
        for member in entry["members"]:
            spec = specs[member]
            terms, values = _member_where(entry, key)
            where = " WHERE " + " AND ".join(terms) if terms else ""
            row = connection.execute(f'SELECT MAX(id) FROM {quote(spec["table"])}{where}', values).fetchone()
            highest = max(highest, row[0] or 0)
            for snapshot in ("before_data", "after_data"):
                terms, values = _member_where(entry, key, snapshot=snapshot)
                where = " AND " + " AND ".join(terms) if terms else ""
                row = connection.execute(f"SELECT MAX(json_extract({snapshot}, '$.id')) FROM changes WHERE kind=?{where}",
                                         [member, *values]).fetchone()
                highest = max(highest, row[0] or 0)
        terms = ["kind=?", "target_id=?"]
        values = [kind, desired["id"]]
        if specs[kind]["scoped"]:
            terms.append("project_id=?")
            values.append(desired["project_id"])
        for snapshot in ("before_data", "after_data"):
            row = connection.execute(f"SELECT MAX(json_extract({snapshot}, '$.{field}')) FROM changes WHERE {' AND '.join(terms)}",
                                     values).fetchone()
            highest = max(highest, row[0] or 0)
        result[field] = highest
    return result

"""通用记录 CRUD：写入方须先开启事务；不提交，不读取配置或执行内容检测。"""

import json
from difflib import get_close_matches
from functools import partial

from layerweave.support.values import same_value
from layerweave.support.transaction import require_session
from layerweave.support.feedback import InputError
from layerweave.support.positions import PositionMath, numeric_position
from layerweave.support.storage.journal import append_change, json_text
from layerweave.support.storage.errors import execute
from .tables import SPECS, get_spec
from .binary import blob_fields, normalize_binary, decode_binary
from .snapshot import read_snapshot


def _spec(kind, *, writing=False, connection=None):
    return get_spec(connection, kind, writing=writing)


def _scope(spec, project_id):
    if spec["scoped"] and project_id is None:
        raise ValueError("按项目管理的记录需要 project_id")
    if not spec["scoped"] and project_id is not None:
        raise ValueError("此种记录使用独立 id；项目条件请放入 filters 的实际字段中")


def _encode(spec, data):
    if not isinstance(data, dict):
        raise TypeError("data 必须是字段字典")
    unknown = set(data) - set(spec["fields"])
    if unknown:
        suggestions = {}
        for key in sorted(unknown):
            if key == "start" and "begin" in spec["fields"]:
                suggestions[key] = "begin"
            else:
                close = get_close_matches(key, spec["fields"], n=1, cutoff=0.75)
                if close:
                    suggestions[key] = close[0]
        raise InputError(f"不能写入这些字段：{', '.join(sorted(unknown))}", code="unknown_fields",
                         field=", ".join(sorted(unknown)), allowed=list(spec["fields"]), suggestions=suggestions)
    data = normalize_binary(spec, data)
    return {
        key: (None if spec["table"] == "layers" and key == "axis" and value is None else json_text(value))
        if key in spec["json"] else value
        for key, value in data.items()
    }


def _decode(spec, row, connection=None):
    if row is None:
        return None
    record = dict(row)
    for key in spec["json"]:
        if record[key] is not None:
            record[key] = json.loads(record[key])
    if spec["table"] == "changes" and connection is not None:
        historical = get_spec(connection, record["kind"], historical=True)
        for key in ("before_data", "after_data"):
            record[key] = decode_binary(historical, record[key])
    return record


def _encode_create(spec, data):
    if not isinstance(data, dict) or spec.get("id_source", "auto") != "provided":
        return _encode(spec, data)
    values = dict(data)
    id = values.pop("id", None)
    if type(id) is not int or id < 1:
        raise InputError("此表由调用方提供编号，创建时 data.id 需要正整数", code="provided_id", field="id")
    return {"id": id, **_encode(spec, values)}


def _where(spec, project_id, id, filters):
    _scope(spec, project_id)
    terms, values = [], []
    if spec["scoped"]:
        terms.append('"project_id" = ?')
        values.append(project_id)
    if id is not None:
        terms.append('"id" = ?')
        values.append(id)
    allowed = {"id", *spec["fields"], *spec["extra"]}
    if spec["scoped"]:
        allowed.add("project_id")
    excluded = set(spec["json"]) | blob_fields(spec)
    for key, value in (filters or {}).items():
        if key not in allowed or key in excluded:
            raise InputError(f"不支持此筛选字段：{key}；当前支持非 JSON/BLOB 列的等值和空值筛选", code="unknown_filter",
                             field=f"filters.{key}", allowed=sorted(allowed - excluded))
        if value is None:
            terms.append(f'"{key}" IS NULL')
        else:
            terms.append(f'"{key}" = ?')
            values.append(value)
    return (" WHERE " + " AND ".join(terms) if terms else ""), values


def read(connection, kind, *, project_id=None, id=None, filters=None):
    """按 id 返回单条或 None；不传 id 返回列表。JSON 字段解码为 Python 值。"""
    with read_snapshot(connection):
        spec = _spec(kind, connection=connection)
        where, values = _where(spec, project_id, id, filters)
        cursor = connection.execute(
            f'SELECT * FROM "{spec["table"]}"{where} ORDER BY {spec["order"]}', values,
        )
        if id is not None:
            return _decode(spec, cursor.fetchone(), connection)
        return [_decode(spec, row, connection) for row in cursor.fetchall()]


def _positions(connection, values, project_id, before=None, math=None):
    if not ({"begin", "end", "layer"} & values.keys()):
        return values
    fields = {name for name in ("begin", "end") if name in values}
    candidate = dict(values)
    if before is not None and "layer" in values and values["layer"] != before["layer"]:
        fields.update(("begin", "end"))
        for name in fields:
            candidate.setdefault(name, before[name])
    layer = candidate.get("layer", (before or {}).get("layer"))
    fields = {name for name in fields if numeric_position(candidate[name])}
    if layer is None or not fields:
        return candidate
    math = math or PositionMath(partial(read, connection), project_id)
    try:
        math.precision(layer)
    except KeyError:
        return candidate  # 缺失引用仍由 SQLite 外键报告，不猜测轴。
    for name in fields:
        candidate[name] = math.snap(layer, candidate[name])
    return candidate


def create(connection, kind, data, *, operation_id, project_id=None, position_math=None):
    """创建记录及日志，返回新记录和变更描述；调用方提交或回滚。"""
    require_session(connection, operation_id)
    spec = _spec(kind, writing=True, connection=connection)
    _scope(spec, project_id)
    values = _encode_create(spec, data)
    if kind == "object":
        values = _positions(connection, values, project_id, math=position_math)
    return _insert(connection, kind, spec, values, operation_id=operation_id, project_id=project_id)


def _insert(connection, kind, spec, values, *, operation_id, project_id=None):
    """插入已编码字段并统一发号/记日志；迁移复用此处保留已有坐标数值。"""
    require_session(connection, operation_id)
    from layerweave.support.numbering import allocate
    from layerweave.support.numbering.registry import entry_for
    from layerweave.support.numbering.state import advance_member_counter, preserve_counters
    values = dict(values)
    if spec["scoped"]:
        values["project_id"] = project_id
    supplied = "id" in values
    member = entry_for(connection, kind)
    if not supplied and member is not None:
        parameters = {field: column["default"] for field, column in spec.get("columns", {}).items() if "default" in column}
        identity = allocate(member[0], data={**parameters, **values})
        if set(identity) - {"id", "project_id"} or ("project_id" in identity and identity["project_id"] != project_id):
            raise InputError("发号规则返回的身份与目标表的项目范围不一致", code="numbering_result")
        values["id"] = identity["id"]
    elif not supplied and spec["scoped"]:
        raise InputError("按项目自动发号的表需要所属发号词条", code="numbering_membership")
    if values:
        columns = ", ".join(f'"{key}"' for key in values)
        placeholders = ", ".join("?" for _ in values)
        cursor = execute(connection,
            f'INSERT INTO "{spec["table"]}" ({columns}) VALUES ({placeholders})',
            list(values.values()), kind=kind, record=values, action="create",
        )
    else:
        cursor = execute(connection, f'INSERT INTO "{spec["table"]}" DEFAULT VALUES', (),
                         kind=kind, record=values, action="create")
    record_id = values.get("id", cursor.lastrowid)
    record = read(connection, kind, project_id=project_id, id=record_id)
    preserved = preserve_counters(connection, kind, record)
    advanced = {field: value for field, value in preserved.items() if value != record.get(field)}
    if advanced:
        where, keys = _where(spec, project_id, record_id, None)
        assignments = ", ".join(f'"{field}"=?' for field in advanced)
        connection.execute(f'UPDATE "{spec["table"]}" SET {assignments}{where}', [*advanced.values(), *keys])
        record = read(connection, kind, project_id=project_id, id=record_id)
    if supplied:
        advance_member_counter(connection, kind, record)
    change = append_change(connection, operation_id, kind, None, record)
    return record, change


def update(connection, kind, id, data, *, operation_id, project_id=None, position_math=None):
    """修改明确传入的字段；JSON 字段整体替换。记录缺失或无变化时不记日志。"""
    require_session(connection, operation_id)
    spec = _spec(kind, writing=True, connection=connection)
    if id is None:
        raise ValueError("update 需要明确的 id")
    values = _encode(spec, data)
    before = read(connection, kind, project_id=project_id, id=id)
    if before is None or not values:
        return before, None
    if kind == "object":
        values = _positions(connection, values, project_id, before, position_math)
    from layerweave.support.numbering.state import check_counter_update, cluster_identity, advance_member_counter
    check_counter_update(connection, kind, before, values)
    moved_scope = cluster_identity(connection, kind, before) != cluster_identity(connection, kind, {**before, **values})
    changed = {}
    for key, value in values.items():
        if key in spec["json"]:
            # 比较真正要保存的 JSON 值，兼容 tuple→list、非字符串键等编码转换。
            candidate = json.loads(value) if value is not None else None
            equal = same_value(before[key], candidate)
        else:
            # 普通 SQL 数值列会规范化 int/float/bool；不把 0 与 0.0 当成内容变化。
            equal = before[key] == value
        if not equal:
            changed[key] = value
    if not changed:
        return before, None
    where, key_values = _where(spec, project_id, id, None)
    assignments = ", ".join(f'"{key}" = ?' for key in changed)
    execute(connection,
        f'UPDATE "{spec["table"]}" SET {assignments}{where}',
        [*changed.values(), *key_values], kind=kind, record={**before, **values}, action="update",
    )
    after = read(connection, kind, project_id=project_id, id=id)
    if moved_scope:
        advance_member_counter(connection, kind, after)
    change = append_change(connection, operation_id, kind, before, after)
    return after, change


def delete(connection, kind, id, *, operation_id, project_id=None):
    """仅删除指定记录，返回删除前的数据；记录不存在时返回 None 且不记日志。"""
    require_session(connection, operation_id)
    spec = _spec(kind, writing=True, connection=connection)
    if id is None:
        raise ValueError("delete 需要明确的 id")
    before = read(connection, kind, project_id=project_id, id=id)
    if before is None:
        return None, None
    where, values = _where(spec, project_id, id, None)
    execute(connection, f'DELETE FROM "{spec["table"]}"{where}', values, kind=kind, record=before, action="delete")
    change = append_change(connection, operation_id, kind, before, None)
    return before, change

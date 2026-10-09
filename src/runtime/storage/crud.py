"""通用记录 CRUD：写入方须先开启事务；不提交，不读取配置或执行内容检测。"""

import json
from difflib import get_close_matches
from functools import partial

from ..values import same_value
from ..feedback import InputError
from ..positions import PositionMath, numeric_position
from .database import allocate_id
from .journal import append_change, json_text
from .errors import execute


# 字段列表只用于确定 SQL 列和托管字段，不校验封装内容。
SPECS = {
    "project": {
        "table": "projects", "fields": ("name", "tips"),
        "extra": ("max_id",), "json": (), "scoped": False, "order": '"id"',
    },
    "layer": {
        "table": "layers", "fields": ("name", "type", "config_ref", "father", "axis", "tips"),
        "extra": (), "json": ("axis",), "scoped": True, "order": '"id"',
    },
    "object": {
        "table": "objects", "fields": ("name", "config_ref", "layer", "begin", "end", "information", "tips"),
        "extra": (), "json": ("information",), "scoped": True, "order": '"begin", "end", "id"',
    },
    "bind": {
        "table": "binds", "fields": (
            "source_kind", "source_project_id", "source_id",
            "target_kind", "target_project_id", "target_id", "tips",
        ),
        "extra": (), "json": (), "scoped": False, "order": '"id"',
    },
    "change": {
        "table": "changes", "fields": (),
        "extra": ("operation_id", "created_at", "kind", "project_id", "target_id", "action", "before_data", "after_data"),
        "json": ("before_data", "after_data"), "scoped": False, "order": '"id"',
    },
}


def _spec(kind, *, writing=False):
    if kind not in SPECS:
        allowed = [name for name in SPECS if not writing or name != "change"]
        suffix = "；change 仅支持 read" if not writing else ""
        raise InputError(f"未知 kind：{kind}{suffix}", code="unknown_kind", field="kind", allowed=allowed)
    if writing and kind == "change":
        raise InputError("改动日志由写操作记录，change 仅支持 read", code="readonly_kind", field="action", allowed=["read"])
    return SPECS[kind]


def _scope(spec, project_id):
    if spec["scoped"] and project_id is None:
        raise ValueError("层和对象需要 project_id")
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
    return {
        key: (None if key == "axis" and value is None else json_text(value))
        if key in spec["json"] else value
        for key, value in data.items()
    }


def _decode(spec, row):
    if row is None:
        return None
    record = dict(row)
    for key in spec["json"]:
        if record[key] is not None:
            record[key] = json.loads(record[key])
    return record


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
    for key, value in (filters or {}).items():
        if key not in allowed or key in spec["json"]:
            raise InputError(f"不支持此筛选字段：{key}；当前支持普通列的等值和空值筛选", code="unknown_filter",
                             field=f"filters.{key}", allowed=sorted(allowed - set(spec["json"])))
        if value is None:
            terms.append(f'"{key}" IS NULL')
        else:
            terms.append(f'"{key}" = ?')
            values.append(value)
    return (" WHERE " + " AND ".join(terms) if terms else ""), values


def read(connection, kind, *, project_id=None, id=None, filters=None):
    """按 id 返回单条或 None；不传 id 返回列表。JSON 字段解码为 Python 值。"""
    spec = _spec(kind)
    where, values = _where(spec, project_id, id, filters)
    cursor = connection.execute(
        f'SELECT * FROM "{spec["table"]}"{where} ORDER BY {spec["order"]}', values,
    )
    if id is not None:
        return _decode(spec, cursor.fetchone())
    return [_decode(spec, row) for row in cursor.fetchall()]


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
    spec = _spec(kind, writing=True)
    _scope(spec, project_id)
    values = _encode(spec, data)
    if kind == "object":
        values = _positions(connection, values, project_id, math=position_math)
    if spec["scoped"]:
        values = {"project_id": project_id, "id": allocate_id(connection, project_id), **values}
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
    record_id = values["id"] if spec["scoped"] else cursor.lastrowid
    record = read(connection, kind, project_id=project_id, id=record_id)
    change = append_change(connection, operation_id, kind, None, record)
    return record, change


def update(connection, kind, id, data, *, operation_id, project_id=None, position_math=None):
    """修改明确传入的字段；JSON 字段整体替换。记录缺失或无变化时不记日志。"""
    spec = _spec(kind, writing=True)
    if id is None:
        raise ValueError("update 需要明确的 id")
    values = _encode(spec, data)
    before = read(connection, kind, project_id=project_id, id=id)
    if before is None or not values:
        return before, None
    if kind == "object":
        values = _positions(connection, values, project_id, before, position_math)
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
    change = append_change(connection, operation_id, kind, before, after)
    return after, change


def delete(connection, kind, id, *, operation_id, project_id=None):
    """仅删除指定记录，返回删除前的数据；记录不存在时返回 None 且不记日志。"""
    spec = _spec(kind, writing=True)
    if id is None:
        raise ValueError("delete 需要明确的 id")
    before = read(connection, kind, project_id=project_id, id=id)
    if before is None:
        return None, None
    where, values = _where(spec, project_id, id, None)
    execute(connection, f'DELETE FROM "{spec["table"]}"{where}', values, kind=kind, record=before, action="delete")
    change = append_change(connection, operation_id, kind, before, None)
    return before, change

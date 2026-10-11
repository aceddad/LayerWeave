"""托管表声明：内置表保持原结构，工具声明随数据库保存，无工具代码依赖。"""
from copy import deepcopy
import json
import math
import re

from layerweave.core.values import same_value
from layerweave.support.feedback import InputError


CATALOG = "_layerweave_tables"
SPECS = {
    "project": {"table": "projects", "fields": ("name", "tips"), "extra": ("max_id",),
                "json": (), "scoped": False, "order": '"id"', "references": []},
    "layer": {"table": "layers", "fields": ("name", "type", "config_ref", "father", "axis", "tips"),
              "extra": (), "json": ("axis",), "scoped": True, "order": '"id"',
              "references": [{"fields": ["project_id"], "kind": "project"},
                             {"fields": ["project_id", "father"], "kind": "layer"}]},
    "object": {"table": "objects", "fields": ("name", "config_ref", "layer", "begin", "end", "information", "tips"),
               "extra": (), "json": ("information",), "scoped": True, "order": '"begin", "end", "id"',
               "references": [{"fields": ["project_id"], "kind": "project"},
                              {"fields": ["project_id", "layer"], "kind": "layer"}]},
    "bind": {"table": "binds", "fields": ("source_kind", "source_project_id", "source_id",
                                          "target_kind", "target_project_id", "target_id", "tips"),
             "extra": (), "json": (), "scoped": False, "order": '"id"', "references": []},
    "change": {"table": "changes", "fields": (),
               "extra": ("operation_id", "created_at", "kind", "project_id", "target_id", "action", "before_data", "after_data", "undo_of"),
               "json": ("before_data", "after_data"), "scoped": False, "order": '"id"', "references": []},
}


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def _exists(connection, table):
    return connection.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone() is not None


def table_specs(connection=None):
    """返回内置与本库扩展表的声明副本；普通读取不会自动建表或修改数据库。"""
    result = deepcopy(SPECS)
    if connection is not None and _exists(connection, CATALOG):
        result.update((row[0], json.loads(row[1])) for row in connection.execute(
            f"SELECT kind, definition FROM {quote(CATALOG)} ORDER BY kind"))
    for spec in result.values():
        spec.setdefault("id_source", "auto")
    return result


def get_spec(connection, kind, *, writing=False):
    specs = SPECS if kind in SPECS else table_specs(connection)
    if kind not in specs:
        raise InputError(f"未知 kind：{kind}" + ("；change 仅支持 read" if not writing else ""),
                         code="unknown_kind", field="kind",
                         allowed=[name for name in specs if not writing or name != "change"])
    if writing and kind == "change":
        raise InputError("改动日志由写操作记录，change 仅支持 read", code="readonly_kind", field="action", allowed=["read"])
    return specs[kind]


def _identifier(name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
        raise InputError("表、种类和字段名使用字母开头的字母、数字、下划线", code="table_definition", field="name")
    return name


def _column(raw):
    column = {"type": raw} if isinstance(raw, str) else dict(raw)
    if set(column) - {"type", "nullable", "default"}:
        raise InputError("列声明支持 type、nullable、default", code="table_definition")
    column.setdefault("nullable", True)
    if column.get("type") not in {"INTEGER", "REAL", "TEXT", "JSON"} or type(column["nullable"]) is not bool:
        raise InputError("列类型使用 INTEGER、REAL、TEXT、JSON；nullable 使用布尔值", code="table_definition")
    if "default" in column:
        value, kind = column["default"], column["type"]
        if value is None:
            if not column["nullable"] and kind != "JSON":
                raise InputError("非空列不能使用 NULL 默认值", code="table_definition")
        elif kind == "TEXT" and not isinstance(value, str):
            raise InputError("TEXT 默认值需要字符串", code="table_definition")
        elif kind == "INTEGER":
            if not isinstance(value, int):
                raise InputError("INTEGER 默认值需要整数", code="table_definition")
            column["default"] = int(value)
        elif kind == "REAL":
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise InputError("REAL 默认值需要有限数值", code="table_definition")
            column["default"] = float(value)
        json.dumps(column["default"], allow_nan=False)
    return column


def _definition(kind, definition):
    _identifier(kind)
    if kind.lower() in SPECS:
        raise InputError("工具声明不能覆盖内置种类", code="table_definition", field="kind")
    if set(definition) - {"table", "fields", "scoped", "references", "id_source"}:
        raise InputError("表声明支持 table、fields、scoped、references、id_source", code="table_definition")
    table = _identifier(definition.get("table", "tool_" + kind))
    scoped = definition.get("scoped", True)
    if type(scoped) is not bool:
        raise InputError("scoped 使用布尔值", code="table_definition", field="scoped")
    id_source = definition.get("id_source", "auto")
    if id_source not in {"auto", "provided"}:
        raise InputError("id_source 使用 auto 或 provided", code="table_definition", field="id_source")
    columns = {}
    for field, declaration in definition.get("fields", {}).items():
        _identifier(field)
        if field.lower() in {"id", "project_id"} or field.lower() in {name.lower() for name in columns}:
            raise InputError("id/project_id 由支撑管理；字段名不能仅大小写不同", code="table_definition", field=field)
        columns[field] = _column(declaration)
    refs = [{"fields": ["project_id"], "kind": "project"}] if scoped else []
    for ref in definition.get("references", []):
        if set(ref) != {"fields", "kind"} or not isinstance(ref["fields"], (list, tuple)):
            raise InputError("引用声明需要 fields 列表和目标 kind", code="table_definition", field="references")
        candidate = {"fields": list(ref["fields"]), "kind": ref["kind"]}
        if candidate not in refs:
            refs.append(candidate)
    return {"table": table, "fields": list(columns), "columns": columns, "extra": [],
            "json": [name for name, column in columns.items() if column["type"] == "JSON"],
            "scoped": scoped, "id_source": id_source, "order": '"id"', "references": refs}


def _column_sql(name, column):
    sql = quote(name) + " " + ("TEXT" if column["type"] == "JSON" else column["type"])
    if not column["nullable"]:
        sql += " NOT NULL"
    if "default" in column:
        value = column["default"]
        if column["type"] == "JSON":
            value = json.dumps(value, ensure_ascii=False, allow_nan=False)
        literal = "NULL" if value is None else "'" + value.replace("'", "''") + "'" if isinstance(value, str) else str(value)
        sql += " DEFAULT " + literal
    return sql


def _create_sql(spec, specs):
    columns = ["project_id INTEGER NOT NULL", "id INTEGER NOT NULL"] if spec["scoped"] else ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
    columns += [_column_sql(name, column) for name, column in spec["columns"].items()]
    if spec["scoped"]:
        columns.append("PRIMARY KEY (project_id, id)")
    for ref in spec["references"]:
        target = specs[ref["kind"]]
        keys = ["project_id", "id"] if target["scoped"] else ["id"]
        columns.append(f'FOREIGN KEY ({", ".join(map(quote, ref["fields"]))}) REFERENCES '
                       f'{quote(target["table"])} ({", ".join(map(quote, keys))})')
    return f'CREATE TABLE {quote(spec["table"])} ({", ".join(columns)})'


def register_tables(connection, definitions):
    """原子创建一组工具表，或为已登记表新增列；声明持久化，不记为业务内容操作。"""
    from layerweave.support.transaction import transaction

    proposed = {kind: _definition(kind, raw) for kind, raw in definitions.items()}
    with transaction(connection):
        existing = table_specs(connection)
        specs = {**existing, **proposed}
        names = [spec["table"].lower() for spec in specs.values()]
        if len(set(names)) != len(names) or CATALOG.lower() in names or any(name.startswith("sqlite_") for name in names):
            raise InputError("表名重复或使用了保留名称", code="table_definition", field="table")
        for kind, spec in proposed.items():
            for ref in spec["references"]:
                target = specs.get(ref["kind"])
                available = {name for name, col in spec["columns"].items() if col["type"] == "INTEGER"} | {"id"}
                if spec["scoped"]:
                    available.add("project_id")
                if target is None or ref["kind"] == "change" or len(ref["fields"]) != (2 if target["scoped"] else 1) or any(name not in available for name in ref["fields"]):
                    raise InputError(f"{kind} 的引用需要对应目标身份的整数列", code="table_definition", field="references")
            old = existing.get(kind)
            if old is not None:
                if any(not same_value(spec[name], old[name]) for name in ("table", "scoped", "references", "id_source")) or any(
                    name not in spec["columns"] or not same_value(col, spec["columns"][name]) for name, col in old["columns"].items()):
                    raise InputError(f"{kind} 已登记；允许新增列，已有列、身份和引用保持不变", code="table_definition_changed")
            elif _exists(connection, spec["table"]):
                raise InputError(f"{spec['table']} 已存在但未登记；请明确迁移到新的托管表", code="table_exists")
        if proposed:
            connection.execute(f"CREATE TABLE IF NOT EXISTS {quote(CATALOG)} (kind TEXT PRIMARY KEY, definition TEXT NOT NULL)")
        for kind, spec in proposed.items():
            old = existing.get(kind)
            if old is None:
                connection.execute(_create_sql(spec, specs))
            else:
                for name, col in spec["columns"].items():
                    if name not in old["columns"]:
                        if not col["nullable"] and "default" not in col:
                            raise InputError("新增非空列需要默认值，以保留已有记录", code="table_definition", field=name)
                        connection.execute(f'ALTER TABLE {quote(spec["table"])} ADD COLUMN {_column_sql(name, col)}')
            connection.execute(f'INSERT INTO {quote(CATALOG)} (kind,definition) VALUES (?,?) '
                               'ON CONFLICT(kind) DO UPDATE SET definition=excluded.definition',
                               (kind, json.dumps(spec, ensure_ascii=False, allow_nan=False)))
        if proposed:
            from layerweave.support.numbering.registry import numbering_entries, persist_entries
            persist_entries(connection, numbering_entries(connection))
    return deepcopy(proposed)


def normalize_record(connection, kind, record):
    """旧快照缺少后来新增的列时，补数据库声明的默认值；不改原日志。"""
    if record is None or kind in SPECS:
        return record
    result = deepcopy(record)
    for name, column in get_spec(connection, kind)["columns"].items():
        if name not in result:
            result[name] = deepcopy(column.get("default"))
    return result

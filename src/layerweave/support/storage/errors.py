"""仅在 SQL 约束失败时解释引用原因；在事务回滚前读取失败现场。"""

import sqlite3

from layerweave.support.feedback import target
from layerweave.core.identity import identity_key
from .tables import table_specs, quote
from .references import missing_references, dependent_records


def _missing_message(kind, ref, key):
    if key[0] == "project":
        return f"项目 {key[2]} 不存在"
    if kind in {"layer", "object"} and key[0] == "layer":
        return f"{'父层' if kind == 'layer' else '所属层'} ({key[1]}, {key[2]}) 不存在"
    return f"引用 {key[0]} ({key[1]}, {key[2]}) 不存在"


def _declared_reference_failure(connection, kind, record, action):
    specs = table_specs(connection)
    if action != "delete":
        for ref, key in missing_references(connection, kind, record, specs):
            return _missing_message(kind, ref, key), ref["fields"][-1], target(*key)
    else:
        key = identity_key(kind, record.get("project_id"), record["id"])
        for dependent, row, ref in dependent_records(connection, key, specs):
            referenced_by = target(dependent, row.get("project_id"), row["id"])
            return (f"不能删除 {kind}：仍被 {dependent} ({referenced_by['project_id']}, {row['id']}) 的 {','.join(ref['fields'])} 引用",
                    "id", referenced_by)
    return None


def _reference_failure(connection, kind, record, action):
    project_id = record.get("project_id")
    if action != "delete":
        if kind in {"layer", "object"}:
            if connection.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone() is None:
                return (f"项目 {project_id} 不存在", "project_id", target("project", None, project_id))
            field = "father" if kind == "layer" else "layer"
            id = record.get(field)
            if id is not None and connection.execute(
                "SELECT 1 FROM layers WHERE project_id=? AND id=?", (project_id, id),
            ).fetchone() is None:
                label = "父层" if kind == "layer" else "所属层"
                return (f"{label} ({project_id}, {id}) 不存在", field, target("layer", project_id, id))
    else:
        if kind == "layer":
            references = [("objects", "layer", project_id, record["id"]),
                          ("layers", "father", project_id, record["id"])]
            subject = f"层 ({project_id}, {record['id']})"
        elif kind == "project":
            references = [("layers", "project_id", record["id"], record["id"]),
                          ("objects", "project_id", record["id"], record["id"])]
            subject = f"项目 {record['id']}"
        else:
            references = []
        for table, field, owner, value in references:
            row = connection.execute(
                f'SELECT project_id, id FROM "{table}" WHERE project_id=? AND "{field}"=? LIMIT 1',
                (owner, value),
            ).fetchone()
            if row is not None:
                reference = target(table[:-1], row[0], row[1])
                return (f"不能删除{subject}：仍被 {reference['kind']} ({row[0]}, {row[1]}) 的 {field} 引用",
                        "id", reference)
    return _declared_reference_failure(connection, kind, record, action)


def execute(connection, sql, parameters, *, kind, record, action):
    try:
        return connection.execute(sql, parameters)
    except sqlite3.IntegrityError as error:
        code = getattr(error, "sqlite_errorcode", None)
        details = {"target": target(kind, record.get("project_id"), record.get("id"))}
        if code == sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY:
            explanation = _reference_failure(connection, kind, record, action)
            if explanation is not None:
                message, field, reference = explanation
                error.args = (message,)
                details.update(code="reference_in_use" if action == "delete" else "missing_reference",
                               field=field, reference=reference)
        elif code == sqlite3.SQLITE_CONSTRAINT_NOTNULL:
            field = str(error).rsplit(".", 1)[-1]
            error.args = (f"字段 {field} 缺失或为 None，数据库要求提供非空值",)
            details.update(code="null_field", field=field)
        error.details = details
        raise


def commit(connection):
    """提交失败时，在上层回滚前解释延迟外键；成功路径不扫描引用。"""
    try:
        connection.commit()
    except sqlite3.IntegrityError as error:
        if getattr(error, "sqlite_errorcode", None) == sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY:
            violations, checked = [], set()
            specs = table_specs(connection)
            kinds = {spec["table"]: kind for kind, spec in specs.items()}
            for table, rowid, parent, _ in connection.execute("PRAGMA foreign_key_check"):
                if table not in kinds or (table, rowid) in checked:
                    continue
                checked.add((table, rowid))
                kind = kinds[table]
                row = dict(connection.execute(f'SELECT * FROM {quote(table)} WHERE rowid=?', (rowid,)).fetchone())
                owner = target(kind, row.get("project_id"), row["id"])
                for ref, key in missing_references(connection, kind, row, specs):
                    message = _missing_message(kind, ref, key)
                    violations.append({"target": owner, "code": "missing_reference",
                                       "field": ref["fields"][-1], "reference": target(*key),
                                       "message": f"{kind} ({owner['project_id']}, {row['id']})：{message}"})
            if violations:
                first = violations[0]
                error.args = (f"无法提交：{first['message']}；共 {len(violations)} 处引用缺失",)
                error.details = {key: first[key] for key in ("target", "code", "field", "reference")}
                error.details["violations"] = violations
        raise

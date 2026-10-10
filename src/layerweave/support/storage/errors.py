"""仅在 SQL 约束失败时解释引用原因；在事务回滚前读取失败现场。"""

import sqlite3

from layerweave.support.feedback import target


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
    return None


def execute(connection, sql, parameters, *, kind, record, action):
    try:
        return connection.execute(sql, parameters)
    except sqlite3.IntegrityError as error:
        code = getattr(error, "sqlite_errorcode", None)
        details = {"target": target(kind, record.get("project_id"), None if action == "create" else record.get("id"))}
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
            violations = []
            for table, rowid, parent, _ in connection.execute("PRAGMA foreign_key_check"):
                if table not in {"layers", "objects"} or parent not in {"projects", "layers"}:
                    continue
                kind = table[:-1]
                field = "father" if kind == "layer" else "layer"
                project_id, id, layer_id = connection.execute(
                    f'SELECT project_id, id, "{field}" FROM "{table}" WHERE rowid=?', (rowid,),
                ).fetchone()
                if parent == "projects":
                    field, reference = "project_id", target("project", None, project_id)
                    message = f"项目 {project_id} 不存在"
                else:
                    reference = target("layer", project_id, layer_id)
                    label = "父层" if kind == "layer" else "所属层"
                    message = f"{label} ({project_id}, {layer_id}) 不存在"
                violations.append({"target": target(kind, project_id, id), "code": "missing_reference",
                                   "field": field, "reference": reference,
                                   "message": f"{kind} ({project_id}, {id})：{message}"})
            if violations:
                first = violations[0]
                error.args = (f"无法提交：{first['message']}；共 {len(violations)} 处引用缺失",)
                error.details = {key: first[key] for key in ("target", "code", "field", "reference")}
                error.details["violations"] = violations
        raise

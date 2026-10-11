"""写会话中的记录原语；事务、发号、日志、落点都由支撑层维护。"""
from .storage.crud import read, create, update, delete
from .storage import crud
from .storage.restoration import restore as _restore
from .transaction import require_session, defer_references
from .storage.tables import table_specs, normalize_record
from .storage.references import dependent_records, reference_key, id_occupants


def writable_fields(kind, *, connection=None):
    """返回记录允许写入的字段名，不暴露 SQL 表和编码细节。"""
    return crud._spec(kind, writing=True, connection=connection)["fields"]


def create_exact(connection, kind, data, *, operation_id, project_id=None):
    """显式保留原值的复制/迁移入口；仍统一发号和记录日志。"""
    require_session(connection, operation_id)
    spec = crud._spec(kind, writing=True, connection=connection)
    crud._scope(spec, project_id)
    return crud._insert(connection, kind, spec, crud._encode(spec, data),
                        operation_id=operation_id, project_id=project_id)


def restore(connection, kind, id, record, *, operation_id, project_id=None, undo_of=None, fields=None):
    """按原身份恢复完整快照或顶层字段。调用方决定冲突策略；支撑负责实际写入。"""
    require_session(connection, operation_id)
    spec = crud._spec(kind, writing=True, connection=connection)
    crud._scope(spec, project_id)
    if type(id) is not int or id < 1:
        raise ValueError("恢复需要明确的正整数编号")
    if record is not None and (record.get("id") != id or (spec["scoped"] and record.get("project_id") != project_id)):
        raise ValueError("恢复快照的身份与写入目标不一致")
    if fields is not None and set(fields) - set(spec["fields"]):
        raise ValueError("恢复字段必须是记录的可写字段")
    if fields is not None:
        current = read(connection, kind, project_id=project_id, id=id)
        if record is None or current is None:
            raise ValueError("fields 只用于恢复已有记录的顶层字段")
        if not fields:
            return current, None
    item = {"restore": record}
    if fields is not None:
        item["fields"] = fields
    change = _restore(connection, (kind, project_id, id), item, operation_id, undo_of)
    return read(connection, kind, project_id=project_id, id=id), change

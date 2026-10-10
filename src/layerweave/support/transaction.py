"""写入会话和结构保证。只处理身份、事务和父链，不检查封装内容。"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from uuid import uuid4

from .feedback import InputError, target


@dataclass
class WriteSession:
    connection: object
    operation_id: str = field(default_factory=lambda: uuid4().hex)
    writing: bool = True
    _changes: list = field(default_factory=list, init=False, repr=False)

    @property
    def changes(self):
        return deepcopy(self._changes)

    def read(self, kind, **scope):
        from .storage.crud import read
        return read(self.connection, kind, **scope)

    def create(self, kind, data, **scope):
        from .records import create
        return create(self.connection, kind, data, operation_id=self.operation_id, **scope)[0]

    def create_exact(self, kind, data, **scope):
        from .records import create_exact
        return create_exact(self.connection, kind, data, operation_id=self.operation_id, **scope)[0]

    def update(self, kind, id, data, **scope):
        from .records import update
        return update(self.connection, kind, id, data, operation_id=self.operation_id, **scope)[0]

    def delete(self, kind, id, **scope):
        from .records import delete
        return delete(self.connection, kind, id, operation_id=self.operation_id, **scope)[0]

    def restore(self, kind, id, record, **scope):
        from .records import restore
        return restore(self.connection, kind, id, record, operation_id=self.operation_id, **scope)[0]

    def defer_references(self):
        defer_references(self.connection)


_active = ContextVar("layerweave_write_session", default=None)


def require_session(connection, operation_id=None):
    session = _active.get()
    if session is None or session.connection is not connection or not session.writing:
        raise RuntimeError("写入需要通过 layerweave.support.transaction.transaction 或 run_operation 开启写会话")
    if operation_id is not None and operation_id != session.operation_id:
        raise ValueError("operation_id 必须属于当前写会话")
    return session


def record_change(connection, operation_id, change):
    require_session(connection, operation_id)._changes.append(deepcopy(change))


def defer_references(connection):
    require_session(connection)
    connection.execute("PRAGMA defer_foreign_keys = ON")


def _check_parents(session):
    starts = {(c["project_id"], c["id"]) for c in session._changes if c["kind"] == "layer"
              and c["after"] is not None and (c["before"] is None or c["before"]["father"] != c["after"]["father"])}
    checked = set()
    for project_id, id in starts:
        path, seen = [], set()
        cursor = id
        while cursor is not None and (project_id, cursor) not in checked:
            if cursor in seen:
                raise InputError(f"层 ({project_id}, {id}) 的父链成环", code="father_cycle", field="father",
                                 target=target("layer", project_id, id), cycle=[*path[path.index(cursor):], cursor])
            seen.add(cursor)
            path.append(cursor)
            row = session.read("layer", project_id=project_id, id=cursor)
            if row is None:
                break  # 引用存在性由外键处理；本批已删除目标也不再参与父链。
            cursor = row["father"]
        checked.update((project_id, item) for item in path)


@contextmanager
def transaction(connection, *, writing=True, _operation_id=None):
    """独占本次事务；成功提交实际记录/发号/日志，异常共同回滚，不接管调用方事务。"""
    if connection.in_transaction:
        raise ValueError("操作入口需要没有待提交操作的连接；批量写入请在同一写会话内组合")
    session = WriteSession(connection, _operation_id or uuid4().hex, writing)
    token = _active.set(session)
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE" if writing else "BEGIN")
            yield session
            _check_parents(session)
    finally:
        _active.reset(token)

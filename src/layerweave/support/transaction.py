"""写入会话和结构保证。只处理身份、事务和父链，不检查封装内容。"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from uuid import uuid4

from .feedback import InputError, target
from .storage.errors import commit
from .storage._metadata import metadata_scope


@dataclass
class WriteSession:
    connection: object
    operation_id: str = field(default_factory=lambda: uuid4().hex)
    writing: bool = True
    _changes: list = field(default_factory=list, init=False, repr=False)
    _numbering: list = field(default_factory=list, init=False, repr=False)

    @property
    def changes(self):
        return deepcopy(self._changes)

    @property
    def numbering(self):
        """当前事务的领号信息；只有事务成功后才是已提交的结果。"""
        return deepcopy(self._numbering)

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


def require_write_session(write):
    """事务内工具只接受当前的写会话，不开启或提交事务。"""
    if _active.get() is not write or not isinstance(write, WriteSession) or not write.writing:
        raise ValueError("*_in_session 需要当前 transaction/run_operation 提供的写会话")
    return write


def reject_nested_operation(connection):
    """独立操作误用于现有会话时抛出，让外层决定回滚，不包装成普通业务数据。"""
    session = _active.get()
    if session is not None and session.connection is connection:
        raise ValueError("已有 LayerWeave 会话；请使用 *_in_session(write, ...) 或 write 原语组合操作")


def current_write_session():
    """支撑组件复用当前写事务，调用方无需给每个组件重复传连接。"""
    session = _active.get()
    if session is None or not session.writing:
        raise RuntimeError("发号需要在 transaction 或 run_operation 的写会话内调用")
    return session


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


def _check_numbering(session):
    """按提交后的最终状态检查同簇占用，允许批内移走旧占用再恢复原记录。"""
    from .numbering.state import check_cluster, cluster_identity
    from .storage.tables import get_spec
    connection = session.connection
    targets = {(c["kind"], c["project_id"], c["id"]) for c in session._changes if c["after"] is not None
               and (c["before"] is None or cluster_identity(connection, c["kind"], c["before"]) !=
                    cluster_identity(connection, c["kind"], c["after"]))}
    for kind, project_id, id in targets:
        # 项目/关联日志的 project_id 是上下文，不是其记录主键的一部分。
        scope = project_id if get_spec(connection, kind)["scoped"] else None
        current = session.read(kind, project_id=scope, id=id)
        if current is not None:
            check_cluster(connection, kind, current)


@contextmanager
def transaction(connection, *, writing=True, _operation_id=None):
    """独占本次事务；成功提交实际记录/发号/日志，异常共同回滚，不接管调用方事务。"""
    if connection.in_transaction:
        raise ValueError("操作入口需要没有待提交操作的连接；批量写入请在同一写会话内组合")
    session = WriteSession(connection, _operation_id or uuid4().hex, writing)
    token = _active.set(session)
    try:
        with connection, metadata_scope(connection):
            connection.execute("BEGIN IMMEDIATE" if writing else "BEGIN")
            yield session
            _check_parents(session)
            _check_numbering(session)
            # 显式提交让错误说明能读到失败现场；异常仍由 with connection 整体回滚。
            commit(connection)
    finally:
        _active.reset(token)

"""事务/读取快照内的声明缓存；不缓存记录、计数或实际编号占用。"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class _Scope:
    connection: object
    values: dict = field(default_factory=dict)
    active: bool = True


_scopes = ContextVar("layerweave_metadata_scopes", default=())


def _current(connection):
    return next((scope for scope in reversed(_scopes.get())
                 if scope.active and scope.connection is connection), None)


@contextmanager
def metadata_scope(connection):
    """同连接嵌套读取共享缓存；不同连接隔离，最外层退出即丢弃。"""
    if _current(connection) is not None:
        yield
        return
    scope = _Scope(connection)
    token = _scopes.set((*_scopes.get(), scope))
    try:
        yield
    finally:
        scope.active = False
        scope.values.clear()
        _scopes.reset(token)


def cached(connection, name, loader):
    """内部借用只读声明；不处于受管理的读取范围时直接加载。"""
    scope = _current(connection)
    if scope is None or connection is None or not connection.in_transaction:
        return loader(connection)
    if name not in scope.values:
        scope.values[name] = loader(connection)
    return scope.values[name]


def invalidate(connection):
    """登记维护改变声明时一并刷新依赖它的元信息。"""
    scope = _current(connection)
    if scope is not None:
        scope.values.clear()

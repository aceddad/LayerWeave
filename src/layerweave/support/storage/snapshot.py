"""读取事务的最小公共实现；不依赖实体装配。"""
from contextlib import contextmanager
from ._metadata import metadata_scope


@contextmanager
def read_snapshot(connection):
    with metadata_scope(connection):
        if connection.in_transaction:
            yield  # 使用调用方的事务，不替调用方提交。
        else:
            with connection:
                connection.execute("BEGIN")
                yield

"""按日志编号连续读取业务变更；页尾延伸到完整操作，不依赖任何工具包。"""
from layerweave.support.feedback import InputError
from .snapshot import read_snapshot
from .crud import _decode
from .tables import SPECS


def change_cursor(connection):
    """当前读取快照的最后一个 changes.id；空库为 0，与项目初始加载共用 read_snapshot。"""
    with read_snapshot(connection):
        return connection.execute("SELECT COALESCE(MAX(id), 0) FROM changes").fetchone()[0]


def read_changes(connection, *, after=0, limit=100):
    """返回 changes/next_cursor/has_more；limit 是行数软上限，不拆页尾操作。"""
    if type(after) is not int or after < 0:
        raise ValueError("after 应为 change_cursor 或上次 next_cursor 返回的非负日志编号")
    if type(limit) is not int or limit < 1:
        raise ValueError("limit 应为正整数")
    with read_snapshot(connection):
        head = change_cursor(connection)
        if after > head:
            raise InputError("游标超过本库当前日志末尾，请重新加载快照与游标", code="cursor_ahead",
                             field="after", current_cursor=head)
        # 正常客户端只传接口产生的页尾；明确指出手填到一批操作中间的错误。
        row = connection.execute("SELECT operation_id FROM changes WHERE id=?", (after,)).fetchone()
        if row is not None and connection.execute(
            "SELECT 1 FROM changes WHERE operation_id=? AND id>? LIMIT 1", (row[0], after),
        ).fetchone() is not None:
            raise InputError("after 位于一次操作内部，请使用完整页的 next_cursor", code="cursor_inside_operation",
                             field="after", operation_id=row[0])
        rows = connection.execute("SELECT * FROM changes WHERE id>? ORDER BY id LIMIT ?", (after, limit + 1)).fetchall()
        if len(rows) > limit:
            last = rows[limit - 1]
            end = connection.execute("SELECT MAX(id) FROM changes WHERE operation_id=?", (last["operation_id"],)).fetchone()[0]
            rows = connection.execute("SELECT * FROM changes WHERE id>? AND id<=? ORDER BY id", (after, end)).fetchall()
        next_cursor = rows[-1]["id"] if rows else after
        return {"changes": [_decode(SPECS["change"], row, connection) for row in rows],
                "next_cursor": next_cursor, "has_more": next_cursor < head}

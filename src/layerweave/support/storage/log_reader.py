"""原始改动日志查询；不依赖历史展示或撤销策略。"""
from . import crud

def content(kind, row, connection=None):
    """发号进度是托管状态，不参与内容撤销及冲突比较。"""
    if row is None:
        return None
    from layerweave.support.numbering.state import counter_fields
    fields = counter_fields(connection, kind, row) if connection is not None else {"max_id"} if kind == "project" else set()
    return {key: value for key, value in row.items() if key not in fields}


def operation_rows(connection, operation_id):
    return crud.read(connection, "change", filters={"operation_id": operation_id})


def operation_page(connection, project_id=None, *, kind=None, id=None, limit=20, before=None):
    terms, values = [], []
    if project_id is not None:
        # 关联两端、移动前后都属于该项目的历史；日志不要求项目仍存在。
        related = ["project_id=?"]
        values.append(project_id)
        for snapshot in ("before_data", "after_data"):
            for side in ("source", "target"):
                related.append(f"(kind='bind' AND json_extract({snapshot}, '$.{side}_project_id')=?)")
                values.append(project_id)
        terms.append("(" + " OR ".join(related) + ")")
    if kind is not None:
        terms.append("kind=?")
        values.append(kind)
    if id is not None:
        terms.append("target_id=?")
        values.append(id)
    where = " WHERE " + " AND ".join(terms) if terms else ""
    counts = connection.execute("SELECT COUNT(DISTINCT operation_id), COUNT(*) FROM changes" + where, values).fetchone()
    having = " HAVING MAX(id) < ?" if before is not None else ""
    page = connection.execute("SELECT operation_id, MAX(id) AS cursor, COUNT(*) AS matched FROM changes" + where +
                              " GROUP BY operation_id" + having + " ORDER BY cursor DESC LIMIT ?",
                              [*values, *([before] if before is not None else []), limit + 1]).fetchall()
    return counts, page

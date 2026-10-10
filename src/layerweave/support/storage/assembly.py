"""读取完整记录：层含直接装载对象，每个实体的 bind 是它发出的完整关联。"""

from contextlib import contextmanager

from layerweave.support.storage import crud


@contextmanager
def _snapshot(connection):
    if connection.in_transaction:
        yield  # 使用调用方的事务，不替调用方提交。
    else:
        with connection:
            connection.execute("BEGIN")
            yield


def _bindings(connection, kind, project_id, entity_id):
    return crud.read(connection, "bind", filters={
        "source_kind": kind, "source_project_id": project_id, "source_id": entity_id,
    })


def read_object(connection, project_id, id):
    """返回对象字典及发出的 bind；不存在返回 None，不加载配置或执行检测。"""
    with _snapshot(connection):
        record = crud.read(connection, "object", project_id=project_id, id=id)
        if record is not None:
            record["bind"] = _bindings(connection, "object", project_id, id)
        return record


def read_layer(connection, project_id, id):
    """返回层、直接装载对象与它们发出的 bind；不递归父层、子层或关联目标。"""
    with _snapshot(connection):
        record = crud.read(connection, "layer", project_id=project_id, id=id)
        if record is None:
            return None
        record["bind"] = _bindings(connection, "layer", project_id, id)
        record["objects"] = crud.read(connection, "object", project_id=project_id, filters={"layer": id})
        objects = {obj["id"]: obj for obj in record["objects"]}
        for obj in objects.values():
            obj["bind"] = []
        if objects:
            # 直接按所属层联查，避免逐对象查询或生成长度随对象数增长的 IN 参数。
            rows = connection.execute(
                "SELECT b.* FROM binds AS b JOIN objects AS o "
                "ON o.project_id = b.source_project_id AND o.id = b.source_id "
                "WHERE o.project_id = ? AND o.layer = ? AND b.source_kind = 'object' ORDER BY b.id",
                (project_id, id),
            )
            for row in rows:
                objects[row["source_id"]]["bind"].append(dict(row))
        return record


def read_project_index(connection, project_id):
    """项目与层摘要：只取身份、层级和直属对象数，不读取正文、轴或配置文件。"""
    with _snapshot(connection):
        project = crud.read(connection, "project", id=project_id)
        if project is None:
            return None
        rows = connection.execute(
            "SELECT l.project_id, l.id, l.name, l.type, l.config_ref, l.father, "
            "COUNT(o.id) AS object_count "
            "FROM layers AS l LEFT JOIN objects AS o "
            "ON o.project_id = l.project_id AND o.layer = l.id "
            "WHERE l.project_id = ? GROUP BY l.project_id, l.id ORDER BY l.id",
            (project_id,),
        )
        return {"project": project, "layers": [dict(row) for row in rows]}

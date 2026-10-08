"""按项目/子树及原始数值范围读取详情，成批装载对象和发出的关联。"""

from . import crud
from .assembly import _snapshot
from .queries import _object_conditions


def read_project_details(connection, project_id, *, layer_id=None, begin=None, end=None):
    """返回 project/scope/layers；不存在的项目或指定层返回 None，筛选无命中时 layers 为空。"""
    where, object_values = _object_conditions(project_id, begin=begin, end=end)
    with _snapshot(connection):
        project = crud.read(connection, "project", id=project_id)
        if project is None:
            return None
        if layer_id is None:
            scope = "SELECT id FROM layers WHERE project_id = ?"
            values = [project_id]
        else:
            root = crud.read(connection, "layer", project_id=project_id, id=layer_id)
            if root is None:
                return None
            layer_id = root["id"]
            # UNION 对编号去重，父链成环时也不会无限递归。
            scope = ("SELECT id FROM layers WHERE project_id = ? AND id = ? UNION "
                     "SELECT child.id FROM layers AS child JOIN layer_scope AS parent ON child.father = parent.id "
                     "WHERE child.project_id = ?")
            values = [project_id, layer_id, project_id]
        prefix = ("WITH RECURSIVE layer_scope(id) AS (" + scope + "), "
                  "matching_objects AS (SELECT * FROM objects WHERE " + where + " AND layer IN (SELECT id FROM layer_scope)), ")
        values += object_values
        if begin is not None or end is not None:
            # 只保留命中层和范围内的祖先路径，不将指定子树以外的父层展开。
            visible = ("SELECT layer FROM matching_objects UNION "
                       "SELECT l.father FROM layers AS l JOIN visible_layers AS v ON l.id = v.id "
                       "WHERE l.project_id = ? AND l.father IN (SELECT id FROM layer_scope)")
            values.append(project_id)
        else:
            visible = "SELECT id FROM layer_scope"
        prefix += "visible_layers(id) AS (" + visible + ") "
        layers = [crud._decode(crud.SPECS["layer"], row) for row in connection.execute(
            prefix + "SELECT * FROM layers WHERE project_id = ? AND id IN (SELECT id FROM visible_layers) ORDER BY id",
            [*values, project_id],
        )]
        result = {"project": project, "scope": {"layer_id": layer_id, "begin": begin, "end": end}, "layers": layers}
        if not layers:
            return result
        layer_map = {row["id"]: row for row in layers}
        for layer in layers:
            layer.update(objects=[], bind=[])
        objects = [crud._decode(crud.SPECS["object"], row) for row in connection.execute(
            prefix + 'SELECT * FROM matching_objects ORDER BY layer, "begin", "end", id', values,
        )]
        object_map = {row["id"]: row for row in objects}
        for obj in objects:
            obj["bind"] = []
            layer_map[obj["layer"]]["objects"].append(obj)
        bindings = connection.execute(
            prefix + "SELECT * FROM binds WHERE source_project_id = ? AND "
            "((source_kind = 'layer' AND source_id IN (SELECT id FROM visible_layers)) OR "
            "(source_kind = 'object' AND source_id IN (SELECT id FROM matching_objects))) ORDER BY id",
            [*values, project_id],
        )
        for row in bindings:
            owner = layer_map if row["source_kind"] == "layer" else object_map
            owner[row["source_id"]]["bind"].append(dict(row))
        return result

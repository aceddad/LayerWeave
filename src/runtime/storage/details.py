"""按项目/多棵子树读取详情；时间仅筛选对象，层范围保持完整。"""

from . import crud
from .assembly import _snapshot
from .queries import _object_conditions


def _tree_key(id, parents):
    """只用编号和父关系确定全项目树序，不读取范围外的正文。"""
    path, seen, current = [], set(), id
    while current is not None and current in parents and current not in seen:
        seen.add(current)
        path.append(current)
        current = parents[current]
    return (0, tuple(reversed(path))) if current is None else (1, (id,))


def read_project_details(connection, project_id, *, layer_id=None, layer_ids=None, begin=None, end=None):
    """完整记录批量读取；多层缺失逐项列出，单层缺失保持返回 None。"""
    if layer_id is not None and layer_ids is not None:
        raise ValueError("layer_id 与 layer_ids 只能提供一个")
    requested = None
    if layer_ids is not None:
        if isinstance(layer_ids, (str, bytes)):
            raise ValueError("layer_ids 应为整数编号列表，不能传字符串")
        requested = list(layer_ids)
        if any(type(id) is not int for id in requested):
            raise ValueError("layer_ids 中的每个编号应为整数")
        requested = list(dict.fromkeys(requested))
    where, object_values = _object_conditions(project_id, begin=begin, end=end)
    with _snapshot(connection):
        project = crud.read(connection, "project", id=project_id)
        if project is None:
            return None
        roots, missing = None, []
        if layer_id is not None:
            root = crud.read(connection, "layer", project_id=project_id, id=layer_id)
            if root is None:
                return None
            layer_id = root["id"]
            requested = roots = [layer_id]
        elif requested is not None:
            parents = dict(connection.execute("SELECT id, father FROM layers WHERE project_id=?", (project_id,))) if requested else {}
            roots = sorted((id for id in requested if id in parents), key=lambda id: _tree_key(id, parents))
            missing = [id for id in requested if id not in parents]
        result = {"project": project, "scope": {"layer_id": layer_id, "layer_ids": requested,
                   "root_ids": roots, "begin": begin, "end": end}, "layers": [], "missing_layer_ids": missing}
        if roots == []:
            return result
        if roots is None:
            scope = "SELECT id FROM layers WHERE project_id = ?"
            values = [project_id]
        else:
            placeholders = ",".join("?" for _ in roots)
            # UNION 对编号去重，父链成环时也不会无限递归。
            scope = (f"SELECT id FROM layers WHERE project_id = ? AND id IN ({placeholders}) UNION "
                     "SELECT child.id FROM layers AS child JOIN layer_scope AS parent ON child.father = parent.id "
                     "WHERE child.project_id = ?")
            values = [project_id, *roots, project_id]
        prefix = ("WITH RECURSIVE layer_scope(id) AS (" + scope + "), "
                  "matching_objects AS (SELECT * FROM objects WHERE " + where + " AND layer IN (SELECT id FROM layer_scope)) ")
        values += object_values
        layers = [crud._decode(crud.SPECS["layer"], row) for row in connection.execute(
            prefix + "SELECT * FROM layers WHERE project_id = ? AND id IN (SELECT id FROM layer_scope) ORDER BY id",
            [*values, project_id],
        )]
        result["layers"] = layers
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
            "((source_kind = 'layer' AND source_id IN (SELECT id FROM layer_scope)) OR "
            "(source_kind = 'object' AND source_id IN (SELECT id FROM matching_objects))) ORDER BY id",
            [*values, project_id],
        )
        for row in bindings:
            owner = layer_map if row["source_kind"] == "layer" else object_map
            owner[row["source_id"]]["bind"].append(dict(row))
        return result

"""按原身份和原始值恢复记录；仅由统一写入入口调用。"""
from copy import deepcopy
from . import crud
from .journal import append_change, json_text
from layerweave.core.values import same_value


def _project_high_water(connection, id, *records):
    values = [row.get("max_id", 0) for row in records if row is not None]
    query = ("SELECT MAX(n) FROM (SELECT MAX(id) n FROM layers WHERE project_id=? UNION ALL "
             "SELECT MAX(id) FROM objects WHERE project_id=? UNION ALL "
             "SELECT MAX(target_id) FROM changes WHERE project_id=? AND kind IN ('layer','object') UNION ALL "
             "SELECT MAX(json_extract(before_data,'$.max_id')) FROM changes WHERE kind='project' AND target_id=? UNION ALL "
             "SELECT MAX(json_extract(after_data,'$.max_id')) FROM changes WHERE kind='project' AND target_id=?)")
    values.append(connection.execute(query, (id,) * 5).fetchone()[0] or 0)
    return max(values, default=0)


def restore(connection, key, item, operation_id, undo_of=None):
    """私有恢复入口：原编号、原始坐标和内容，不重发号或按当前轴归一。"""
    kind, project_id, id = key
    current = crud.read(connection, kind, project_id=project_id, id=id)
    desired = deepcopy(item["restore"])
    if same_value(current, desired):
        return None
    if desired is not None and kind in {"layer", "object"}:
        other = "object" if kind == "layer" else "layer"
        if crud.read(connection, other, project_id=project_id, id=id) is not None:
            raise ValueError(f"编号 ({project_id}, {id}) 已被 {other} 使用")
    spec = crud.SPECS[kind]
    where, identity = crud._where(spec, project_id, id, None)
    if desired is None:
        connection.execute(f'DELETE FROM "{spec["table"]}"{where}', identity)
    else:
        if kind == "project":
            desired["max_id"] = _project_high_water(connection, id, current, desired)
        columns = ["id", *spec["fields"], *(("project_id",) if spec["scoped"] else ())]
        if kind == "project":
            columns.append("max_id")
        values = {name: json_text(desired[name]) if name in spec["json"] and not (name == "axis" and desired[name] is None)
                  else desired[name] for name in columns}
        if current is None:
            names = ", ".join(f'"{name}"' for name in columns)
            connection.execute(f'INSERT INTO "{spec["table"]}" ({names}) VALUES ({", ".join("?" for _ in columns)})', list(values.values()))
        else:
            writable = [name for name in columns if name not in {"id", "project_id"}
                        and ("fields" not in item or name in item["fields"])]
            if kind == "project" and "max_id" not in writable and desired["max_id"] != current["max_id"]:
                writable.append("max_id")
            assignments = ", ".join(f'"{name}"=?' for name in writable)
            connection.execute(f'UPDATE "{spec["table"]}" SET {assignments}{where}', [*[values[name] for name in writable], *identity])
        if spec["scoped"]:
            connection.execute("UPDATE projects SET max_id=MAX(max_id, ?) WHERE id=?", (id, project_id))
    after = crud.read(connection, kind, project_id=project_id, id=id)
    return append_change(connection, operation_id, kind, current, after, undo_of=undo_of)

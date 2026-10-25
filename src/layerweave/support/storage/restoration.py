"""按原身份和原始值恢复记录；仅由统一写入入口调用。"""
from copy import deepcopy
from . import crud
from .journal import append_change, json_text
from layerweave.core.values import same_value
from .tables import normalize_record
from .binary import normalize_binary
from .errors import execute
from layerweave.support.numbering.state import preserve_counters, advance_member_counter, counter_fields


def restore(connection, key, item, operation_id, undo_of=None):
    """私有恢复入口：原编号、原始坐标和内容，不重发号或按当前轴归一。"""
    kind, project_id, id = key
    spec = crud._spec(kind, writing=True, connection=connection)
    current = crud.read(connection, kind, project_id=project_id, id=id)
    desired = normalize_record(connection, kind, deepcopy(normalize_binary(spec, item["restore"])))
    if same_value(current, desired):
        return None
    where, identity = crud._where(spec, project_id, id, None)
    if desired is None:
        execute(connection, f'DELETE FROM "{spec["table"]}"{where}', identity,
                kind=kind, record=current, action="delete")
    else:
        desired = preserve_counters(connection, kind, desired, current)
        columns = ["id", *spec["fields"], *(("project_id",) if spec["scoped"] else ())]
        if kind == "project":
            columns.append("max_id")
        values = {name: json_text(desired[name]) if name in spec["json"] and not (kind == "layer" and name == "axis" and desired[name] is None)
                  else desired[name] for name in columns}
        if current is None:
            names = ", ".join(f'"{name}"' for name in columns)
            execute(connection, f'INSERT INTO "{spec["table"]}" ({names}) VALUES ({", ".join("?" for _ in columns)})', list(values.values()),
                    kind=kind, record=desired, action="create")
        else:
            writable = [name for name in columns if name not in {"id", "project_id"}
                        and ("fields" not in item or name in item["fields"])]
            for field in counter_fields(connection, kind, desired):
                if field not in writable and desired[field] != current[field]:
                    writable.append(field)
            assignments = ", ".join(f'"{name}"=?' for name in writable)
            execute(connection, f'UPDATE "{spec["table"]}" SET {assignments}{where}', [*[values[name] for name in writable], *identity],
                    kind=kind, record=desired, action="update")
        advance_member_counter(connection, kind, desired)
    after = crud.read(connection, kind, project_id=project_id, id=id)
    return append_change(connection, operation_id, kind, current, after, undo_of=undo_of)

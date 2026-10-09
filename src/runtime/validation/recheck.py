"""主动复查的范围选择；使用同一读取快照与现有检测器，不写数据或日志。"""

from functools import partial

from .runner import validate
from ..configuration.loader import DEFAULT_ROOT
from ..storage import crud
from ..storage.assembly import _snapshot
from ..storage.details import read_project_details


def recheck(connection, project_id, *, layer_ids=None, object_ids=None, config_root=DEFAULT_ROOT):
    if layer_ids is not None and object_ids is not None:
        raise ValueError("layer_ids 与 object_ids 只能选择一个；均省略时复查整个项目")
    selection = layer_ids if layer_ids is not None else object_ids
    if selection is not None:
        selection = list(selection)
        if any(type(id) is not int for id in selection):
            raise ValueError("复查目标应为整数编号列表")
        selection = list(dict.fromkeys(selection))
    mode = "subtrees" if layer_ids is not None else "objects" if object_ids is not None else "project"
    counts = {"layers": 0, "objects": 0}
    with _snapshot(connection):
        reader = partial(crud.read, connection)
        project = reader("project", id=project_id)
        if project is None or mode == "project":
            targets = [{"kind": "project", "id": project_id}]
            if project is not None:
                counts = {"layers": len(reader("layer", project_id=project_id)),
                          "objects": len(reader("object", project_id=project_id))}
        elif mode == "subtrees":
            data = read_project_details(connection, project_id, layer_ids=selection)
            targets = [{"kind": "layer", "project_id": project_id, "id": id}
                       for id in [*[layer["id"] for layer in data["layers"]], *data["missing_layer_ids"]]]
            counts = {"layers": len(data["layers"]), "objects": sum(len(layer["objects"]) for layer in data["layers"])}
        else:
            targets = [{"kind": "object", "project_id": project_id, "id": id} for id in selection]
            counts["objects"] = sum(reader("object", project_id=project_id, id=id) is not None for id in selection)
        result = validate(targets, reader, config_root=config_root)
    return {"scope": {"project_id": project_id, "mode": mode, "ids": selection},
            "counts": counts, **result,
            "issue_counts": {level: sum(i["severity"] == level for i in result["issues"]) for level in ("error", "warn")}}

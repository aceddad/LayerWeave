"""python -X utf8 -B -m examples.second_batch：第二批六个工具的完整内存示例。"""

from contextlib import closing
import json

from runtime.api import dispatch, open_database, read_layer, save_layer
from runtime.storage.database import SCHEMA_PATH
from tools.common.objects import append_object, copy_object
from tools.common.positions import align_objects, arrange_objects, set_duration, shift_objects


def _ok(result):
    if not result["ok"]:
        raise RuntimeError(result["error"])
    return result


def create_example():
    with closing(open_database(":memory:")) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        project_id = _ok(dispatch(connection, {"action": "create", "kind": "project", "data": {"name": "第二批工具示例"}}))["id"]
        layer = _ok(save_layer(connection, project_id, {"type": "text", "config_ref": "layers/text.toml", "name": "主线"}))["data"]
        a = _ok(append_object(connection, project_id, layer["id"], {
            "config_ref": "objects/text.toml", "name": "A", "information": {"text": "第一句"},
        }, duration=3))
        b = _ok(append_object(connection, project_id, layer["id"], {
            "config_ref": "objects/text.toml", "name": "B", "information": {"text": "第二句"},
        }, duration=2))
        _ok(dispatch(connection, {"action": "create", "kind": "bind", "data": {
            "source_kind": "object", "source_project_id": project_id, "source_id": a["id"],
            "target_kind": "object", "target_project_id": project_id, "target_id": b["id"], "tips": "原对象之间的关联",
        }}))
        shifted = _ok(shift_objects(connection, project_id, [a["id"], b["id"]], offset=4))
        arranged = _ok(arrange_objects(connection, project_id, layer["id"], object_ids=[b["id"], a["id"]], start=0))
        second_layer = _ok(save_layer(connection, project_id, {"type": "text", "config_ref": "layers/text.toml", "name": "副本"}))["data"]
        copied = _ok(copy_object(connection, project_id, a["id"], layer_id=second_layer["id"], append=True))
        aligned = _ok(align_objects(connection, project_id, [a["id"], copied["id"]], position=10))
        resized = _ok(set_duration(connection, project_id, copied["id"], 4))
        return {
            "operations": {"append_a": a, "append_b": b, "shift": shifted, "arrange": arranged,
                           "copy": copied, "align": aligned, "duration": resized},
            "layers": [read_layer(connection, project_id, layer["id"]),
                       read_layer(connection, project_id, second_layer["id"])],
        }


if __name__ == "__main__":
    print(json.dumps(create_example(), ensure_ascii=False, indent=2))

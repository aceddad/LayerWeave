"""python -X utf8 -B -m examples.project_details：详细展开与数值范围筛选的内存示例。"""

from contextlib import closing

from runtime.api import dispatch, open_database, save_layer
from runtime.storage.database import SCHEMA_PATH
from tools.common.objects import append_object
from tools.common.project_details import format_details, project_details


def create_example():
    with closing(open_database(":memory:")) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        project_id = dispatch(connection, {"action": "create", "kind": "project", "data": {"name": "详细展开示例"}})["id"]
        root = save_layer(connection, project_id, {"config_ref": "layers/text.toml", "name": "字幕",
                                                  "axis": {"unit": "秒", "precision": 0.001}})["data"]
        for text in ("第一句", "第二句", "第三句"):
            append_object(connection, project_id, root["id"], {"config_ref": "objects/text.toml", "information": {"text": text}}, duration=0.1)
        save_layer(connection, project_id, {"config_ref": "layers/audio.toml", "name": "配音", "father": root["id"],
                                            "objects": [{"config_ref": "objects/audio.toml", "begin": 0.1, "end": 0.4,
                                                         "information": {"source": "assets/voice.wav"}}]})
        save_layer(connection, project_id, {"config_ref": "layers/image.toml", "name": "参考",
                                            "axis": {"unit": "帧", "precision": 1},
                                            "objects": [{"config_ref": "objects/image.toml", "begin": 1, "end": 2,
                                                         "information": {"source": "assets/reference.png"}}]})
        return {
            "whole": project_details(connection, project_id),
            "subtree": project_details(connection, project_id, layer_id=root["id"]),
            "window": project_details(connection, project_id, begin=0.1, end=0.3),
            "subtree_window": project_details(connection, project_id, layer_id=root["id"], begin=0.1, end=0.3),
        }


if __name__ == "__main__":
    print(format_details(create_example()["subtree_window"]))

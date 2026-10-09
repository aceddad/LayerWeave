"""python -X utf8 -B -m examples.first_batch：四个内部工具的完整内存示例。"""

from contextlib import closing
import json

from tool.builtin.usage.records.dispatch import dispatch
from support.api import open_database
from tool.builtin.usage.records.save import save_layer
from support.storage.database import SCHEMA_PATH
from tool.builtin.usage.query.find_objects import find_objects
from tool.builtin.usage.query.project_overview import project_overview
from tool.builtin.usage.query.relations import query_relations
from tool.builtin.usage.text.collect import collect_text


def create_example():
    with closing(open_database(":memory:")) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        project_id = dispatch(connection, {
            "action": "create", "kind": "project", "data": {"name": "第一批工具示例"},
        })["id"]
        text = save_layer(connection, project_id, {
            "config_ref": "layers/text.toml", "name": "台词",
            "objects": [
                {"config_ref": "objects/text.toml", "name": "开场", "begin": 0, "end": 2, "information": {"text": "开场白"}},
                {"config_ref": "objects/text.toml", "name": "结尾", "begin": 2, "end": 4, "information": {"text": "结束语"}},
            ],
        })["data"]
        voice = save_layer(connection, project_id, {
            "config_ref": "layers/audio.toml", "name": "配音", "father": text["id"],
            "objects": [{"config_ref": "objects/audio.toml", "begin": 0, "end": 2,
                         "information": {"source": "assets/opening.wav"}}],
        })["data"]
        object_id = text["objects"][0]["id"]
        dispatch(connection, {"action": "create", "kind": "bind", "data": {
            "source_kind": "object", "source_project_id": project_id, "source_id": voice["objects"][0]["id"],
            "target_kind": "object", "target_project_id": project_id, "target_id": object_id, "tips": "这段台词的配音",
        }})
        return {
            "overview": project_overview(connection, project_id),
            "objects": find_objects(connection, project_id, layer_id=text["id"], content="开场", begin=0, end=2),
            "relations": query_relations(connection, project_id, "object", object_id),
            "text": collect_text(connection, project_id, text["id"]),
        }


if __name__ == "__main__":
    print(json.dumps(create_example(), ensure_ascii=False, indent=2))

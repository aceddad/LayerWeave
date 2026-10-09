"""python -X utf8 -B -m examples.diagnostics：选填静音、类型错误、落点与同因合并。"""

from contextlib import closing

from models import Model, ModelLayer, TextLayer
from tool.builtin.usage.records.dispatch import dispatch
from support.api import format_feedback, open_database
from tool.builtin.usage.records.save import save_layer, save_object
from support.storage.database import SCHEMA_PATH


def main():
    with closing(open_database(":memory:")) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        project_id = dispatch(connection, {"action": "create", "kind": "project", "data": {}})["id"]
        model_layer = ModelLayer()
        save_layer(connection, project_id, model_layer)
        model = Model(layer=model_layer.id, information={"source": "model.glb"})
        print(format_feedback(save_object(connection, project_id, model)))
        model.information["data"] = "这里应当是字典"
        print(format_feedback(save_object(connection, project_id, model)))
        layer = TextLayer(axis={"precision": 0.001})
        save_layer(connection, project_id, layer)
        result = dispatch(connection, {"action": "create", "kind": "object", "project_id": project_id,
            "data": {"layer": layer.id, "config_ref": "objects/text.toml", "end": 0.1 + 0.2,
                     "information": {"text": "直接写入也落点"}}})
        print(f"实际保存的终点：{result['data']['end']}")
        missing = dispatch(connection, {"action": "create", "kind": "object", "project_id": project_id,
            "data": {"layer": layer.id, "config_ref": "objects/txt.toml"}})
        print(format_feedback(missing))


if __name__ == "__main__":
    main()

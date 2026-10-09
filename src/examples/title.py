"""python -X utf8 -B -m examples.title：一份派生配置对应一个派生类。"""

from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from models import Text, TextLayer, Title
from tool.builtin.usage.records.dispatch import dispatch
from support.api import initialize_database, load_layer, open_database, read_layer
from tool.builtin.usage.records.save import save_layer


def _saved(result):
    if not result["ok"]:
        raise RuntimeError(result["error"])
    return result


def create_example():
    with TemporaryDirectory(prefix="layerweave-title-") as directory:
        database = initialize_database(Path(directory) / "example.sqlite3")
        with closing(open_database(database)) as connection:
            project_id = _saved(dispatch(connection, {"action": "create", "kind": "project",
                                                      "data": {"name": "派生封装示例"}}))["id"]
            layer = TextLayer(name="文章")
            _saved(save_layer(connection, project_id, layer))
            layer.objects = [
                Title(layer=layer.id, name="标题", information={"text": "第一章"}),
                Text(layer=layer.id, name="正文", information={"text": "故事从这里开始。"}),
            ]
            written = _saved(save_layer(connection, project_id, layer))

        with closing(open_database(database)) as connection:
            loaded = load_layer(connection, project_id, layer.id)
            loaded.objects[0].information["text"] = "第一章：出发"
            updated = _saved(save_layer(connection, project_id, loaded))
            record = read_layer(connection, project_id, layer.id)
        return {"layer_class": type(loaded).__name__, "layer_type_from_toml": record["type"],
                "objects": [{"class": type(obj).__name__, "config_ref": row["config_ref"],
                             "information": row["information"]}
                            for obj, row in zip(loaded.objects, record["objects"])],
                "write_checks": written["checks"], "update_checks": updated["checks"]}


if __name__ == "__main__":
    print(json.dumps(create_example(), ensure_ascii=False, indent=2))

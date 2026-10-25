"""python -X utf8 -B examples/data.py：通用 JSON 数据保存、重开与实例还原。"""

from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.models import Data, DataLayer
from layerweave.support.api import initialize_database, load_layer, open_database, transaction
from layerweave.tool.builtin.usage.records.save import save_layer_with_checks


def create_example():
    values = [
        ("结构", {"name": "角色甲", "tags": ["主角"], "settings": {"enabled": True}}),
        ("列表", [1, "中文", False, None, {"weight": 0.25}]),
        ("字符串", "原文也可以作为字符串保存"),
        ("整数", 12), ("小数", 0.25), ("布尔值", False), ("空值", None),
        ("空字典", {}), ("空列表", []), ("空字符串", ""), ("零", 0),
    ]
    with TemporaryDirectory(prefix="layerweave-data-") as directory:
        database = initialize_database(Path(directory) / "data.sqlite3")
        with closing(open_database(database)) as connection:
            with transaction(connection) as write:
                project_id = write.create("project", {"name": "通用数据示例"})["id"]
            layer = DataLayer(name="数据目录", axis={"unit": "序号", "precision": 1})
            created = save_layer_with_checks(connection, project_id, layer)
            if not created["ok"]:
                raise RuntimeError(created)
            layer.objects = [
                Data(layer=layer.id, name=name, begin=index, end=index, information={"data": value})
                for index, (name, value) in enumerate(values, 1)
            ]
            saved = save_layer_with_checks(connection, project_id, layer)
            if not saved["ok"] or saved["checks"]["issues"]:
                raise RuntimeError(saved)

        with closing(open_database(database)) as connection:
            loaded = load_layer(connection, project_id, layer.id)
            assert type(loaded) is DataLayer
            for obj, (name, value) in zip(loaded.objects, values):
                assert type(obj) is Data and obj.name == name
                assert type(obj.information["data"]) is type(value)
                assert obj.information["data"] == value
            return {"layer_class": type(loaded).__name__, "checks": saved["checks"],
                    "objects": [{"class": type(obj).__name__, "name": obj.name,
                                 "information": obj.information} for obj in loaded.objects]}


if __name__ == "__main__":
    print(json.dumps(create_example(), ensure_ascii=False, allow_nan=False, indent=2))

"""通用数据的实际保存、检查、交换、撤销和配置发现。"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from layerweave.models import Data, DataLayer, Layer, Object
from layerweave.support.api import (
    initialize_database, load_layer, load_object, open_database, query_objects,
    read_record, transaction,
)
from layerweave.support.configuration.loader import Loader
from layerweave.tool.builtin.shared.help.config_help import config_help, format_help
from layerweave.tool.builtin.usage.exchange import export_project, import_project
from layerweave.tool.builtin.usage.records.save import save_layer_with_checks, save_object_with_checks
from layerweave.tool.builtin.usage.undo.service import undo_operation


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="layerweave-data-test-")
        self.addCleanup(self.temp.cleanup)
        self.path = initialize_database(Path(self.temp.name) / "data.sqlite3")
        self.c = open_database(self.path)
        self.addCleanup(lambda: self.c.close())
        with transaction(self.c) as write:
            self.project = write.create("project", {"name": "data"})["id"]
        self.layer = DataLayer(name="data", axis={"unit": "序号", "precision": 1})
        self.assertTrue(save_layer_with_checks(self.c, self.project, self.layer)["ok"])

    def test_json_values_survive_reopen_and_exchange_without_type_loss(self):
        values = [{"items": [False, None, {"中文": 0.5}]}, [1, "a", True, None],
                  "中文", 12, -3, 0.25, True, False, None, {}, [], "", 0, 0.0]
        self.layer.objects = [Data(layer=self.layer.id, begin=i, end=i, information={"data": value})
                              for i, value in enumerate(values, 1)]
        result = save_layer_with_checks(self.c, self.project, self.layer)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["checks"]["issues"], [])
        self.c.close()
        self.c = open_database(self.path)
        loaded = load_layer(self.c, self.project, self.layer.id)
        self.assertIs(type(loaded), DataLayer)
        self.assertEqual(len(loaded.objects), len(values))
        for obj, value in zip(loaded.objects, values):
            self.assertIs(type(obj), Data)
            self.assertIs(type(obj.information["data"]), type(value))
            self.assertEqual(obj.information["data"], value)
        document = json.loads(json.dumps(export_project(self.c, self.project, op="add"), allow_nan=False))
        copied = import_project(self.c, document)
        self.assertTrue(copied["ok"], copied)
        self.assertEqual(copied["checks"]["issues"], [])
        rows = query_objects(self.c, copied["data"]["project_id"])
        self.assertEqual([row["information"]["data"] for row in rows], values)
        self.assertEqual([type(row["information"]["data"]) for row in rows], list(map(type, values)))

    def test_missing_data_warns_but_explicit_null_and_empty_values_are_valid(self):
        missing = save_object_with_checks(self.c, self.project, Data(layer=self.layer.id))
        self.assertTrue(missing["ok"])
        self.assertEqual([(issue["code"], issue["field"], issue["severity"])
                          for issue in missing["checks"]["issues"]],
                         [("missing_field", "information.data", "warn")])
        for value in (None, False, 0, "", {}, []):
            result = save_object_with_checks(self.c, self.project,
                                            Data(layer=self.layer.id, information={"data": value}))
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["checks"]["issues"], [])

    def test_nested_update_undo_and_non_json_failure_use_existing_storage(self):
        obj = Data(layer=self.layer.id, information={"data": {"items": [1, None]}})
        self.assertTrue(save_object_with_checks(self.c, self.project, obj)["ok"])
        obj.information["data"] = [False, {"nested": "新值"}]
        edited = save_object_with_checks(self.c, self.project, obj)
        self.assertTrue(edited["ok"], edited)
        self.assertTrue(undo_operation(self.c, edited["operation_id"])["ok"])
        self.assertEqual(load_object(self.c, self.project, obj.id).information, {"data": {"items": [1, None]}})
        before = read_record(self.c, "project", id=self.project)["max_id"]
        bad = save_object_with_checks(self.c, self.project,
                                      Data(layer=self.layer.id, information={"data": {"nested": b"binary"}}))
        self.assertFalse(bad["ok"])
        self.assertEqual(read_record(self.c, "project", id=self.project)["max_id"], before)

    def test_help_and_layer_acceptance_use_base_derived_configs(self):
        self.assertEqual(Data.__bases__, (Object,))
        self.assertEqual(DataLayer.__bases__, (Layer,))
        loader = Loader()
        layer = loader.load("layers/data.toml", "layer")
        obj = loader.load("objects/data.toml", "object")
        self.assertTrue(loader.accepts_object(layer, obj))
        self.assertFalse(loader.accepts_object(layer, loader.load("objects/text.toml", "object")))
        self.assertFalse(loader.accepts_object(loader.load("layers/text.toml", "layer"), obj))
        self.assertEqual(set(obj["information"]), {"data"})
        overview = config_help()
        entry = next(item for item in overview["items"] if item["config_ref"] == "layers/data.toml")
        self.assertEqual([item["config_ref"] for item in entry["accepted_objects"]], ["objects/data.toml"])
        for audience in ("usage", "developer"):
            result = config_help("combined", "data", audience=audience)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["issues"], [])
            self.assertEqual(result["object_details"][0]["config_ref"], "objects/data.toml")
            field_label = "information.data:" if audience == "usage" else "data:"
            self.assertIn(field_label + " dict | list | str | int | float | bool | None", format_help(result))
            self.assertIn("objects/data.toml", result["object_details"][0]["save_example"]["code"])


if __name__ == "__main__":
    unittest.main()

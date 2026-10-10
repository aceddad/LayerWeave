"""实际 JSON 类型变化必须写日志并参与最终状态检测。"""

from functools import partial
from pathlib import Path
import shutil
import tempfile
import unittest

from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.support.api import open_database
from layerweave.support.configuration.loader import ConfigError, DEFAULT_ROOT, Loader
from layerweave.support.storage import crud
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.tool.builtin.usage.validation.runner import check_changes


class ChangeValueTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="layerweave-values-")
        self.addCleanup(temp.cleanup)
        self.configs = Path(temp.name) / "configs"
        shutil.copytree(DEFAULT_ROOT, self.configs)
        (self.configs / "objects/typed.toml").write_text(
            '[object]\ntype="typed"\nclass="fixture_types:TypedObject"\nextends="base.toml"\n[object.information]\nflag={type="int"}\n', encoding="utf-8")
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.checker = partial(check_changes, config_root=self.configs)
        self.project_id = self.call("create", "project", data={})["id"]
        self.layer_id = self.call("create", "layer", project_id=self.project_id,
                                  data={"type": "Layer", "config_ref": "layers/base.toml"})["id"]

    def call(self, action, kind, **args):
        return dispatch(self.connection, {"action": action, "kind": kind, **args}, checker=self.checker)

    def create(self, information):
        return self.call("create", "object", project_id=self.project_id, data={
            "layer": self.layer_id, "config_ref": "objects/typed.toml", "information": information,
        })["id"]

    def update(self, id, information):
        return self.call("update", "object", project_id=self.project_id, id=id, data={"information": information})

    def test_number_to_bool_is_logged_and_checked(self):
        id = self.create({"flag": 1})
        result = self.update(id, {"flag": True})
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["applied"])
        self.assertIs(type(result["data"]["information"]["flag"]), bool)
        logs = crud.read(self.connection, "change", filters={"operation_id": result["operation_id"]})
        self.assertEqual(len(logs), 1)
        self.assertIs(type(logs[0]["before_data"]["information"]["flag"]), int)
        self.assertIs(type(logs[0]["after_data"]["information"]["flag"]), bool)
        self.assertTrue(any(item.get("field") == "information.flag" for item in result["checks"]["issues"]))

    def test_nested_numeric_type_changes_are_preserved(self):
        for before, after in ((1, True), (True, 1), (0, False), (False, 0), (1, 1.0), (1.0, 1), (1.0, True)):
            with self.subTest(before=type(before).__name__, after=type(after).__name__):
                id = self.create({"nested": [{"value": before}]})
                result = self.update(id, {"nested": [{"value": after}]})
                self.assertTrue(result["applied"], result)
                self.assertIs(type(result["data"]["information"]["nested"][0]["value"]), type(after))
                self.assertEqual(len(crud.read(self.connection, "change", filters={"operation_id": result["operation_id"]})), 1)

    def test_batch_uses_type_aware_final_state_and_field_selection(self):
        id = self.create({"flag": 1})
        result = dispatch(self.connection, [
            {"action": "update", "kind": "object", "project_id": self.project_id, "id": id,
             "data": {"information": {"flag": value}}} for value in (1.0, True)
        ], checker=self.checker)
        self.assertTrue(result["applied"])
        self.assertEqual(len(crud.read(self.connection, "change", filters={"operation_id": result["operation_id"]})), 2)
        self.assertTrue(any(item.get("field") == "information.flag" for item in result["checks"]["issues"]))

    def test_batch_restoring_original_type_has_no_final_issue(self):
        id = self.create({"flag": 1})
        result = dispatch(self.connection, [
            {"action": "update", "kind": "object", "project_id": self.project_id, "id": id,
             "data": {"information": {"flag": value}}} for value in (True, 1)
        ], checker=self.checker)
        self.assertEqual(len(crud.read(self.connection, "change", filters={"operation_id": result["operation_id"]})), 2)
        self.assertEqual(result["checks"]["issues"], [])

    def test_json_key_order_and_sql_numeric_equivalence_are_noops(self):
        id = self.create({"flag": 1, "nested": {"a": 1, "b": [True, 2]}})
        statements = []
        self.connection.set_trace_callback(statements.append)
        try:
            result = self.call("update", "object", project_id=self.project_id, id=id, data={
                "begin": 0, "end": 0, "information": {"nested": {"b": [True, 2], "a": 1}, "flag": 1},
            })
        finally:
            self.connection.set_trace_callback(None)
        self.assertFalse(result["applied"])
        self.assertFalse(any(sql.startswith("UPDATE") for sql in statements))
        self.assertEqual(result["checks"]["reason"], "no_changes")

    def test_comparison_uses_serialized_json_values(self):
        id = self.create({"nested": {"1": [1, True]}})
        statements = []
        self.connection.set_trace_callback(statements.append)
        try:
            result = self.update(id, {"nested": {1: (1, True)}})
        finally:
            self.connection.set_trace_callback(None)
        self.assertFalse(result["applied"])
        self.assertFalse(any(sql.startswith("UPDATE") for sql in statements))

    def test_configuration_cannot_replace_bool_contract_with_number(self):
        for text in ('[object]\ntype="bad"\nclass="fixture_types:BadObject"\nextends="base.toml"\nopen=1\n',
                     '[object]\ntype="bad"\nclass="fixture_types:BadObject"\nextends="base.toml"\n[object.rules]\nbegin_le_end=1\n'):
            (self.configs / "objects/bad.toml").write_text(text, encoding="utf-8")
            with self.assertRaises(ConfigError):
                Loader(self.configs).load("objects/bad.toml", "object")

"""类与配置的一一对应、TOML 类型来源及原始记录的身份诊断。"""

from functools import partial
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from models import Text, TextLayer, Title
from runtime.api import (dispatch, load_layer, load_object, open_database, read_layer,
                         save_layer, save_object, validate)
from runtime.configuration.loader import ConfigError, DEFAULT_ROOT, Loader
from runtime.storage import crud
from runtime.storage.database import SCHEMA_PATH
from tools.usage.text.collect import collect_text


class EncapsulationIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-identity-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.configs = self.root / "configs"
        shutil.copytree(DEFAULT_ROOT, self.configs)
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.project = dispatch(self.connection, {"action": "create", "kind": "project", "data": {}})["id"]

    def save(self, value):
        return save_layer(self.connection, self.project, value, config_root=self.configs)

    def call(self, action, **args):
        return dispatch(self.connection, {"action": action, "kind": "layer", "project_id": self.project, **args},
                        config_root=self.configs)

    def test_python_layer_type_comes_only_from_toml(self):
        path = self.configs / "layers/text.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('type    = "text"', 'type    = "caption"'), encoding="utf-8")
        layer = TextLayer()
        self.assertFalse(hasattr(layer, "type"))
        result = self.save(layer)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["type"], "caption")
        self.assertEqual(result["checks"]["issues"], [])
        self.assertIs(type(load_layer(self.connection, self.project, layer.id, config_root=self.configs)), TextLayer)
        raw = self.call("create", data={"config_ref": "layers/text.toml"})
        self.assertEqual(raw["data"]["type"], "caption")
        self.assertEqual(raw["checks"]["issues"], [])

    def test_dictionary_type_is_filled_and_round_trip_is_noop(self):
        data = {"config_ref": "layers/text.toml"}
        result = self.save(data)
        self.assertTrue(result["ok"], result)
        self.assertEqual(data["type"], "text")
        record = read_layer(self.connection, self.project, data["id"])
        self.assertFalse(self.save(record)["applied"])
        changed = self.save({"id": data["id"], "config_ref": "layers/image.toml"})
        self.assertEqual(changed["data"]["type"], "image")
        self.assertEqual(type(load_layer(self.connection, self.project, data["id"])).__name__, "ImageLayer")

    def test_conflicting_dictionary_type_fails_without_allocating_or_logging(self):
        before = len(crud.read(self.connection, "change"))
        data = {"type": "image", "config_ref": "layers/text.toml"}
        result = self.save(data)
        self.assertFalse(result["ok"])
        self.assertIn("不一致", result["error"]["message"])
        self.assertNotIn("id", data)
        self.assertEqual(crud.read(self.connection, "project", id=self.project)["max_id"], 0)
        self.assertEqual(len(crud.read(self.connection, "change")), before)

    def test_title_is_a_text_subclass_and_text_tools_include_it(self):
        layer = TextLayer()
        self.assertTrue(self.save(layer)["ok"])
        layer.objects = [Title(layer=layer.id, information={"text": "标题"}),
                         Text(layer=layer.id, information={"text": "正文"})]
        result = self.save(layer)
        self.assertEqual(result["checks"]["issues"], [])
        self.assertTrue(issubclass(Title, Text))
        loaded = load_layer(self.connection, self.project, layer.id)
        self.assertEqual([type(obj) for obj in loaded.objects], [Title, Text])
        self.assertEqual(collect_text(self.connection, self.project, layer.id)["text"], "标题\n正文")
        # 空字符串是合法文字内容，Title 演示不添加非空限制。
        loaded.objects[0].information["text"] = ""
        self.assertEqual(self.save(loaded)["checks"]["issues"], [])

    def test_existing_instance_identity_follows_its_actual_class(self):
        layer = TextLayer()
        self.save(layer)
        original = Text(layer=layer.id, information={"text": "同一记录"})
        save_object(self.connection, self.project, original)
        title = Title(id=original.id, layer=layer.id, information=original.information)
        result = save_object(self.connection, self.project, title)
        self.assertEqual(result["data"]["config_ref"], "objects/title.toml")
        self.assertIs(type(load_object(self.connection, self.project, title.id)), Title)

    def test_derived_config_must_explicitly_declare_its_own_class(self):
        (self.configs / "objects/alias.toml").write_text('[object]\ntype="alias"\nextends="text.toml"\n', encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "明确声明"):
            Loader(self.configs).load("objects/alias.toml", "object")
        # 无关的不完整配置不阻断可用的封装。
        self.assertEqual(Loader(self.configs).load("objects/text.toml", "object")["type"], "text")

    def test_explicit_reference_does_not_bypass_duplicate_class_binding(self):
        (self.configs / "objects/duplicate.toml").write_text(
            '[object]\ntype="duplicate"\nextends="text.toml"\nclass="models.objects.text:Text"\n', encoding="utf-8")
        for ref in ("objects/text.toml", "objects/duplicate.toml"):
            with self.subTest(ref=ref), self.assertRaisesRegex(ConfigError, "只绑定一份配置"):
                Loader(self.configs).load(ref, "object")

    def test_import_alias_cannot_restore_as_a_separate_encapsulation(self):
        (self.root / "identity_alias.py").write_text('from models import Text\n', encoding="utf-8")
        sys.path.insert(0, str(self.root))
        self.addCleanup(sys.path.remove, str(self.root))
        self.addCleanup(sys.modules.pop, "identity_alias", None)
        (self.configs / "objects/alias.toml").write_text(
            '[object]\ntype="alias"\nextends="text.toml"\nclass="identity_alias:Text"\n', encoding="utf-8")
        layer = TextLayer()
        self.save(layer)
        row = dispatch(self.connection, {"action": "create", "kind": "object", "project_id": self.project,
            "data": {"layer": layer.id, "config_ref": "objects/alias.toml"}}, config_root=self.configs)
        with self.assertRaisesRegex(ValueError, "定义位置"):
            load_object(self.connection, self.project, row["id"], config_root=self.configs)

    def test_dispatch_can_derive_type_on_create_and_config_change(self):
        result = self.call("create", data={"config_ref": "layers/text.toml"})
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["type"], "text")
        changed = self.call("update", id=result["id"], data={"config_ref": "layers/image.toml"})
        self.assertEqual(changed["data"]["type"], "image")
        self.assertEqual(changed["checks"]["issues"], [])

    def test_raw_type_mismatch_is_reported_on_create_update_and_manual_check(self):
        result = self.call("create", data={"type": "image", "config_ref": "layers/text.toml"})
        self.assertTrue(result["ok"], result)
        issue = next(item for item in result["checks"]["issues"] if item["rule"] == "layer_type")
        self.assertEqual((issue["severity"], issue["field"]), ("error", "type"))
        self.assertEqual(read_layer(self.connection, self.project, result["id"])["type"], "image")
        with self.assertRaisesRegex(ValueError, "不一致"):
            load_layer(self.connection, self.project, result["id"])
        fixed = self.call("update", id=result["id"], data={"type": "text"})
        self.assertEqual(fixed["checks"]["issues"], [])
        changed = self.call("update", id=result["id"], data={"type": "audio"})
        self.assertEqual(changed["checks"]["issues"][0]["rule"], "layer_type")
        report = validate([{"kind": "layer", "project_id": self.project, "id": result["id"]}],
                          partial(crud.read, self.connection), config_root=self.configs)
        self.assertTrue(any(item["rule"] == "layer_type" for item in report["issues"]))
        renamed = self.call("update", id=result["id"], data={"name": "只改名字"})
        self.assertEqual(renamed["checks"]["issues"], [])

    def test_missing_raw_config_is_not_compared_to_fallback_base_type(self):
        result = self.call("create", data={"type": "custom", "config_ref": "layers/missing.toml"})
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["checks"]["status"], "partial")
        self.assertFalse(any(item["rule"] == "layer_type" for item in result["checks"]["issues"]))
        self.assertEqual(read_layer(self.connection, self.project, result["id"])["type"], "custom")

    def test_normal_save_needs_config_and_rolls_back_whole_layer(self):
        layer = TextLayer()
        self.save(layer)
        before_logs = len(crud.read(self.connection, "change"))
        result = self.save({"id": layer.id, "name": "不应留下的修改", "objects": [
            {"config_ref": "objects/missing.toml", "information": {"text": "原始数据"}},
        ]})
        self.assertFalse(result["ok"])
        self.assertEqual(read_layer(self.connection, self.project, layer.id)["name"], "")
        self.assertEqual(len(crud.read(self.connection, "change")), before_logs)

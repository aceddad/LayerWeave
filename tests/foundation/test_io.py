"""完整记录和 Python 实例的双向读写，覆盖关闭重开、组合事务和扩充类。"""

from contextlib import closing
from importlib import import_module
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from layerweave.models import Text, TextLayer, Title
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.support.api import initialize_database, load_layer, load_object, open_database, read_layer, read_object
from layerweave.tool.builtin.usage.records.save import save_layer_with_checks, save_object_with_checks
from layerweave.support.configuration.loader import DEFAULT_ROOT
from layerweave.support.storage import crud
from layerweave.support.storage.database import SCHEMA_PATH


class IOTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-io-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.configs = self.root / "configs"
        shutil.copytree(DEFAULT_ROOT, self.configs)
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.project_id = self.project()

    def project(self):
        return dispatch(self.connection, {"action": "create", "kind": "project", "data": {}})["id"]

    def layer(self, **kwargs):
        layer = TextLayer(**kwargs)
        result = save_layer_with_checks(self.connection, self.project_id, layer)
        self.assertTrue(result["ok"], result)
        return layer

    def test_whole_record_create_read_modify_and_noop(self):
        source = {"type": "text", "config_ref": "layers/text.toml", "name": "主线", "objects": [
            {"config_ref": "objects/text.toml", "name": "文本", "begin": 1, "end": 3, "information": {"text": "第一版", "extra": [1, True, None]}}
        ]}
        result = save_layer_with_checks(self.connection, self.project_id, source)
        self.assertTrue(result["ok"], result)
        self.assertEqual((source["id"], source["objects"][0]["id"], source["objects"][0]["layer"]), (1, 2, 1))
        self.assertEqual(result["checks"]["issues"], [])
        record = read_layer(self.connection, self.project_id, 1)
        self.assertEqual(record["objects"][0]["information"]["extra"], [1, True, None])
        record["objects"][0]["information"]["text"] = "第二版"
        changed = save_layer_with_checks(self.connection, self.project_id, record)
        self.assertTrue(changed["applied"])
        logs = crud.read(self.connection, "change", filters={"operation_id": changed["operation_id"]})
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["kind"], "object")
        unchanged = save_layer_with_checks(self.connection, self.project_id, record)
        self.assertFalse(unchanged["applied"])
        self.assertEqual(unchanged["checks"]["reason"], "no_changes")

    def test_python_objects_round_trip_without_new_metadata_fields(self):
        layer = self.layer(name="主线", axis={"unit": "秒"})
        obj = Text(layer=layer.id, information={"text": "内容"})
        layer.objects.append(obj)
        result = save_layer_with_checks(self.connection, self.project_id, layer)
        self.assertTrue(result["ok"], result)
        restored = load_layer(self.connection, self.project_id, layer.id)
        self.assertIsInstance(restored, TextLayer)
        self.assertIsInstance(restored.objects[0], Text)
        self.assertIs(restored.return_self(), restored)
        self.assertIs(restored.objects[0].return_self(), restored.objects[0])
        self.assertFalse(hasattr(restored.objects[0], "config_ref"))
        restored.objects[0].information["text"] = "修改"
        changed = save_layer_with_checks(self.connection, self.project_id, restored)
        self.assertTrue(changed["ok"], changed)
        self.assertEqual(load_object(self.connection, self.project_id, obj.id).information["text"], "修改")

    def test_outgoing_binds_round_trip_and_cross_project_identity(self):
        layer = self.layer()
        other_project = self.project()
        target = TextLayer()
        save_layer_with_checks(self.connection, other_project, target)
        obj = Text(layer=layer.id, information={"text": "source"}, bind=[{
            "target_kind": "layer", "target_project_id": other_project, "target_id": target.id, "tips": "引用",
        }])
        result = save_object_with_checks(self.connection, self.project_id, obj)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["checks"]["issues"], [])
        binding_id = obj.bind[0]["id"]
        restored = load_object(self.connection, self.project_id, obj.id)
        self.assertEqual(restored.bind[0]["target_project_id"], other_project)
        self.assertEqual(restored.bind[0]["source_id"], obj.id)
        self.assertEqual(read_layer(self.connection, other_project, target.id)["bind"], [])
        restored.bind[0]["tips"] = "更新引用说明"
        result = save_object_with_checks(self.connection, self.project_id, restored)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(crud.read(self.connection, "bind")), 1)
        self.assertEqual(crud.read(self.connection, "bind", id=binding_id)["tips"], "更新引用说明")

    def test_partial_save_does_not_delete_omitted_objects_or_binds(self):
        layer = self.layer()
        obj = Text(layer=layer.id, bind=[{"target_kind": "layer", "target_project_id": self.project_id, "target_id": layer.id}])
        save_object_with_checks(self.connection, self.project_id, obj)
        layer.objects = []
        self.assertTrue(save_layer_with_checks(self.connection, self.project_id, layer)["ok"])
        obj.bind = []
        self.assertTrue(save_object_with_checks(self.connection, self.project_id, obj)["ok"])
        self.assertEqual(len(read_layer(self.connection, self.project_id, layer.id)["objects"]), 1)
        self.assertEqual(len(read_object(self.connection, self.project_id, obj.id)["bind"]), 1)
        result = dispatch(self.connection, {"action": "delete", "kind": "bind", "id": crud.read(self.connection, "bind")[0]["id"]})
        self.assertTrue(result["applied"])

    def test_partial_record_updates_and_membership_change(self):
        first, second = self.layer(), self.layer()
        obj = Text(layer=first.id, information={"text": "keep"})
        save_object_with_checks(self.connection, self.project_id, obj)
        result = save_layer_with_checks(self.connection, self.project_id, {"id": second.id, "objects": [{"id": obj.id, "name": "moved"}]})
        self.assertTrue(result["ok"], result)
        self.assertEqual(read_layer(self.connection, self.project_id, first.id)["objects"], [])
        record = read_object(self.connection, self.project_id, obj.id)
        self.assertEqual(record["layer"], second.id)
        self.assertEqual(record["information"], {"text": "keep"})
        self.assertEqual(record["config_ref"], "objects/text.toml")

    def test_failure_rolls_back_records_counter_log_and_python_ids(self):
        layer = self.layer()
        before_logs = len(crud.read(self.connection, "change"))
        good = Text(layer=layer.id, information={"text": "good"}, bind=[{
            "target_kind": "layer", "target_project_id": self.project_id, "target_id": layer.id,
        }])
        bad = Text(layer=layer.id, information={"not_json": object()})
        layer.name = "unsaved"
        layer.objects = [good, bad]
        result = save_layer_with_checks(self.connection, self.project_id, layer)
        self.assertFalse(result["ok"])
        self.assertIsNone(good.id)
        self.assertIsNone(bad.id)
        self.assertNotIn("id", good.bind[0])
        self.assertEqual(read_layer(self.connection, self.project_id, layer.id)["name"], "")
        self.assertEqual(crud.read(self.connection, "project", id=self.project_id)["max_id"], 1)
        self.assertEqual(len(crud.read(self.connection, "change")), before_logs)
        self.assertEqual(crud.read(self.connection, "bind"), [])

    def test_whole_save_checks_once_after_commit_with_shared_log_id(self):
        layer = self.layer()
        layer.objects = [Text(layer=layer.id, information={"text": word}) for word in ("a", "b")]
        calls = []

        def checker(changes, read_record):
            self.assertFalse(self.connection.in_transaction)
            self.assertEqual(len(read_record("object", project_id=self.project_id)), 2)
            calls.append(changes)
            raise RuntimeError("checker unavailable")

        result = save_layer_with_checks(self.connection, self.project_id, layer, checker=checker)
        self.assertTrue(result["ok"])
        self.assertEqual(result["checks"]["status"], "failed")
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(obj.id is not None for obj in layer.objects))
        logs = crud.read(self.connection, "change", filters={"operation_id": result["operation_id"]})
        self.assertEqual(len(logs), 2)

    def test_derived_title_keeps_its_class_and_config_when_saved_again(self):
        layer = self.layer()
        layer.objects = [Title(layer=layer.id, information={"text": "title"}), Text(layer=layer.id)]
        result = save_layer_with_checks(self.connection, self.project_id, layer, config_root=self.configs)
        self.assertTrue(result["ok"], result)
        loaded = load_layer(self.connection, self.project_id, layer.id, config_root=self.configs)
        self.assertIs(type(loaded.objects[0]), Title)
        self.assertIs(type(loaded.objects[1]), Text)
        loaded.objects[0].tips = "edit"
        result = save_layer_with_checks(self.connection, self.project_id, loaded, config_root=self.configs)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["objects"][0]["config_ref"], "objects/title.toml")
        self.assertEqual(result["data"]["objects"][1]["config_ref"], "objects/text.toml")

    def test_missing_config_does_not_prevent_raw_io_but_load_explains_target(self):
        layer = self.layer()
        result = dispatch(self.connection, {"action": "create", "kind": "object", "project_id": self.project_id,
                                           "data": {"layer": layer.id, "config_ref": "objects/missing.toml"}})
        self.assertTrue(result["ok"])
        self.assertEqual(result["checks"]["status"], "partial")
        self.assertEqual(read_object(self.connection, self.project_id, result["id"])["config_ref"], "objects/missing.toml")
        with self.assertRaisesRegex(ValueError, "objects/missing.toml"):
            load_object(self.connection, self.project_id, result["id"])

    def test_read_missing_and_read_inside_callers_transaction(self):
        self.assertIsNone(read_layer(self.connection, self.project_id, 999))
        self.assertIsNone(load_object(self.connection, self.project_id, 999))
        layer = self.layer()
        self.connection.execute("UPDATE layers SET name='pending' WHERE project_id=? AND id=?", (self.project_id, layer.id))
        self.assertEqual(read_layer(self.connection, self.project_id, layer.id)["name"], "pending")
        self.assertTrue(self.connection.in_transaction)
        self.assertFalse(save_layer_with_checks(self.connection, self.project_id, layer)["ok"])
        self.assertTrue(self.connection.in_transaction)
        self.connection.rollback()
        self.assertEqual(read_layer(self.connection, self.project_id, layer.id)["name"], "")

    def test_saving_deleted_id_or_wrong_project_cannot_silently_create(self):
        layer = self.layer()
        record = read_layer(self.connection, self.project_id, layer.id)
        other_project = self.project()
        self.assertFalse(save_layer_with_checks(self.connection, other_project, record)["ok"])
        dispatch(self.connection, {"action": "delete", "kind": "layer", "project_id": self.project_id, "id": layer.id})
        self.assertFalse(save_layer_with_checks(self.connection, self.project_id, layer)["ok"])

    def test_cannot_overwrite_bind_owned_by_another_entity(self):
        first, second = self.layer(), self.layer()
        first.bind = [{"target_kind": "layer", "target_project_id": self.project_id, "target_id": second.id}]
        save_layer_with_checks(self.connection, self.project_id, first)
        second.bind = [{"id": first.bind[0]["id"], "tips": "wrong owner"}]
        result = save_layer_with_checks(self.connection, self.project_id, second)
        self.assertFalse(result["ok"])
        self.assertEqual(crud.read(self.connection, "bind")[0]["source_id"], first.id)

    def test_new_python_subclass_is_loaded_from_config_without_core_changes(self):
        module_name = "layerweave_example_types"
        (self.root / f"{module_name}.py").write_text('from layerweave.models.objects.text import Text\nclass Dialogue(Text):\n    pass\n', encoding="utf-8")
        sys.path.insert(0, str(self.root))
        self.addCleanup(sys.path.remove, str(self.root))
        self.addCleanup(sys.modules.pop, module_name, None)
        Dialogue = import_module(module_name).Dialogue
        (self.configs / "objects/dialogue.toml").write_text('[object]\ntype="dialogue"\nextends="text.toml"\nclass="layerweave_example_types:Dialogue"\n', encoding="utf-8")
        layer = self.layer()
        obj = Dialogue(layer=layer.id, information={"text": "custom"})
        result = save_object_with_checks(self.connection, self.project_id, obj, config_root=self.configs)
        self.assertTrue(result["ok"], result)
        self.assertIsInstance(load_object(self.connection, self.project_id, obj.id, config_root=self.configs), Dialogue)

    def test_all_builtin_types_survive_database_reopen_and_full_cli_read(self):
        from layerweave import models
        path = self.root / "round-trip.sqlite3"
        initialize_database(path)
        with closing(open_database(path)) as connection:
            project_id = dispatch(connection, {"action": "create", "kind": "project", "data": {}})["id"]
            ids = []
            for prefix in ("Text", "Data", "Image", "Audio", "Movie", "Model", "Active"):
                layer = getattr(models, prefix + "Layer")(name=prefix)
                result = save_layer_with_checks(connection, project_id, layer)
                self.assertTrue(result["ok"], result)
                layer.objects.append(getattr(models, prefix)(layer=layer.id, information={"arbitrary": {"unicode": "中文"}}))
                result = save_layer_with_checks(connection, project_id, layer)
                self.assertTrue(result["ok"], result)
                ids.append((layer.id, prefix))
        with closing(open_database(path)) as connection:
            for layer_id, prefix in ids:
                loaded = load_layer(connection, project_id, layer_id)
                self.assertIsInstance(loaded, getattr(models, prefix + "Layer"))
                self.assertIsInstance(loaded.objects[0], getattr(models, prefix))
                self.assertEqual(loaded.objects[0].information["arbitrary"]["unicode"], "中文")
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", "layerweave.tool.builtin.usage.records.cli", str(path)],
                                input=json.dumps({"action": "read", "kind": "layer", "project_id": project_id, "id": ids[0][0], "full": True}),
                                text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(len(response["data"]["objects"]), 1)
        self.assertEqual(response["checks"]["status"], "not_run")

    def test_api_import_does_not_load_all_models_or_rules(self):
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c",
            'import sys; import layerweave.support.api; assert "layerweave.models.objects.active" not in sys.modules; assert "layerweave.tool.builtin.usage.validation.runner" not in sys.modules'],
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

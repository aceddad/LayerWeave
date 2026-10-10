"""错误可修正、提交状态明确，关联诊断不冒充历史问题。"""

from functools import partial
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from layerweave.models import Text, TextLayer
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.support.api import format_feedback, initialize_database, open_database
from layerweave.tool.builtin.usage.records.save import save_layer
from layerweave.tool.builtin.usage.validation.runner import validate
from layerweave.support.configuration.loader import DEFAULT_ROOT, ConfigError, Loader
from layerweave.support.storage import crud
from layerweave.support.storage.database import SCHEMA_PATH


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-feedback-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.configs = self.root / "configs"
        shutil.copytree(DEFAULT_ROOT, self.configs)
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.project = self.call("create", "project", data={})["id"]
        self.layer = self.call("create", "layer", data={"config_ref": "layers/text.toml"})["id"]

    def call(self, action, kind, **args):
        if kind in {"layer", "object"}:
            args.setdefault("project_id", self.project)
        return dispatch(self.connection, {"action": action, "kind": kind, **args}, config_root=self.configs)

    def obj(self, **extra):
        return self.call("create", "object", data={"layer": self.layer, "config_ref": "objects/text.toml",
                                                   "information": {"text": "正文"}, **extra})

    def test_unknown_kind_and_action_offer_applicable_choices(self):
        for action in ("read", "create"):
            error = self.call(action, "objects", **({"data": {}} if action == "create" else {}))["error"]
            self.assertEqual(error["code"], "unknown_kind")
            self.assertIn("object", error["allowed"])
            self.assertEqual("change" in error["allowed"], action == "read")
        error = self.call("add", "object", data={})["error"]
        self.assertEqual(error["allowed"], ["create", "read", "update", "delete"])
        error = self.call("create", "change", data={})["error"]
        self.assertEqual(error["allowed"], ["read"])

    def test_unknown_fields_offer_hints_without_accepting_aliases(self):
        result = self.obj(start=1, infomation={})
        self.assertEqual(result["operation"]["status"], "failed")
        error = result["error"]
        self.assertIn("begin", error["allowed"])
        self.assertEqual(error["suggestions"], {"infomation": "information", "start": "begin"})
        self.assertEqual(crud.read(self.connection, "object", project_id=self.project), [])
        text = format_feedback(result)
        self.assertIn("start → begin", text)
        self.assertIn("可选值", text)
        # information 仍开放；提示顶层字段不改变内容容错规则。
        self.assertTrue(self.obj(information={"text": "正文", "start": 1})["ok"])

    def test_missing_foreign_keys_identify_scope_and_field(self):
        result = self.obj(layer=99)
        self.assertEqual(result["error"]["message"], f"所属层 ({self.project}, 99) 不存在")
        self.assertEqual(result["error"]["field"], "layer")
        self.assertEqual(result["error"]["type"], "IntegrityError")
        result = self.call("create", "layer", data={"config_ref": "layers/text.toml", "father": 99})
        self.assertIn("父层", result["error"]["message"])
        self.assertEqual(result["error"]["field"], "father")
        other = self.call("create", "project", data={})["id"]
        result = self.call("create", "object", project_id=other, data={"layer": self.layer, "config_ref": "objects/text.toml"})
        self.assertEqual(result["error"]["reference"], {"kind": "layer", "project_id": other, "id": self.layer})
        result = self.call("create", "object", project_id=999, data={"layer": 99, "config_ref": "objects/text.toml"})
        self.assertEqual(result["error"]["field"], "project_id")

    def test_null_and_other_sql_failures_are_not_called_missing_layers(self):
        result = self.obj(layer=None)
        self.assertEqual(result["error"]["code"], "null_field")
        self.connection.execute("CREATE TRIGGER reject_object BEFORE INSERT ON objects BEGIN SELECT RAISE(ABORT, 'custom rejection'); END")
        result = self.obj()
        self.assertIn("custom rejection", result["error"]["message"])
        self.assertNotEqual(result["error"].get("code"), "missing_reference")

    def test_delete_error_identifies_referencing_object_and_preserves_data(self):
        obj = self.obj()
        result = self.call("delete", "layer", id=self.layer)
        self.assertEqual(result["error"]["code"], "reference_in_use")
        self.assertEqual(result["error"]["reference"]["id"], obj["id"])
        self.assertEqual(result["operation"]["changes"], [])
        self.assertIsNotNone(crud.read(self.connection, "layer", project_id=self.project, id=self.layer))
        project = self.call("delete", "project", id=self.project)
        self.assertEqual(project["error"]["reference"]["kind"], "layer")

    def test_failed_batch_explains_references_before_rolling_everything_back(self):
        result = dispatch(self.connection, [
            {"action": "create", "kind": "object", "project_id": self.project,
             "data": {"layer": self.layer, "config_ref": "objects/text.toml"}},
            {"action": "delete", "kind": "layer", "project_id": self.project, "id": self.layer},
        ])
        self.assertEqual(result["error"]["reference"]["id"], 2)
        self.assertEqual(result["error"]["request_index"], 1)
        self.assertEqual(result["operation"], {"status": "failed", "changes": []})
        self.assertNotIn("写入成功", format_feedback(result))
        self.assertEqual(crud.read(self.connection, "object", project_id=self.project), [])
        self.assertEqual(crud.read(self.connection, "project", id=self.project)["max_id"], 1)

    def test_missing_config_uses_relative_paths_and_bounded_same_kind_candidates(self):
        for index in range(12):
            (self.configs / f"objects/extra_{index}.toml").write_text("# 尚未完成的示例\n", encoding="utf-8")
        result = self.obj(config_ref="objects/txt.toml")
        issue = next(item for item in result["checks"]["issues"] if item.get("code") == "config_not_found")
        self.assertEqual(issue["candidates"][0], "objects/text.toml")
        self.assertLessEqual(len(issue["candidates"]), 8)
        self.assertGreater(issue["candidate_count"], len(issue["candidates"]))
        self.assertTrue(all(ref.startswith("objects/") for ref in issue["candidates"]))
        self.assertNotIn(str(self.configs), json.dumps(result, ensure_ascii=False))
        self.assertNotIn("Errno", issue["message"])

    def test_bad_toml_is_distinguished_from_missing_file(self):
        (self.configs / "objects/broken.toml").write_text("[object\n", encoding="utf-8")
        with self.assertRaises(ConfigError) as caught:
            Loader(self.configs).load("objects/broken.toml", "object")
        self.assertNotEqual(caught.exception.details.get("code"), "config_not_found")
        self.assertIn("objects/broken.toml", str(caught.exception))
        self.assertNotIn(str(self.configs), str(caught.exception))

    def test_success_and_related_config_error_are_separate(self):
        self.obj()
        bad = self.obj(config_ref="objects/txt.toml")
        self.assertTrue(all(item["scope"] == "direct" for item in bad["checks"]["issues"]))
        result = self.obj()
        self.assertEqual(result["operation"], {"status": "committed", "changes": [
            {"action": "create", "target": {"kind": "object", "project_id": self.project, "id": result["id"]}},
        ]})
        issue = result["checks"]["issues"][0]
        self.assertEqual(issue["target"]["id"], bad["id"])
        self.assertEqual(issue["scope"], "related")
        self.assertEqual(issue["checked_target"]["id"], self.layer)
        self.assertEqual(issue["field"], "config_ref")
        rendered = format_feedback(result)
        self.assertTrue(rendered.startswith(f"[写入成功] object ({self.project}, {result['id']})：已创建"))
        self.assertIn("关联目标，本次未直接修改", rendered)
        self.assertNotIn("旧问题", rendered)
        self.assertEqual(len(crud.read(self.connection, "object", project_id=self.project)), 3)

    def test_new_overlap_with_existing_object_is_never_labelled_old(self):
        path = self.configs / "layers/text.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("overlap = true", "overlap = false"), encoding="utf-8")
        first = self.obj(begin=0, end=3)
        second = self.obj(begin=1, end=4)
        issue = next(item for item in second["checks"]["issues"] if item["rule"] == "overlap")
        self.assertEqual({item["id"] for item in issue["related"]}, {first["id"], second["id"]})
        self.assertEqual(issue["scope"], "related")  # 检查目标是未直接修改的层，不代表冲突原来就存在。
        self.assertNotIn("旧问题", format_feedback(second))

    def test_manual_validation_has_no_implicit_write_scope(self):
        self.obj(config_ref="objects/txt.toml")
        result = validate([{"kind": "layer", "project_id": self.project, "id": self.layer}],
                          partial(crud.read, self.connection), config_root=self.configs)
        self.assertTrue(result["issues"])
        self.assertTrue(all(item["scope"] == "manual" for item in result["issues"]))

    def test_read_noop_and_failed_checker_keep_distinct_statuses(self):
        result = self.call("read", "project", id=self.project)
        self.assertEqual(result["operation"]["status"], "read")
        self.assertIn('"max_id"', format_feedback(result))
        noop = self.call("update", "layer", id=self.layer, data={"name": ""})
        self.assertEqual(noop["operation"], {"status": "unchanged", "changes": []})
        def checker(changes, read):
            raise RuntimeError("检查器异常")
        result = dispatch(self.connection, {"action": "create", "kind": "project", "data": {}}, checker=checker)
        self.assertEqual(result["operation"]["status"], "committed")
        self.assertIn("[ERROR] 检测执行器", format_feedback(result))
        self.assertNotIn("[操作失败]", format_feedback(result))

    def test_model_save_feedback_lists_actual_nested_changes(self):
        layer = TextLayer()
        result = save_layer(self.connection, self.project, layer)
        self.assertEqual(result["operation"]["changes"][0]["target"]["id"], layer.id)
        layer.objects.append(Text(layer=layer.id, information={"text": "正文"}))
        result = save_layer(self.connection, self.project, layer)
        self.assertEqual(len(result["operation"]["changes"]), 1)
        self.assertEqual(result["operation"]["changes"][0]["target"]["kind"], "object")
        failed = save_layer(self.connection, self.project, {"id": layer.id, "objects": [
            {"config_ref": "objects/txt.toml"},
        ]})
        self.assertEqual(failed["error"]["target"]["kind"], "object")
        self.assertEqual(failed["operation"]["status"], "failed")

    def test_cli_text_mode_does_not_change_json_defaults_or_exit_codes(self):
        path = initialize_database(self.root / "cli.sqlite3")
        command = [sys.executable, "-X", "utf8", "-B", "-m", "layerweave.tool.builtin.usage.records.cli", str(path)]
        def run(request, *flags):
            return subprocess.run([*command, *flags], input=json.dumps(request), text=True, encoding="utf-8", capture_output=True)
        created = run({"action": "create", "kind": "project", "data": {}})
        self.assertEqual(json.loads(created.stdout)["operation"]["status"], "committed")
        layer = run({"action": "create", "kind": "layer", "project_id": 1, "data": {"config_ref": "layers/text.toml"}})
        self.assertEqual(layer.returncode, 0, layer.stderr)
        checked = run({"action": "create", "kind": "object", "project_id": 1,
                       "data": {"layer": 1, "config_ref": "objects/text.toml", "information": {"text": 123}}}, "--text")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("[写入成功]", checked.stdout)
        self.assertIn("[ERROR]", checked.stdout)
        failed = run({"action": "add", "kind": "object", "project_id": 1}, "--text")
        self.assertEqual(failed.returncode, 1)
        self.assertIn("可选值：create / read / update / delete", failed.stdout)
        tool = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", "layerweave.tool.builtin.usage.editing.positions", str(path), "1",
                               "--text", "duration", "2", "2"], text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(tool.returncode, 0, tool.stderr)
        self.assertIn("[写入成功] object (1, 2)：已更新", tool.stdout)

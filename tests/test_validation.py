"""从公开分流入口验证规则、触发范围、批次最终状态和逐条反馈。"""

from functools import partial
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from runtime.configuration.loader import DEFAULT_ROOT
from runtime.dispatch import dispatch
from runtime.storage import crud
from runtime.storage.database import SCHEMA_PATH, open_database
from runtime.validation.registry import RULES
from runtime.validation.runner import check_changes, validate


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-production-rules-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "configs"
        shutil.copytree(DEFAULT_ROOT, self.root)
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.checker = partial(check_changes, config_root=self.root)
        self.project = self.call("create", "project", data={})["id"]
        self.layer_id = self.layer()["id"]

    def call(self, action, kind, **args):
        if kind in {"layer", "object"}:
            args.setdefault("project_id", self.project)
        return dispatch(self.connection, {"action": action, "kind": kind, **args}, checker=self.checker)

    def layer(self, **data):
        return self.call("create", "layer", data={"type": "text", "config_ref": "layers/text.toml", **data})

    def obj(self, **data):
        return self.call("create", "object", data={"layer": self.layer_id, "config_ref": "objects/text.toml", **data})

    def write(self, ref, content):
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def track(self):
        self.write("layers/track.toml", '[layer]\ntype="track"\nextends="base.toml"\nobjects="text"\n[layer.constraint]\noverlap=false\n')
        return self.layer(type="track", config_ref="layers/track.toml")["id"]

    def issues(self, result, rule):
        return [issue for issue in result["checks"]["issues"] if issue["rule"] == rule]

    def test_object_requires_existing_layer_and_rolls_back_allocation(self):
        before = crud.read(self.connection, "project", id=self.project)["max_id"]
        for data in ({}, {"layer": None}, {"layer": 999}):
            result = self.call("create", "object", data={"config_ref": "objects/text.toml", **data})
            self.assertFalse(result["ok"])
        self.assertEqual(crud.read(self.connection, "project", id=self.project)["max_id"], before)

    def test_missing_content_warns_but_negative_position_and_optional_root_axis_are_allowed(self):
        result = self.obj(begin=-3, end=-1, information={"extra": [1, 2]})
        self.assertTrue(result["ok"])
        self.assertEqual(result["checks"]["status"], "completed")
        self.assertEqual([item["field"] for item in result["checks"]["issues"]], ["information.text"])
        self.assertEqual(result["checks"]["issues"][0]["severity"], "warn")

    def test_content_error_is_saved_and_names_do_not_recheck_it(self):
        obj = self.obj(information={"text": 123})
        self.assertTrue(obj["applied"])
        self.assertEqual(len(self.issues(obj, "fields")), 1)
        renamed = self.call("update", "object", id=obj["id"], data={"name": "renamed"})
        self.assertEqual(renamed["checks"]["issues"], [])
        self.assertEqual(renamed["data"]["information"], {"text": 123})

    def test_inheritance_compatibility_and_config_ref_change(self):
        self.write("objects/dialogue.toml", '[object]\ntype="dialogue"\nextends="text.toml"\n[object.information]\nspeaker={type="str"}\n')
        result = self.obj(config_ref="objects/dialogue.toml", information={"text": "hello", "speaker": "A"})
        self.assertEqual(result["checks"]["issues"], [])
        changed = self.call("update", "object", id=result["id"], data={"config_ref": "objects/image.toml"})
        self.assertEqual(len(self.issues(changed, "accepts_objects")), 1)
        base = self.obj(config_ref="objects/base.toml", information={"text": "has text but is not Text"})
        self.assertEqual(len(self.issues(base, "accepts_objects")), 2)  # 两个真实不兼容对象，各报告一条。

    def test_missing_config_does_not_stop_other_objects_or_base_checks(self):
        result = dispatch(self.connection, [
            {"action": "create", "kind": "object", "project_id": self.project,
             "data": {"layer": self.layer_id, "config_ref": "objects/missing.toml", "begin": 4, "end": 1}},
            {"action": "create", "kind": "object", "project_id": self.project,
             "data": {"layer": self.layer_id, "config_ref": "objects/text.toml", "information": {"text": 123}}},
        ], checker=self.checker)
        self.assertTrue(result["applied"])
        self.assertEqual(result["checks"]["status"], "partial")
        self.assertEqual(len(self.issues(result, "begin_le_end")), 1)
        self.assertEqual(len(self.issues(result, "fields")), 1)
        self.assertTrue(self.issues(result, "configuration"))

    def test_axis_option_parent_change_and_no_root_requirement(self):
        child = self.layer(father=self.layer_id, axis={"unit": "frame"})
        self.assertEqual(len(self.issues(child, "axis_only_on_root")), 1)
        self.write("layers/local.toml", '[layer]\ntype="local"\nextends="text.toml"\n[layer.options]\naxis_only_on_root=false\n')
        changed = self.call("update", "layer", id=child["id"], data={"config_ref": "layers/local.toml", "type": "local"})
        self.assertEqual(changed["checks"]["issues"], [])
        root = self.layer(axis={"unit": "second"})
        changed = self.call("update", "layer", id=root["id"], data={"father": self.layer_id})
        self.assertEqual(len(self.issues(changed, "axis_only_on_root")), 1)

    def test_father_cycle_is_reported_but_saved_and_notes_do_not_traverse(self):
        child = self.layer(father=self.layer_id)
        result = self.call("update", "layer", id=self.layer_id, data={"father": child["id"]})
        self.assertTrue(result["applied"])
        self.assertEqual(len(self.issues(result, "no_cycle")), 1)
        with patch("runtime.validation.rules.layers.no_cycle", side_effect=AssertionError("must not traverse")):
            result = self.call("update", "layer", id=self.layer_id, data={"tips": "note"})
            self.assertEqual(result["checks"]["issues"], [])

    def test_overlap_all_endpoint_cases(self):
        cases = [((1, 3), (3, 5), False), ((1, 4), (3, 5), True),
                 ((3, 3), (1, 3), False), ((3, 3), (3, 5), True),
                 ((3, 3), (3, 3), True), ((2, 2), (1, 3), True),
                 ((1, 5), (2, 4), True), ((0, 0), (1, 1), False)]
        for first, second, expected in cases:
            with self.subTest(first=first, second=second):
                layer_id = self.track()
                self.obj(layer=layer_id, begin=first[0], end=first[1])
                result = self.obj(layer=layer_id, begin=second[0], end=second[1])
                self.assertEqual(bool(self.issues(result, "overlap")), expected)

    def test_overlap_batch_deduplicates_rule_but_preserves_distinct_pairs(self):
        layer_id = self.track()
        with patch("runtime.validation.rules.layers.overlap", wraps=__import__("runtime.validation.rules.layers", fromlist=["overlap"]).overlap) as check:
            result = dispatch(self.connection, [
                {"action": "create", "kind": "object", "project_id": self.project,
                 "data": {"layer": layer_id, "config_ref": "objects/text.toml", "begin": 1, "end": 4}}
                for _ in range(3)
            ], checker=self.checker)
        self.assertEqual(check.call_count, 1)
        self.assertEqual(len(self.issues(result, "overlap")), 3)

    def test_only_final_state_is_checked_including_create_then_delete(self):
        obj = self.obj(begin=0, end=1)
        result = dispatch(self.connection, [
            {"action": "update", "kind": "object", "project_id": self.project, "id": obj["id"], "data": {"begin": 4}},
            {"action": "update", "kind": "object", "project_id": self.project, "id": obj["id"], "data": {"end": 5}},
        ], checker=self.checker)
        self.assertEqual(result["checks"]["issues"], [])
        next_id = crud.read(self.connection, "project", id=self.project)["max_id"] + 1
        result = dispatch(self.connection, [
            {"action": "create", "kind": "object", "project_id": self.project,
             "data": {"layer": self.layer_id, "config_ref": "objects/missing.toml"}},
            {"action": "delete", "kind": "object", "project_id": self.project, "id": next_id},
        ], checker=self.checker)
        self.assertEqual(result["checks"]["issues"], [])

    def test_move_and_layer_config_change_trigger_membership_rules(self):
        image_layer = self.layer(type="image", config_ref="layers/image.toml")["id"]
        obj = self.obj()
        moved = self.call("update", "object", id=obj["id"], data={"layer": image_layer})
        self.assertEqual(len(self.issues(moved, "accepts_objects")), 1)
        changed = self.call("update", "layer", id=image_layer, data={"config_ref": "layers/text.toml", "type": "text"})
        self.assertEqual(changed["checks"]["issues"], [])

    def test_duration_and_invalid_input_skip_dependent_arithmetic(self):
        self.write("objects/positive.toml", '[object]\ntype="positive"\nextends="base.toml"\n[object.constraint]\nduration="positive"\n')
        layer = self.layer(type="Layer", config_ref="layers/base.toml")["id"]
        result = self.obj(layer=layer, config_ref="objects/positive.toml")
        self.assertEqual(len(self.issues(result, "duration")), 1)
        invalid = self.obj(begin="bad", end=2, information={"text": ""})
        self.assertTrue(invalid["applied"])
        self.assertEqual(invalid["checks"]["status"], "partial")
        self.assertEqual(len(self.issues(invalid, "fields")), 1)
        self.assertTrue(self.issues(invalid, "begin_le_end")[0]["skipped"])

    def test_bind_checks_both_ends_and_deleted_targets(self):
        obj = self.obj()
        bind = self.call("create", "bind", data={
            "source_kind": "layer", "source_project_id": self.project, "source_id": self.layer_id,
            "target_kind": "object", "target_project_id": self.project, "target_id": obj["id"],
        })
        self.assertEqual(bind["checks"]["issues"], [])
        deleted = self.call("delete", "object", id=obj["id"])
        self.assertEqual(len(self.issues(deleted, "bind_endpoints")), 1)
        changed = self.call("update", "bind", id=bind["id"], data={"source_id": 999})
        self.assertEqual(len(self.issues(changed, "bind_endpoints")), 2)
        self.assertIsNotNone(crud.read(self.connection, "bind", id=bind["id"]))

    def test_unknown_rule_invalid_parameter_and_rule_failure_continue(self):
        self.write("objects/custom.toml", '[object]\ntype="custom"\nextends="base.toml"\n[object.rules]\nunknown=true\n[object.constraint]\nduration="mystery"\n')
        result = self.obj(config_ref="objects/custom.toml", begin=4, end=1)
        self.assertEqual(result["checks"]["status"], "partial")
        self.assertTrue(self.issues(result, "begin_le_end"))
        self.assertTrue(self.issues(result, "configuration"))
        with patch("runtime.validation.rules.fields.check", side_effect=RuntimeError("broken rule")):
            result = self.obj(begin=5, end=1)
        self.assertEqual(result["checks"]["status"], "partial")
        self.assertTrue(self.issues(result, "begin_le_end"))
        self.assertIn("broken rule", self.issues(result, "fields")[0]["message"])

    def test_manual_recheck_reads_edited_config_without_changing_journal(self):
        obj = self.obj(information={"text": "hello"})
        count = len(crud.read(self.connection, "change"))
        path = self.root / "objects/text.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('text = { type = "str"', 'text = { type = "int"'), encoding="utf-8")
        result = validate([{"kind": "project", "id": self.project}], partial(crud.read, self.connection), config_root=self.root)
        self.assertEqual(result["status"], "completed")
        self.assertTrue(any(issue.get("field") == "information.text" for issue in result["issues"]))
        self.assertEqual(len(crud.read(self.connection, "change")), count)

    def test_lazy_imports_and_required_python_layer(self):
        code = '''import sys
import models
assert "models.objects.active" not in sys.modules
from models import Text, Layer
assert "models.objects.active" not in sys.modules
assert "models.layers.active" not in sys.modules
assert "runtime.validation.rules.layers" not in sys.modules
obj = Text(layer=1)
assert obj.return_self() is obj
try:
    Text()
except TypeError:
    pass
else:
    raise AssertionError("layer must be provided")
'''
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_new_rule_uses_registry_without_changing_runner(self):
        self.write("objects/title.toml", '[object]\ntype="title"\nextends="text.toml"\n[object.rules]\ntext_nonempty=true\n')
        module = Path(self.temp.name) / "custom_rule.py"
        module.write_text('def check(record, config, read_record):\n    return [{"severity":"error", "field":"information.text", "message":"标题不能为空"}] if record["information"].get("text") == "" else []\n', encoding="utf-8")
        sys.path.insert(0, self.temp.name)
        self.addCleanup(sys.path.remove, self.temp.name)
        self.addCleanup(sys.modules.pop, "custom_rule", None)
        entry = {"function": "custom_rule:check", "triggers": {"object": ("information",)},
                 "scope": "self", "setting": ("rules", "text_nonempty")}
        with patch.dict(RULES, {"text_nonempty": entry}):
            result = self.obj(config_ref="objects/title.toml", information={"text": ""})
            self.assertEqual(len(self.issues(result, "text_nonempty")), 1)
            with patch("custom_rule.check", side_effect=AssertionError("unrelated update")):
                result = self.call("update", "object", id=result["id"], data={"tips": "note"})
                self.assertEqual(result["checks"]["issues"], [])

    def test_default_checker_import_failure_preserves_operation_result(self):
        with patch.dict(sys.modules, {"runtime.validation.runner": None}):
            result = dispatch(self.connection, {"action": "create", "kind": "object", "project_id": self.project,
                                               "data": {"layer": self.layer_id, "config_ref": "objects/text.toml"}})
        self.assertTrue(result["ok"])
        self.assertTrue(result["applied"])
        self.assertEqual(result["checks"]["status"], "failed")
        self.assertIsNotNone(crud.read(self.connection, "object", project_id=self.project, id=result["id"]))

    def test_rule_declared_for_wrong_kind_is_not_silently_accepted(self):
        self.write("objects/wrong.toml", '[object]\ntype="wrong"\nextends="text.toml"\n[object.rules]\nno_cycle=true\n')
        result = self.obj(config_ref="objects/wrong.toml")
        self.assertEqual(result["checks"]["status"], "partial")
        self.assertIn("rules.no_cycle", self.issues(result, "configuration")[0]["message"])

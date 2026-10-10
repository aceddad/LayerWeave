"""汇报等级、同因诊断和统一刻度的端到端回归。"""

from functools import partial
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from layerweave.models import Text, TextLayer
from layerweave.support.api import diagnostic_report, format_feedback, load_object, open_database, read_object
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.tool.builtin.usage.records.save import save_layer, save_object
from layerweave.tool.builtin.usage.validation.runner import validate
from layerweave.support.configuration.loader import DEFAULT_ROOT
from layerweave.support.storage import crud
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.tool.builtin.usage.text.collect import collect_text


class ReportingPrecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-reporting-")
        self.addCleanup(self.temp.cleanup)
        self.configs = Path(self.temp.name) / "configs"
        shutil.copytree(DEFAULT_ROOT, self.configs)
        self.policy = self.configs / "logging" / "diagnostics.toml"
        path = self.configs / "layers/text.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("overlap = true", "overlap = false"), encoding="utf-8")
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.p = dispatch(self.c, {"action": "create", "kind": "project", "data": {}})["id"]
        self.layer = self.make_layer(axis={"precision": 0.001})

    def call(self, action, kind, **args):
        return dispatch(self.c, {"action": action, "kind": kind, "project_id": self.p, **args}, config_root=self.configs)

    def make_layer(self, **data):
        result = self.call("create", "layer", data={"config_ref": "layers/text.toml", **data})
        self.assertTrue(result["ok"], result)
        return result["id"]

    def obj(self, layer=None, **data):
        return self.call("create", "object", data={"layer": self.layer if layer is None else layer,
                         "config_ref": "objects/text.toml", "information": {"text": "正文"}, **data})

    def row(self, id):
        return read_object(self.c, self.p, id)

    def legacy(self, id, begin, end):
        # 仅模拟既有数据库中的未落点记录，不修改用户数据。
        self.c.execute('UPDATE objects SET "begin"=?, "end"=? WHERE project_id=? AND id=?', (begin, end, self.p, id))
        self.c.commit()

    def test_optional_fields_are_silent_but_types_and_typos_are_not(self):
        for kind in ("model", "active"):
            layer = self.make_layer(config_ref=f"layers/{kind}.toml")
            for information in ({}, {"source": "asset"}, {"data": {}}, {"source": "", "data": {}}):
                result = self.obj(layer, config_ref=f"objects/{kind}.toml", information=information)
                self.assertEqual(result["checks"]["issues"], [])
            bad = self.obj(layer, config_ref=f"objects/{kind}.toml", information={"data": "wrong"})
            self.assertEqual([(i["code"], i["severity"]) for i in bad["checks"]["issues"]], [("field_type", "error")])
            typo = self.obj(layer, config_ref=f"objects/{kind}.toml", information={"src": "asset"})
            self.assertEqual(typo["checks"]["issues"][0]["suggestions"], {"src": "source"})
        text = self.obj(information={"txt": "正文"})
        self.assertEqual(len(text["checks"]["issues"]), 1)
        self.assertEqual(text["checks"]["issues"][0]["code"], "field_typo")

    def test_missing_policy_and_unknown_diagnostic_default_to_warn(self):
        self.policy.unlink()
        result = self.obj(information={"text": 123})
        self.assertEqual(result["checks"]["issues"][0]["severity"], "warn")
        self.assertEqual(diagnostic_report([{"rule": "future_rule", "message": "扩展问题", "severity": "error"}],
                                           config_root=self.configs)["issues"][0]["severity"], "warn")

    def test_rule_switch_and_reporting_level_are_independent(self):
        self.policy.write_text('[levels]\nbegin_le_end="none"\n', encoding="utf-8")
        from layerweave.tool.builtin.usage.validation.rules.objects import begin_le_end
        with patch("layerweave.tool.builtin.usage.validation.rules.objects.begin_le_end", wraps=begin_le_end) as check:
            result = self.obj(begin=3, end=1)
        self.assertTrue(check.called)
        self.assertFalse(any(i["rule"] == "begin_le_end" for i in result["checks"]["issues"]))
        # 约束关闭后，单独把汇报级别改为 error 不能重新启用检查。
        base = self.configs / "objects/base.toml"
        base.write_text(base.read_text(encoding="utf-8").replace("begin_le_end       = true", "begin_le_end       = false"), encoding="utf-8")
        self.policy.write_text('[levels]\nbegin_le_end="error"\n', encoding="utf-8")
        with patch("layerweave.tool.builtin.usage.validation.rules.objects.begin_le_end", wraps=begin_le_end) as check:
            self.obj(begin=5, end=4)
        self.assertFalse(check.called)

    def test_field_override_takes_precedence_without_muting_type_errors(self):
        self.policy.write_text('[levels]\nmissing_field="error"\nfield_type="error"\n'
                              '[overrides."objects/text.toml".missing_field]\n"information.text"="none"\n', encoding="utf-8")
        self.assertEqual(self.obj(information={})["checks"]["issues"], [])
        result = self.obj(begin=1, end=2, information={"text": 123})
        self.assertEqual(result["checks"]["issues"][0]["severity"], "error")
        collected = collect_text(self.c, self.p, self.layer, config_root=self.configs)
        self.assertEqual(collected["status"], "partial")
        self.assertEqual([i["code"] for i in collected["issues"]], ["field_type"])

    def test_bad_policy_falls_back_without_hiding_committed_write(self):
        for source in ('[levels\n', '[levels]\nfield_type="wran"\n'):
            self.policy.write_text(source, encoding="utf-8")
            result = self.obj(information={"text": 123})
            self.assertTrue(result["ok"], result)
            self.assertTrue(any(i.get("code") == "diagnostics_config" for i in result["checks"]["issues"]))
            self.assertEqual(next(i for i in result["checks"]["issues"] if i.get("code") == "field_type")["severity"], "warn")

    def test_config_failure_merges_by_target_and_keeps_affected_checks(self):
        first = self.obj(config_ref="objects/txt.toml")
        issues = [i for i in first["checks"]["issues"] if i.get("code") == "config_not_found"]
        self.assertEqual(len(issues), 1)
        self.assertEqual({i["rule"] for i in issues[0]["affected_checks"]}, {"configuration", "accepts_objects"})
        second = self.obj(begin=1, end=2, config_ref="objects/txt.toml")
        issues = [i for i in second["checks"]["issues"] if i.get("code") == "config_not_found"]
        self.assertEqual({i["target"]["id"] for i in issues}, {first["id"], second["id"]})
        third = self.obj(begin=3, end=4)
        rendered = format_feedback(third)
        self.assertTrue(rendered.startswith("[写入成功]"))
        self.assertNotIn("[检查未完成]", rendered)
        self.assertNotIn("[检查完成]", rendered)
        self.assertIn("此项检查无法完成", rendered)

    def test_suppressed_failure_still_means_checks_are_partial(self):
        self.policy.write_text('[levels]\nconfig_not_found="none"\n', encoding="utf-8")
        result = self.obj(config_ref="objects/txt.toml")
        self.assertEqual(result["checks"], {"status": "partial", "issues": []})
        self.assertNotIn("[ERROR]", format_feedback(result))
        checks = validate([{"kind": "object", "project_id": self.p, "id": result["id"]}],
                          partial(crud.read, self.c), config_root=self.configs)
        self.assertEqual(checks, {"status": "partial", "issues": []})

    def test_direct_writes_and_legacy_values_compare_on_same_grid(self):
        first = self.obj(begin=0, end=0.1+0.2)
        self.assertEqual(first["data"]["end"], 0.3)
        self.legacy(first["id"], 0, 0.1+0.2)
        second = self.obj(begin=0.3, end=0.4)
        self.assertEqual(second["checks"]["issues"], [])
        self.assertEqual(self.row(first["id"])["end"], 0.1+0.2)
        unchanged = self.call("update", "object", id=first["id"], data={"name": "只改名字"})
        self.assertEqual(unchanged["data"]["end"], 0.1+0.2)
        normalized = self.call("update", "object", id=first["id"], data={"end": 0.1+0.2})
        log = crud.read(self.c, "change", filters={"operation_id": normalized["operation_id"]})[0]
        self.assertEqual(log["after_data"]["end"], 0.3)

    def test_default_precision_own_axis_and_nondecimal_steps(self):
        for axis in (None, {"unit": "秒"}):
            layer = self.make_layer(axis=axis)
            result = self.obj(layer, begin=-0.0000005, end=0.1234567)
            self.assertEqual((result["data"]["begin"], result["data"]["end"]), (-0.000001, 0.123457))
        local = self.make_layer(father=self.layer, axis={"unit": "帧"})
        self.assertEqual(self.obj(local, end=0.0000007)["data"]["end"], 0.000001)
        quarter = self.make_layer(axis={"precision": 0.25})
        self.assertEqual(self.obj(quarter, begin=-0.125, end=0.125)["data"]["begin"], -0.25)
        frame = self.make_layer(axis={"precision": 1/30})
        self.assertEqual(self.obj(frame, end=0.1+0.2)["data"]["end"], 0.3)

    def test_core_crud_and_model_backfill_use_actual_coordinates(self):
        from layerweave.support.api import transaction
        with transaction(self.c) as write:
            row, change = crud.create(self.c, "object", {"layer": self.layer, "config_ref": "objects/text.toml",
                                      "begin": 0.0004, "end": 0.1+0.2}, project_id=self.p, operation_id=write.operation_id)
        self.assertEqual((row["begin"], change["after"]["end"]), (0, 0.3))
        obj = Text(layer=self.layer, begin=1.0004, end=2.0004, information={"text": "正文"})
        result = save_object(self.c, self.p, obj, config_root=self.configs)
        self.assertEqual((obj.begin, obj.end), (1, 2))
        self.assertEqual(result["data"]["begin"], obj.begin)
        loaded = load_object(self.c, self.p, obj.id)
        self.assertEqual(loaded.end, obj.end)

    def test_failed_whole_save_does_not_backfill_normalized_positions(self):
        layer = TextLayer(axis={"precision": 0.001})
        save_layer(self.c, self.p, layer, config_root=self.configs)
        good = Text(layer=layer.id, begin=0.0004, end=1, information={"text": "正文"})
        layer.objects = [good, Text(layer=layer.id, information={"bad": object()})]
        result = save_layer(self.c, self.p, layer, config_root=self.configs)
        self.assertFalse(result["ok"])
        self.assertIsNone(good.id)
        self.assertEqual(good.begin, 0.0004)
        self.assertEqual(crud.read(self.c, "object", project_id=self.p), [])

    def test_move_requantizes_both_positions_and_batch_axis_changes_invalidate_cache(self):
        fine = self.make_layer(axis={"precision": 0.001})
        coarse = self.make_layer(axis={"precision": 0.01})
        obj = self.obj(fine, begin=2.006, end=3.006)
        moved = self.call("update", "object", id=obj["id"], data={"layer": coarse})
        self.assertEqual((moved["data"]["begin"], moved["data"]["end"]), (2.01, 3.01))
        child = self.make_layer(father=fine)
        results = dispatch(self.c, [
            {"action": "create", "kind": "object", "project_id": self.p,
             "data": {"layer": child, "config_ref": "objects/text.toml", "end": 0.0004}},
            {"action": "update", "kind": "layer", "project_id": self.p, "id": fine,
             "data": {"axis": {"precision": 0.01}}},
            {"action": "create", "kind": "object", "project_id": self.p,
             "data": {"layer": child, "config_ref": "objects/text.toml", "end": 0.006}},
        ], config_root=self.configs)["results"]
        self.assertEqual((results[0]["data"]["end"], results[2]["data"]["end"]), (0, 0.01))

    def test_axis_change_rechecks_descendants_without_rewriting_old_positions(self):
        child = self.make_layer(father=self.layer)
        first = self.obj(child, begin=0.1, end=0.4)
        self.obj(child, begin=0.4, end=0.6)
        changed = self.call("update", "layer", id=self.layer, data={"axis": {"precision": 1}})
        overlap = next(i for i in changed["checks"]["issues"] if i["rule"] == "overlap")
        self.assertEqual(overlap["target"]["id"], child)
        self.assertEqual(overlap["scope"], "related")
        self.assertEqual(self.row(first["id"])["end"], 0.4)

    def test_legacy_reversed_tail_is_an_instant_for_order_and_duration(self):
        path = self.configs / "objects/text.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('duration = "any"', 'duration = "zero"'), encoding="utf-8")
        obj = self.obj(begin=0.3, end=0.3)
        self.legacy(obj["id"], 0.1+0.2, 0.3)
        report = validate([{"kind": "object", "project_id": self.p, "id": obj["id"]}],
                          partial(crud.read, self.c), config_root=self.configs)
        self.assertEqual(report["issues"], [])

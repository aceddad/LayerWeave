"""配置拼写、单向收紧与提交后诊断的实际调用回归。"""
from functools import partial
from pathlib import Path
import shutil
import tempfile
import unittest

from layerweave.core.encapsulation import DefinitionError, merge_definition
from layerweave.support.api import open_database
from layerweave.support.configuration.loader import ConfigError, DEFAULT_ROOT, Loader
from layerweave.support.storage import crud
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.tool.builtin.usage.validation.runner import validate


class DeclarationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="layerweave-declarations-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "configs"
        shutil.copytree(DEFAULT_ROOT, self.root)
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.p = dispatch(self.c, {"action": "create", "kind": "project", "data": {}})["id"]
        self.layer = self.call("layer", {"config_ref": "layers/text.toml"})["id"]

    def call(self, kind, data):
        return dispatch(self.c, {"action": "create", "kind": kind, "project_id": self.p, "data": data},
                        config_root=self.root)

    def obj(self, ref="objects/custom.toml", **info):
        return self.call("object", {"config_ref": ref, "layer": self.layer, "information": {"text": "正文", **info}})

    def config(self, body, *, name="custom", parent="text"):
        ref = f"objects/{name}.toml"
        (self.root / ref).write_text(
            f'[object]\ntype="{name}"\nclass="fixture_types:{name}"\nextends="{parent}.toml"\n' + body,
            encoding="utf-8")
        return ref

    def test_section_typos_warn_without_reinterpreting_or_blocking_save(self):
        pairs = {"constraints": "constraint", "constrant": "constraint", "displays": "display",
                 "rule": "rules", "informations": "information", "option": "options", "exmaple": "example"}
        self.config('\n'.join(f'[object.{name}]\ncustom=true' for name in pairs))
        result = self.obj()
        self.assertEqual(result["operation"]["status"], "committed")
        self.assertEqual(result["checks"]["status"], "completed")
        hints = result["checks"]["issues"]
        self.assertEqual(len(hints), len(pairs))
        self.assertEqual({h["field"]: h["suggestions"][h["field"]] for h in hints},
                         {f"object.{a}": f"object.{b}" for a, b in pairs.items()})
        self.assertTrue(all(h["code"] == "config_typo" and h["severity"] == "warn" for h in hints))
        effective = Loader(self.root).load("objects/custom.toml", "object")
        self.assertEqual(effective["constraint"]["duration"], "any")
        self.assertIn("constraints", effective)

    def test_display_hint_points_to_declaring_parent_once_and_respects_policy(self):
        self.config('[object.display]\nvisiblity=false\n')
        ref = self.config('', name="child", parent="custom")
        result = self.obj(ref)
        hints = result["checks"]["issues"]
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["source_ref"], "objects/custom.toml")
        self.assertEqual(hints[0]["config_ref"], ref)
        self.assertEqual(hints[0]["field"], "object.display.visiblity")
        self.assertTrue(Loader(self.root).load(ref, "object")["display"]["visibility"])
        policy = self.root / "logging/diagnostics.toml"
        policy.write_text('[overrides."objects/custom.toml"]\nconfig_typo="none"\n', encoding="utf-8")
        # 汇报路径覆盖不继承；修改的是子封装自己的覆盖。
        self.assertEqual(len(self.obj(ref)["checks"]["issues"]), 1)
        policy.write_text(f'[overrides."{ref}"]\nconfig_typo="none"\n', encoding="utf-8")
        self.assertEqual(self.obj(ref)["checks"]["issues"], [])
        policy.write_text(f'[overrides."{ref}"]\nconfig_typo="error"\n', encoding="utf-8")
        result = self.obj(ref)
        self.assertEqual(result["checks"]["issues"][0]["severity"], "error")
        self.assertEqual(result["operation"]["status"], "committed")

    def test_valid_display_and_custom_sections_remain_quiet(self):
        self.config('[object.display]\nvisibility=true\n' + '\n'.join(
            f'[object.{name}]\ncustom=true' for name in ("my_checks", "timeline", "lyrics_rules", "audio", "tags")))
        self.assertEqual(self.obj()["checks"]["issues"], [])

    def test_default_display_typo_is_visible_during_manual_recheck(self):
        self.config('[object.defaults.display]\nvisiblity=false\n')
        result = self.obj()
        report = validate([{"kind": "object", "project_id": self.p, "id": result["id"]}],
                          partial(crud.read, self.c), config_root=self.root)
        self.assertEqual(report["status"], "completed")
        self.assertEqual([h["field"] for h in report["issues"]], ["object.defaults.display.visiblity"])
        self.assertEqual(report["issues"][0]["scope"], "manual")

    def test_open_can_narrow_inherit_and_add_fields_but_not_reopen(self):
        self.config('open=false\n[object.information]\nspeaker={type="str"}\n')
        child = self.config('', name="child", parent="custom")
        self.assertFalse(Loader(self.root).load(child, "object")["open"])
        self.assertEqual(self.obj(child, speaker="A")["checks"]["issues"], [])
        result = self.obj(child, speaker="A", extension=1)
        self.assertEqual(result["operation"]["status"], "committed")
        self.assertEqual([h["code"] for h in result["checks"]["issues"]], ["unknown_field"])
        self.assertEqual(result["data"]["information"]["extension"], 1)
        self.config('open=true\n', name="child", parent="custom")
        with self.assertRaisesRegex(ConfigError, "放宽父约定"):
            Loader(self.root).load(child, "object")

    def test_open_boolean_semantics_in_pure_core(self):
        parent = merge_definition(None, {"open": True})
        closed = merge_definition(parent, {"open": False})
        self.assertTrue(parent["open"])
        self.assertFalse(merge_definition(closed, {"open": False})["open"])
        self.assertFalse(merge_definition(None, {"open": False})["open"])
        for value in (0, 1, "false", None):
            with self.subTest(value=value), self.assertRaises(DefinitionError):
                merge_definition(parent, {"open": value})


if __name__ == "__main__":
    unittest.main()

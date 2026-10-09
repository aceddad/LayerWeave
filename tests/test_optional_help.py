"""可选字段是继承约定；两种 help 的说明与实际保存行为保持一致。"""

import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from runtime.api import dispatch, open_database, save_layer, save_object
from runtime.configuration.loader import ConfigError, DEFAULT_ROOT, Loader
from runtime.storage.database import SCHEMA_PATH
from runtime.validation.rules import fields
from tools.common.config_help import config_help, format_help
from tools.text.collect import collect_text


class OptionalHelpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-optional-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.configs = self.root / "configs"
        shutil.copytree(DEFAULT_ROOT, self.configs)
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.project = dispatch(self.c, {"action": "create", "kind": "project", "data": {}})["id"]

    def write(self, ref, text):
        path = self.configs / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def derive(self, name, parent, declarations=""):
        ref = f"objects/{name}.toml"
        self.write(ref, f'[object]\ntype="{name}"\nclass="optional_test_models:{name}"\nextends="{parent}.toml"\n{declarations}')
        return ref

    def layer(self, kind):
        result = save_layer(self.c, self.project, {"config_ref": f"layers/{kind}.toml"}, config_root=self.configs)
        self.assertTrue(result["ok"], result)
        return result["data"]["id"]

    def obj(self, ref, information, layer):
        result = save_object(self.c, self.project, {"config_ref": ref, "layer": layer, "information": information}, config_root=self.configs)
        self.assertTrue(result["ok"], result)
        return result

    def query(self, view, target, **kwargs):
        return config_help(view, target, config_root=self.configs, **kwargs)

    def test_derived_python_models_inherit_optional_without_logging_overrides(self):
        self.write("../optional_test_models.py", 'from models.objects.model import Model\nfrom models.objects.active import Active\nclass XModel(Model): pass\nclass XActive(Active): pass\n')
        sys.path.insert(0, str(self.root))
        self.addCleanup(sys.path.remove, str(self.root))
        self.addCleanup(sys.modules.pop, "optional_test_models", None)
        module = importlib.import_module("optional_test_models")
        (self.configs / "logging/diagnostics.toml").unlink()
        for name, parent in (("XModel", "model"), ("XActive", "active")):
            self.derive(name, parent)
            layer = self.layer(parent)
            obj = getattr(module, name)(layer=layer, information={"source": "resource"})
            with patch("runtime.validation.rules.fields.check", wraps=fields.check) as check:
                result = save_object(self.c, self.project, obj, config_root=self.configs)
            self.assertTrue(check.called)
            self.assertEqual(result["checks"], {"status": "completed", "issues": []})
            self.assertEqual(result["data"]["config_ref"], f"objects/{name}.toml")
            self.assertIsNotNone(obj.id)

    def test_present_optional_values_still_check_type_including_none(self):
        ref = self.derive("XModel", "model")
        layer = self.layer("model")
        for value in (None, "bad", 17):
            result = self.obj(ref, {"data": value}, layer)
            self.assertEqual([(i["code"], i["field"], i["severity"]) for i in result["checks"]["issues"]],
                             [("field_type", "information.data", "error")])
        self.assertEqual(self.obj(ref, {"data": {}, "source": ""}, layer)["checks"]["issues"], [])

    def test_optional_allows_absence_but_does_not_hide_typos(self):
        ref = self.derive("XModel", "model")
        result = self.obj(ref, {"src": "asset"}, self.layer("model"))
        self.assertEqual(len(result["checks"]["issues"]), 1)
        self.assertEqual(result["checks"]["issues"][0]["suggestions"], {"src": "source"})

    def test_logging_is_local_while_field_contracts_inherit(self):
        ref = self.derive("XModel", "model")
        layer = self.layer("model")
        self.write("logging/diagnostics.toml", '[levels]\nfield_type="error"\n[overrides."objects/model.toml"]\nfield_type="none"\n')
        self.assertEqual(self.obj("objects/model.toml", {"data": "bad"}, layer)["checks"]["issues"], [])
        result = self.obj(ref, {"data": "bad"}, layer)
        self.assertEqual(result["checks"]["issues"][0]["severity"], "error")
        self.assertEqual(self.obj(ref, {}, layer)["checks"]["issues"], [])
        self.write("logging/diagnostics.toml", '[overrides."objects/model.toml"]\nfield_type="none"\n')
        self.assertEqual(self.obj(ref, {"data": "bad"}, layer)["checks"]["issues"][0]["severity"], "warn")

    def test_omitted_or_explicit_false_reports_missing_after_inheritance(self):
        layer = self.layer("text")
        for name, declaration in (("Omitted", ""), ("Explicit", '[object.information]\ntext={optional=false}\n')):
            ref = self.derive(name, "text", declaration)
            issues = self.obj(ref, {}, layer)["checks"]["issues"]
            self.assertEqual([(i["code"], i["severity"]) for i in issues], [("missing_field", "warn")])
        self.assertNotIn("optional", Loader(self.configs).load("objects/text.toml", "object")["information"]["text"])

    def test_explicit_optional_is_a_fixed_boolean_contract(self):
        bad = self.derive("Bad", "model", '[object.information]\ndata={optional=false}\n')
        with self.assertRaisesRegex(ConfigError, "改写父约定"):
            Loader(self.configs).load(bad, "object")
        self.derive("Explicit", "text", '[object.information]\ntext={optional=false}\n')
        bad = self.derive("BadChild", "Explicit", '[object.information]\ntext={optional=true}\n')
        with self.assertRaisesRegex(ConfigError, "改写父约定"):
            Loader(self.configs).load(bad, "object")
        for value in ('"true"', '1'):
            bad = self.derive("Invalid", "text", f'[object.information]\ntext={{optional={value}}}\n')
            with self.assertRaisesRegex(ConfigError, "应为 true 或 false"):
                Loader(self.configs).load(bad, "object")

    def test_collect_respects_optional_absence_and_still_reports_bad_values(self):
        ref = self.derive("OptionalText", "text", '[object.information]\ntext={optional=true}\n')
        self.derive("OptionalChild", "OptionalText")
        layer = self.layer("text")
        self.obj("objects/OptionalChild.toml", {}, layer)
        self.obj(ref, {"text": "正文"}, layer)
        result = collect_text(self.c, self.project, layer, config_root=self.configs)
        self.assertEqual((result["text"], result["skipped_count"], result["status"], result["issues"]), ("正文", 1, "completed", []))
        self.obj(ref, {"text": None}, layer)
        result = collect_text(self.c, self.project, layer, config_root=self.configs)
        self.assertEqual(result["status"], "partial")
        self.assertEqual([i["code"] for i in result["issues"]], ["field_type"])

    def test_usage_is_short_and_developer_retains_definitions_origins_and_source(self):
        result = self.query("combined", "text")
        self.assertEqual(result["audience"], "usage")
        self.assertNotIn("definition", result["items"][0])
        self.assertNotIn("source", result["items"][0])
        self.assertIn("when", result["items"][0]["summary"])
        self.assertIn("text", result["object_details"][1]["usage"]["information"])
        rendered = format_help(result)
        self.assertNotIn("类型错误=", rendered)
        self.assertEqual(rendered.count("公共保存接口"), 1)
        self.assertLess(len(rendered.encode("utf-8")), 5800)  # 旧联查为 8282 字节。
        self.derive("XModel", "model")
        dev = self.query("objects", ["XModel", "text"], audience="developer")
        model, text = dev["items"]
        self.assertTrue(model["definition"]["information"]["data"]["optional"])
        self.assertEqual(model["field_origins"]["information"]["data"]["optional"], "objects/model.toml")
        self.assertEqual(text["field_origins"]["information"]["text"]["optional"], "default: false")
        self.assertIn("source", model)
        self.assertIn("layer", model["definition"]["fields"])
        self.assertNotIn("config_ref", model["definition"]["example"])
        self.assertNotIn("source", self.query("objects", "XModel", audience="developer", include_source=False)["items"][0])

    def test_new_content_and_purpose_appear_in_both_help_audiences(self):
        self.derive("Dialogue", "text", '''when="带说话人的对白"
not_for="音频文件"
[object.information]
speaker={type="str",optional=true,note="说话人"}
[object.example]
information={text="你好",speaker="A"}
''')
        for audience in ("usage", "developer"):
            result = self.query("objects", "Dialogue", audience=audience)
            rendered = format_help(result)
            self.assertIn("带说话人的对白", rendered)
            self.assertIn("音频文件", rendered)
            self.assertIn("speaker", rendered)
            self.assertIn("text", rendered)
            self.assertIn("objects/Dialogue.toml", result["items"][0]["save_example"]["code"])

    def test_both_help_save_examples_execute_with_real_context(self):
        self.derive("XModel", "model")
        for audience in ("usage", "developer"):
            for kind in ("base", "text", "image", "audio", "movie", "model", "active"):
                item = self.query("layers", f"layers/{kind}.toml", audience=audience)["items"][0]
                scope = {"connection": self.c, "project_id": self.project}
                exec(item["save_example"]["code"], scope)
                self.assertTrue(scope["result"]["ok"], scope["result"])
                self.assertEqual(scope["result"]["checks"]["issues"], [])
                scope["layer_id"] = scope["result"]["data"]["id"]
                refs = [f"objects/{kind}.toml"] + (["objects/title.toml"] if kind == "text" else ["objects/XModel.toml"] if kind == "model" else [])
                for ref in refs:
                    example = self.query("objects", ref, audience=audience)["items"][0]["save_example"]
                    self.assertEqual(example["status"], "available")
                    exec(example["code"], scope)
                    result = scope["result"]
                    self.assertTrue(result["ok"], result)
                    self.assertEqual(result["checks"]["issues"], [])
                    self.assertEqual(result["data"]["config_ref"], ref)
                    self.assertEqual(result["data"]["layer"], scope["layer_id"])

    def test_example_does_not_reuse_ids_and_explains_composite_context(self):
        self.derive("ExampleText", "text", '[object.example]\nid=99\nlayer=99\ninformation={text="hello"}\nbind=[{target_kind="object",target_id=99,target_project_id=99}]\n')
        example = self.query("objects", "ExampleText")["items"][0]["save_example"]
        self.assertNotIn("99", example["code"])
        self.assertEqual(set(example["required_context"]), {"connection", "project_id", "layer_id", "bind"})
        scope = {"connection": self.c, "project_id": self.project, "layer_id": self.layer("text"), "bind": []}
        exec(example["code"], scope)
        self.assertTrue(scope["result"]["ok"])

    def test_unusable_author_example_is_not_presented_as_a_save_request(self):
        for declaration in ('[object.example]\nunknown=4\n', '[object.example]\ninformation={time=2026-10-09}\n'):
            self.derive("BadExample", "text", declaration)
            item = self.query("objects", "BadExample")["items"][0]
            self.assertEqual(item["status"], "loaded")
            self.assertEqual(item["save_example"]["status"], "unavailable")
            self.assertNotIn("code", item["save_example"])

    def test_usage_shows_only_local_reporting_exceptions(self):
        self.derive("XModel", "model")
        self.write("logging/diagnostics.toml", '[levels]\nfield_type="error"\n[overrides."objects/model.toml"]\nfield_type="warn"\n')
        parent, child = self.query("objects", ["model", "XModel"])["items"]
        self.assertTrue(parent["reporting_exceptions"])
        self.assertNotIn("reporting_exceptions", child)
        with self.assertRaisesRegex(ValueError, "未知 help 用途"):
            self.query("objects", "model", audience="other")

    def test_cli_developer_mode_and_usage_raw_are_distinct(self):
        command = [sys.executable, "-X", "utf8", "-B", "-m", "tools.common.config_help", "objects", "model", "--json", "--config-root", str(self.configs)]
        for flags, audience in ((["--dev"], "developer"), (["--raw"], "usage")):
            run = subprocess.run([*command, *flags], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertEqual(result["audience"], audience)
            self.assertIn("source", result["items"][0])


if __name__ == "__main__":
    unittest.main()

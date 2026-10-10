"""配置 help 的动态发现、四种范围、继承说明和无数据库运行。"""

from collections import Counter
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from layerweave.support.api import diagnostic_report
from layerweave.tool.builtin.shared.help.catalog import read_support
from layerweave.support.configuration.loader import DEFAULT_ROOT, Loader
from layerweave.tool.builtin.shared.help.config_help import config_help, format_help


class ConfigHelpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-help-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.configs = self.root / "configs"
        shutil.copytree(DEFAULT_ROOT, self.configs)
        # 技能声明相关的用例以"文字层未声明 tools"为基线；仓库自带的 text.toml 已绑定技能，这里在副本中清空。
        text = self.configs / "layers/text.toml"
        text.write_text(re.sub(r"tools = \[[^\]]*\]", "tools = []", text.read_text(encoding="utf-8"), count=1), encoding="utf-8")

    def query(self, view="overview", targets=None, **kwargs):
        kwargs.setdefault("audience", "developer")
        return config_help(view, targets, config_root=self.configs, **kwargs)

    def write(self, ref, source):
        path = self.configs / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    def test_overview_lists_layers_and_compatible_class_summaries(self):
        result = self.query()
        self.assertEqual(result["status"], "completed")
        self.assertEqual({item["config_ref"] for item in result["items"]},
                         {path.relative_to(self.configs).as_posix() for path in (self.configs / "layers").rglob("*.toml")})
        text = next(item for item in result["items"] if item["summary"]["type"] == "text")
        self.assertEqual({item["type"] for item in text["accepted_objects"]}, {"text", "title", "note"})   # note：视图工具登记的批注对象，继承文字对象
        self.assertTrue(all("definition" not in item for item in result["items"]))
        self.assertTrue(all("information" not in item for item in text["accepted_objects"]))
        self.assertNotIn("logging/diagnostics.toml", [item["config_ref"] for item in result["items"]])

    def test_skill_routes_are_visible_without_reading_or_resolving_them(self):
        external = self.root / "external-skill.md"
        external.write_text("外部技能内容不属于配置 help 的读取范围", encoding="utf-8")
        routes = [
            {"route": external.as_posix(), "tier": "层级", "when": "整理文字格式时"},
            {"route": "skill:missing-scene-skill", "tier": "自定义场景", "when": "已有歌词和时间标记时"},
        ]
        declaration = "tools = [\n" + ",\n".join(
            "  { " + ", ".join(f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in item.items()) + " }"
            for item in routes) + "\n]"
        path = self.configs / "layers/text.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("tools = []", declaration, 1), encoding="utf-8")
        original_open = Path.open

        def config_only(path, *args, **kwargs):
            if path == external:
                raise AssertionError("help must not read routed skills")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", config_only):
            for audience in ("usage", "developer"):
                for view in ("overview", "layers", "combined"):
                    with self.subTest(audience=audience, view=view):
                        result = self.query(view, None if view == "overview" else "text", audience=audience, include_source=False)
                        self.assertEqual(result["status"], "completed")
                        self.assertEqual(result["issues"], [])
                        item = next(item for item in result["items"] if item["config_ref"] == "layers/text.toml")
                        self.assertEqual(item.get("definition", item.get("summary"))["tools"], routes)
                        rendered = format_help(result)
                        for route in routes:
                            self.assertEqual(rendered.count("route: " + route["route"]), 1)
                            self.assertIn("tier: " + route["tier"], rendered)
                            self.assertIn("when: " + route["when"], rendered)

    def test_skill_declarations_are_display_data_not_validation_rules(self):
        path = self.configs / "layers/text.toml"
        source = path.read_text(encoding="utf-8")
        for value in ('[{ route = "skill:only-a-reference" }, "free note"]', '"free-form declaration"'):
            path.write_text(source.replace("tools = []", "tools = " + value, 1), encoding="utf-8")
            for audience in ("usage", "developer"):
                result = self.query("layers", "text", audience=audience, include_source=False)
                self.assertEqual(result["issues"], [])
                self.assertEqual(result["status"], "completed")
                self.assertIn("外置技能", format_help(result))
        path.write_text(source, encoding="utf-8")
        self.assertIn("（未声明）", format_help(self.query("layers", "text", audience="usage")))

    def test_layer_details_use_merged_definition_and_only_class_summaries(self):
        result = self.query("layers", ["TextLayer", "image"])
        self.assertEqual(len(result["items"]), 2)
        text = result["items"][0]
        self.assertEqual(text["lineage"], ["layers/base.toml", "layers/text.toml"])
        self.assertIn("father", text["definition"]["fields"])
        self.assertTrue(text["definition"]["constraint"]["overlap"])
        self.assertTrue(text["fixed_contracts"]["constraint"]["overlap"])
        self.assertEqual(text["definition"]["methods"]["return_self"], Loader(self.configs).load("layers/base.toml", "layer")["methods"]["return_self"])
        self.assertNotIn("object_details", result)
        self.assertNotIn("_contracts", text["definition"])
        self.assertIn("层支持详情", format_help(result))

    def test_object_batch_resolves_paths_types_and_class_names_without_duplicates(self):
        result = self.query("objects", ["Text", "objects/text.toml", "text", "layerweave.models.objects.title:Title", "image"])
        self.assertEqual([item["config_ref"] for item in result["items"]], ["objects/text.toml", "objects/title.toml", "objects/image.toml"])
        title = result["items"][1]
        self.assertEqual(title["definition"]["class"], "layerweave.models.objects.title:Title")
        self.assertIn("text", title["definition"]["information"])
        self.assertIn("layer", title["definition"]["fields"])
        self.assertEqual(title["lineage"], ["objects/base.toml", "objects/text.toml", "objects/title.toml"])

    def test_combined_expands_shared_object_descriptions_once(self):
        result = self.query("combined", ["text", "Layer"])
        self.assertEqual(len(result["items"]), 2)
        refs = [item["config_ref"] for item in result["object_details"]]
        # 工具包登记的派生类型（requires 与层不同）只在支持列表里点名，不在别的层下展开详情
        expected = {obj["config_ref"] for layer in result["items"] for obj in layer["accepted_objects"]
                    if not obj.get("requires") or obj["requires"] == layer.get("summary", {}).get("requires")}
        self.assertEqual(set(refs), expected)
        self.assertIn("objects/note.toml", {obj["config_ref"] for obj in result["items"][0]["accepted_objects"]})
        self.assertNotIn("objects/note.toml", refs)
        self.assertIn("objects/note.toml", [item["config_ref"] for item in self.query("combined", "note")["object_details"]])
        self.assertEqual(len(refs), len(set(refs)))
        self.assertTrue(all("definition" in item for item in result["object_details"]))
        self.assertIn("共用的说明只展开一次", format_help(result))

    def test_new_nested_encapsulations_are_discovered_without_registration_or_import(self):
        module = self.root / "fresh_help_types.py"
        module.write_text('raise AssertionError("help must not import model modules")\n', encoding="utf-8")
        sys.path.insert(0, str(self.root))
        self.addCleanup(sys.path.remove, str(self.root))
        self.addCleanup(sys.modules.pop, "fresh_help_types", None)
        ref = "objects/dialogue/entry.toml"
        path = self.write(ref, '''[object]
type="dialogue"
name="对白对象"
class="fresh_help_types:Dialogue"
extends="../text.toml"
[object.information]
speaker={type="str",note="说话人",choices=["A","B"]}
[object.custom]
guide="用户添加的说明也应该显示"
published=2026-10-09
weight=inf
''')
        self.write("layers/dialogue/entry.toml", '''[layer]
type="dialogue"
name="对白层"
class="fresh_help_types:DialogueLayer"
extends="../text.toml"
objects="dialogue"
''')
        with patch("sqlite3.connect", side_effect=AssertionError("help must not connect to a database")):
            overview = self.query()
            detail = self.query("combined", ["dialogue"])
        self.assertNotIn("fresh_help_types", sys.modules)
        text = next(item for item in overview["items"] if item["config_ref"] == "layers/text.toml")
        self.assertIn(ref, [obj["config_ref"] for obj in text["accepted_objects"]])
        self.assertEqual([obj["config_ref"] for obj in detail["items"][0]["accepted_objects"]], [ref])
        obj = detail["object_details"][0]
        self.assertEqual(set(obj["definition"]["information"]), {"text", "speaker"})
        self.assertEqual(obj["definition"]["custom"]["published"], "2026-10-09")
        self.assertEqual(obj["definition"]["custom"]["weight"], "inf")
        self.assertIn("用户添加的说明也应该显示", format_help(detail))
        self.assertIn('"choices": ["A", "B"]', format_help(detail))
        json.dumps(detail, allow_nan=False)
        path.write_text(path.read_text(encoding="utf-8").replace("说话人", "新说明"), encoding="utf-8")
        self.assertEqual(self.query("objects", "dialogue")["items"][0]["definition"]["information"]["speaker"]["note"], "新说明")

    def test_raw_source_preserves_comments_and_inherited_fields_remain_separate(self):
        result = self.query("objects", ["title"], include_source=True)
        item = result["items"][0]
        self.assertEqual(item["source"], (self.configs / "objects/title.toml").read_text(encoding="utf-8"))
        self.assertIn("# 派生封装示例", item["source"])
        self.assertNotIn("[object.information]", item["source"])
        self.assertIn("text", item["definition"]["information"])
        self.assertIn("当前 TOML 原文", format_help(result))

    def test_reporting_matches_real_diagnostics_and_refreshes_between_calls(self):
        item = self.query("objects", "model")["items"][0]
        levels = item["reporting"]["information"]["data"]
        self.assertEqual(levels, {"missing_field": "warn", "field_type": "error"})
        self.assertTrue(item["definition"]["information"]["data"]["optional"])
        policy = self.configs / "logging/diagnostics.toml"
        policy.write_text('[levels]\nmissing_field="error"\nfield_type="warn"\n'
                          '[overrides."objects/model.toml".missing_field]\n"information.data"="warn"\n'
                          '[overrides."objects/model.toml".duration]\nend="none"\n', encoding="utf-8")
        item = self.query("objects", "model")["items"][0]
        expected = diagnostic_report([{"code": "missing_field", "config_ref": "objects/model.toml",
                                       "field": "information.data", "message": "缺少 data"}], config_root=self.configs)
        self.assertEqual(item["reporting"]["information"]["data"]["missing_field"], expected["issues"][0]["severity"])
        self.assertEqual(item["reporting"]["constraint"]["duration"]["fields"], {"end": "none"})
        policy.unlink()
        self.assertEqual(self.query("objects", "model")["items"][0]["reporting"]["information"]["data"]["field_type"], "warn")

    def test_bad_configuration_is_reported_while_valid_targets_continue(self):
        source = "# 保留用于修复的原文\n[object\n"
        self.write("objects/broken.toml", source)
        result = self.query("objects", ["objects/broken.toml", "Text"], include_source=True)
        self.assertEqual(result["status"], "partial")
        self.assertEqual([item["status"] for item in result["items"]], ["unavailable", "loaded"])
        self.assertEqual(result["items"][0]["source"], source)
        self.assertEqual(result["issues"][0]["target"]["id"], "objects/broken.toml")
        overview = self.query()
        self.assertTrue(any(i["config_ref"] == "layers/image.toml" and "summary" in i for i in overview["items"]))
        self.assertTrue(any(i["target"]["id"] == "objects/broken.toml" for i in overview["issues"]))
        self.assertTrue(any(not i.get("accepted_objects_complete", True) for i in overview["items"]))

    def test_missing_targets_and_wrong_categories_are_not_guessed(self):
        result = self.query("objects", ["absent", "objects/missing.toml", "layers/text.toml", "Title"])
        self.assertEqual([item["status"] for item in result["items"]], ["unavailable", "unavailable", "unavailable", "loaded"])
        self.assertEqual(result["status"], "partial")
        self.assertTrue(any(issue.get("candidates") for issue in result["issues"]))
        self.assertEqual(self.query("objects", [])["items"], [])
        with self.assertRaises(ValueError):
            self.query("unknown")
        with self.assertRaises(ValueError):
            self.query("layers")
        with self.assertRaises(ValueError):
            self.query("overview", ["text"])

    def test_ambiguous_types_require_an_explicit_configuration_reference(self):
        self.write("objects/other_text.toml", '[object]\ntype="text"\nclass="unknown_module:OtherText"\nextends="base.toml"\n')
        result = self.query("objects", ["text", "objects/text.toml", "OtherText"])
        self.assertEqual([item["status"] for item in result["items"]], ["unavailable", "loaded", "loaded"])
        self.assertEqual(set(result["issues"][0]["candidates"]), {"objects/text.toml", "objects/other_text.toml"})

    def test_help_never_overrides_parent_contracts(self):
        self.write("objects/bad.toml", '[object]\ntype="bad"\nclass="module_not_loaded:Bad"\nextends="text.toml"\n'
                   '[object.information]\ntext={type="int"}\n')
        result = self.query("objects", ["bad", "Text"])
        self.assertEqual(result["items"][0]["status"], "unavailable")
        self.assertEqual(result["items"][1]["status"], "loaded")
        self.assertIn("改写父约定", result["issues"][0]["message"])

    def test_each_file_is_read_once_even_for_combined_raw_batch(self):
        opened = Counter()
        original = Path.open
        def tracked(path, *args, **kwargs):
            if path.suffix == ".toml":
                opened[str(path)] += 1
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", tracked):
            result = self.query("combined", ["Layer", "TextLayer", "ImageLayer", "TextLayer"], include_source=True)
        self.assertEqual(result["status"], "completed")
        self.assertTrue(opened)
        self.assertTrue(all(count == 1 for count in opened.values()), opened)

    def test_non_utf8_source_does_not_abort_other_targets(self):
        (self.configs / "objects/non_utf8.toml").write_bytes(b'\xff\xfe\x00')
        result = self.query("objects", ["objects/non_utf8.toml", "Text"], include_source=True)
        self.assertEqual([item["status"] for item in result["items"]], ["unavailable", "loaded"])
        self.assertNotIn("source", result["items"][0])

    def test_cli_four_modes_json_raw_and_no_database_argument(self):
        command = [sys.executable, "-X", "utf8", "-B", "-m", "layerweave.tool.builtin.shared.help.config_help"]
        for args in ([], ["layers", "text", "image"], ["objects", "Text", "Title", "--raw"], ["combined", "text", "audio"]):
            result = subprocess.run([*command, *args, "--config-root", str(self.configs), "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "completed")
        partial = subprocess.run([*command, "objects", "absent", "text"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(partial.returncode, 0, partial.stderr)
        self.assertIn("[WARN] configuration", partial.stdout)
        self.assertIn("文字对象", partial.stdout)
        self.assertIn("项目中的实际层和对象请使用项目查询工具", partial.stdout)
        failed = subprocess.run([*command, "--config-root", str(self.root / "missing"), "--json"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(json.loads(failed.stdout)["status"], "failed")

    def test_api_and_help_do_not_import_encapsulation_modules(self):
        script = 'import sys\nfrom layerweave.tool.builtin.shared.help.catalog import read_support\nr=read_support("combined", ["text", "image"])\nassert r["status"]=="completed"\nassert not any(n.startswith("layerweave.models.") for n in sys.modules)\n'
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

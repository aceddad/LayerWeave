"""Language changes affect presentation only; optional plugin packs do not block loading."""
from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from layerweave.support.api import initialize_database, open_database, transaction
from layerweave.tool.builtin.view.at import read_spans
from layerweave.tool.builtin.view.i18n import translate, ViewError, error_payload
from layerweave.tool.builtin.view.plugins import plugin, list_plugins
from layerweave.tool.builtin.view.plugin_manifest import manifest
from layerweave.tool.builtin.view.screenshot import capture, link_query, page_params


class ViewLanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_message_preserves_detail_and_substitutes_once(self):
        error = ViewError("error.action", {"action": "x{action}$&"})
        self.assertEqual(str(error), "不认识的动作：x{action}$&")
        self.assertEqual(translate(error.ui["key"], error.ui["values"], lang="en"), "Unknown action: x{action}$&")
        self.assertEqual(error_payload(OSError("raw 原文"))["ui"]["detail"], "raw 原文")
        self.assertEqual(translate("missing.key", lang="unknown"), "missing.key")
        serialized=json.dumps(error_payload(ViewError("pluginError.fetch", {"value1": Path("x"), "value2": OSError("raw")})))
        self.assertIn("raw", serialized)

    def test_optional_plugin_resources_and_canonical_metadata(self):
        folder = self.root / "plugin"; folder.mkdir()
        (folder / "plugin.js").write_text("export default () => ({label:'原始'});", encoding="utf-8")
        (folder / "README.md").write_text("原始说明", encoding="utf-8")
        (folder / "README.en.md").write_text("English usage", encoding="utf-8")
        meta = {"format":1,"kind":"view-plugin","publisher":"alice","name":"demo","version":"1.0.0",
                "label":"原始", "description":"说明", "requires":{"view":">=0.29.0","host_api":[3]},
                "locales":{"en":"en.json", "zh":"missing.json"}}
        (folder / "plugin.json").write_text(json.dumps(meta),encoding="utf-8")
        (folder / "en.json").write_text(json.dumps({"messages":{"hello":"Hello"},"display":{"label":"Localized"},"usage":"README.en.md"}),encoding="utf-8")
        state = self.root / "state"
        plugin("add", str(folder), root=state)
        plain = list_plugins(state)["plugins"][0]
        self.assertNotIn("localizations", plain)
        shown = list_plugins(state,languages=True)["plugins"][0]
        self.assertIsNone(shown["problem"])
        self.assertEqual(shown["label"],"原始")
        self.assertEqual(shown["localizations"]["en"]["display"]["label"],"Localized")
        self.assertEqual(len(shown["language_warnings"]),1)
        info = plugin("info", "alice.demo", root=state)
        self.assertEqual(info["manifest"]["label"],"原始")
        self.assertEqual(info["localizations"]["en"]["usage_text"],"English usage")
        (folder / "en.json").write_text("{broken",encoding="utf-8")
        shown = list_plugins(state,languages=True)["plugins"][0]
        self.assertIsNone(shown["problem"])
        self.assertEqual(shown["localizations"],{})
        self.assertEqual(len(shown["language_warnings"]),2)
        with self.assertRaises(ValueError): manifest({**meta,"locales":{"en":"../escape.json"}})

    def test_copy_is_localized_but_user_data_and_database_are_unchanged(self):
        database=initialize_database(self.root / "test.sqlite3")
        with closing(open_database(database)) as c:
            with transaction(c) as w:
                project=w.create("project",{"name":"中文项目"})["id"]
                layer=w.create("layer",{"type":"text","config_ref":"layers/text.toml","name":"中文层","axis":{"unit":"拍"}},project_id=project)["id"]
                w.create("object",{"config_ref":"objects/text.toml","layer":layer,"begin":0,"end":1,"information":{"text":"用户正文 {name}"}},project_id=project)
            before=list(c.iterdump())
            zh=read_spans(c,project,[(layer,0,0)])
            en=read_spans(c,project,[(layer,0,0)],lang="en")
            self.assertIn("根层",zh["text"]);self.assertIn("Root #",en["text"])
            self.assertIn("用户正文 {name}",en["text"]);self.assertIn("中文层",en["text"])
            self.assertNotIn("层「",en["text"])
            ended=read_spans(c,project,[(layer,2,2)],lang="en")
            self.assertIn("Ended: last object ends at 1 拍",ended["text"])
            self.assertEqual(before,list(c.iterdump()))

    def test_capture_language_is_reserved_and_validated_before_browser(self):
        self.assertEqual(link_query("http://localhost/?project=1&lang=en",1)["lang"],"en")
        with self.assertRaises(ValueError): page_params(["lang=en"])
        with patch("layerweave.tool.builtin.view.screenshot.find_browser") as browser:
            with self.assertRaisesRegex(ValueError,"lang"):
                capture("unused",1,self.root / "no.png",lang="bad")
            browser.assert_not_called()


if __name__ == "__main__": unittest.main()

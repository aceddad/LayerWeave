"""配置继承、可调项与固定约定；所有临时配置在独立临时目录。"""

from pathlib import Path
import shutil
import tempfile
import unittest

from support.configuration.loader import ConfigError, DEFAULT_ROOT, Loader


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-production-config-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "configs"
        shutil.copytree(DEFAULT_ROOT, self.root)

    def write(self, ref, text):
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_all_builtin_configs_load_with_defaults_and_ancestry(self):
        loader = Loader(self.root)
        for path in [*self.root.glob("layers/*.toml"), *self.root.glob("objects/*.toml")]:
            kind = "layer" if path.parent.name == "layers" else "object"
            config = loader.load(loader.ref(path), kind)
            self.assertTrue(config["display"]["visibility"])
            self.assertIn(f"{kind}s/base.toml", config["_lineage"])
        self.assertEqual(len(loader.cache), 15)

    def test_derived_field_addition_repeats_rule_once(self):
        self.write("objects/dialogue.toml", '''[object]
type="dialogue"
class="fixture_types:DialogueObject"
extends="text.toml"
[object.information]
speaker={type="str"}
[object.rules]
begin_le_end=true
''')
        result = Loader(self.root).load("objects/dialogue.toml", "object")
        self.assertEqual(set(result["information"]), {"text", "speaker"})
        self.assertEqual(list(result["rules"]), ["begin_le_end"])
        self.assertEqual(result["_lineage"], ["objects/base.toml", "objects/text.toml", "objects/dialogue.toml"])

    def test_parent_field_and_rule_cannot_be_rewritten(self):
        for suffix in ('[object.information]\ntext={type="int"}', '[object.rules]\nbegin_le_end=false'):
            self.write("objects/bad.toml", '[object]\ntype="bad"\nclass="fixture_types:BadObject"\nextends="text.toml"\n' + suffix)
            with self.assertRaises(ConfigError):
                Loader(self.root).load("objects/bad.toml", "object")

    def test_defaults_can_be_chosen_but_explicit_parent_contract_is_fixed(self):
        self.write("layers/track.toml", '[layer]\ntype="track"\nclass="fixture_types:TrackLayer"\nextends="base.toml"\n[layer.constraint]\noverlap=false\n[layer.display]\nvisibility=false\n')
        self.write("layers/child.toml", '[layer]\ntype="child"\nclass="fixture_types:ChildLayer"\nextends="track.toml"\n[layer.constraint]\noverlap=true\n')
        loader = Loader(self.root)
        track = loader.load("layers/track.toml", "layer")
        self.assertFalse(track["constraint"]["overlap"])
        self.assertFalse(track["display"]["visibility"])
        with self.assertRaises(ConfigError):
            loader.load("layers/child.toml", "layer")

    def test_axis_option_can_change_without_rewriting_fixed_rules(self):
        self.write("layers/local.toml", '[layer]\ntype="local"\nclass="fixture_types:LocalLayer"\nextends="text.toml"\n[layer.options]\naxis_only_on_root=false\n')
        config = Loader(self.root).load("layers/local.toml", "layer")
        self.assertFalse(config["options"]["axis_only_on_root"])
        self.assertTrue(config["rules"]["no_cycle"])
        self.assertNotIn("root_has_axis", config["rules"])

    def test_cycle_missing_and_malformed_configs_are_individual_errors(self):
        self.write("objects/a.toml", '[object]\ntype="a"\nclass="fixture_types:AObject"\nextends="b.toml"\n')
        self.write("objects/b.toml", '[object]\ntype="b"\nclass="fixture_types:BObject"\nextends="a.toml"\n')
        self.write("objects/bad.toml", '[object]\ntype="bad"\nclass="fixture_types:BadObject"\nfields=123\n')
        loader = Loader(self.root)
        for ref in ("objects/a.toml", "objects/missing.toml", "objects/bad.toml"):
            with self.subTest(ref=ref), self.assertRaises(ConfigError):
                loader.load(ref, "object")
        self.assertEqual(loader.load("objects/text.toml", "object")["type"], "text")

    def test_object_reference_ambiguity_and_layer_narrowing(self):
        self.write("objects/extra/text.toml", '[object]\ntype="text"\nclass="fixture_types:TextObject"\nextends="../base.toml"\n')
        with self.assertRaisesRegex(ConfigError, "唯一定位"):
            Loader(self.root).object_config("text")
        (self.root / "objects/extra/text.toml").unlink()
        self.write("layers/bad.toml", '[layer]\ntype="bad"\nclass="fixture_types:BadLayer"\nextends="text.toml"\nobjects="image"\n')
        with self.assertRaises(ConfigError):
            Loader(self.root).load("layers/bad.toml", "layer")

    def test_each_new_loader_observes_edited_config(self):
        first = Loader(self.root).load("objects/text.toml", "object")
        path = self.root / "objects/text.toml"
        path.write_text(path.read_text(encoding="utf-8") + '\n[object.rules]\ncustom=true\n', encoding="utf-8")
        second = Loader(self.root).load("objects/text.toml", "object")
        self.assertNotIn("custom", first["rules"])
        self.assertTrue(second["rules"]["custom"])

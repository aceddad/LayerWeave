"""使用查询/文件读取次数约束重复工作，不依赖机器速度。"""

from collections import Counter
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from layerweave.models import Text, TextLayer
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.support.api import open_database, read_layer
from layerweave.tool.builtin.usage.records.save import save_layer, save_object
from layerweave.support.configuration.loader import DEFAULT_ROOT
from layerweave.support.storage.database import SCHEMA_PATH


class IOEfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.project_id = dispatch(self.connection, {"action": "create", "kind": "project", "data": {}}, checker=None)["id"]

    def layer(self, project_id=None):
        layer = TextLayer()
        result = save_layer(self.connection, project_id or self.project_id, layer, checker=None)
        self.assertTrue(result["ok"], result)
        return layer

    def test_config_reads_do_not_grow_per_new_instance(self):
        counts = []
        for count in (1, 100):
            layer = self.layer()
            layer.objects = [Text(layer=layer.id, information={"text": str(i)}) for i in range(count)]
            opened = Counter()
            original = Path.open

            def tracked(path, *args, **kwargs):
                if path.suffix == ".toml":
                    opened[str(path)] += 1
                return original(path, *args, **kwargs)

            with patch.object(Path, "open", tracked):
                result = save_layer(self.connection, self.project_id, layer)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["checks"]["issues"], [])
            counts.append(sum(opened.values()))
        self.assertEqual(counts[0], counts[1])

    def test_configuration_index_is_local_to_each_save(self):
        with tempfile.TemporaryDirectory(prefix="layerweave-config-index-") as directory:
            configs = Path(directory) / "configs"
            shutil.copytree(DEFAULT_ROOT, configs)
            layer = self.layer()
            first = save_object(self.connection, self.project_id, Text(layer=layer.id), config_root=configs)
            self.assertTrue(first["ok"], first)
            (configs / "objects/other.toml").write_text(
                '[object]\ntype="other"\nextends="text.toml"\nclass="layerweave.models.objects.text:Text"\n', encoding="utf-8")
            second = save_object(self.connection, self.project_id, Text(layer=layer.id), config_root=configs)
            self.assertFalse(second["ok"])
            self.assertIn("只绑定一份配置", second["error"]["message"])
            explicit = save_object(self.connection, self.project_id,
                                   {"layer": layer.id, "config_ref": "objects/other.toml"}, config_root=configs)
            self.assertFalse(explicit["ok"], explicit)

    def test_unchanged_layer_issues_no_update_or_log(self):
        layer = self.layer()
        layer.objects = [Text(layer=layer.id, begin=i, end=i+1, information={"text": str(i)}) for i in range(100)]
        layer.objects[0].bind = [{"target_kind": "layer", "target_project_id": self.project_id, "target_id": layer.id}]
        self.assertTrue(save_layer(self.connection, self.project_id, layer)["ok"])
        statements = []
        self.connection.set_trace_callback(statements.append)
        try:
            result = save_layer(self.connection, self.project_id, layer)
        finally:
            self.connection.set_trace_callback(None)
        self.assertFalse(result["applied"])
        self.assertEqual(result["checks"]["reason"], "no_changes")
        self.assertFalse(any(sql.startswith(("UPDATE", "INSERT", "DELETE")) for sql in statements))

    def test_full_layer_uses_bounded_queries_and_preserves_binding_scope(self):
        layer = self.layer()
        layer.objects = [Text(layer=layer.id, begin=i, end=i+1) for i in range(100)]
        self.assertTrue(save_layer(self.connection, self.project_id, layer, checker=None)["ok"])
        other_project = dispatch(self.connection, {"action": "create", "kind": "project", "data": {}}, checker=None)["id"]
        other_layer = self.layer(other_project)
        foreign = Text(layer=other_layer.id)
        save_object(self.connection, other_project, foreign, checker=None)
        self.assertEqual(foreign.id, layer.objects[0].id)
        cases = [
            ("object", self.project_id, layer.objects[0].id, "outgoing first"),
            ("object", self.project_id, layer.objects[0].id, "outgoing second"),
            ("layer", self.project_id, layer.id, "layer binding"),
            ("object", other_project, foreign.id, "incoming from another project"),
            ("layer", self.project_id, layer.objects[0].id, "wrong source kind"),
        ]
        for kind, project_id, id, tips in cases:
            result = dispatch(self.connection, {"action": "create", "kind": "bind", "data": {
                "source_kind": kind, "source_project_id": project_id, "source_id": id,
                "target_kind": "object", "target_project_id": self.project_id, "target_id": layer.objects[0].id,
                "tips": tips,
            }}, checker=None)
            self.assertTrue(result["ok"], result)
        statements = []
        self.connection.set_trace_callback(statements.append)
        try:
            result = read_layer(self.connection, self.project_id, layer.id)
        finally:
            self.connection.set_trace_callback(None)
        selects = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
        self.assertLessEqual(len(selects), 4)
        self.assertEqual([row["tips"] for row in result["bind"]], ["layer binding"])
        self.assertEqual([row["tips"] for row in result["objects"][0]["bind"]], ["outgoing first", "outgoing second"])
        self.assertTrue(all(obj["bind"] == [] for obj in result["objects"][1:]))
        self.assertEqual([obj["begin"] for obj in result["objects"]], list(range(100)))

"""项目概览保持轻量、只读，并完整保留不能排入根层树的记录。"""

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from runtime.api import dispatch, open_database
from runtime.storage import crud
from runtime.storage.database import SCHEMA_PATH
from tools.usage.common.project_overview import format_overview, project_overview


class ProjectOverviewTests(unittest.TestCase):
    def setUp(self):
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.project_id = self.request("create", "project", data={"name": "项目", "tips": "说明"})["id"]

    def request(self, action, kind, **args):
        result = dispatch(self.connection, {"action": action, "kind": kind, **args}, checker=None)
        self.assertTrue(result["ok"], result)
        return result

    def layer(self, name, *, father=None, project_id=None, type="text"):
        return self.request("create", "layer", project_id=project_id or self.project_id, data={
            "name": name, "type": type, "config_ref": "layers/need-not-exist.toml", "father": father,
        })["id"]

    def obj(self, layer_id, *, project_id=None):
        return self.request("create", "object", project_id=project_id or self.project_id, data={
            "layer": layer_id, "config_ref": "objects/need-not-exist.toml", "information": {"text": "正文"},
        })["id"]

    def test_order_depth_counts_and_project_isolation(self):
        root = self.layer("主线")
        second = self.layer("参考", type="image")
        child = self.layer("配音", father=root, type="audio")
        leaf = self.layer("叶子", father=child)
        self.obj(root)
        self.obj(child)
        self.obj(child)
        other = self.request("create", "project", data={})["id"]
        other_layer = self.layer("其他项目", project_id=other)
        self.obj(other_layer, project_id=other)
        result = project_overview(self.connection, self.project_id)
        self.assertEqual(result["project"]["tips"], "说明")
        self.assertEqual(result["counts"], {"layers": 4, "objects": 3, "roots": 2, "unplaced_layers": 0})
        self.assertEqual([row["id"] for row in result["layers"]], [root, child, leaf, second])
        self.assertEqual([row["depth"] for row in result["layers"]], [0, 1, 2, 0])
        self.assertEqual([row["object_count"] for row in result["layers"]], [1, 2, 0, 0])
        self.assertTrue(all(row["project_id"] == self.project_id for row in result["layers"]))
        self.assertIn("4 个层 · 3 个对象", format_overview(result))
        self.assertNotIn("其他项目", format_overview(result))

    def test_empty_and_missing_projects(self):
        empty = project_overview(self.connection, self.project_id)
        self.assertEqual(empty["layers"], [])
        self.assertEqual(empty["counts"], {"layers": 0, "objects": 0, "roots": 0, "unplaced_layers": 0})
        self.assertIsNone(project_overview(self.connection, 999))
        self.assertEqual(format_overview(None), "项目不存在。")

    def test_read_only_and_no_content_or_configuration_loading(self):
        layer_id = self.layer("摘要")
        self.obj(layer_id)
        # 摘要不需要解码正文；即使外部 SQL 写入了损坏正文也应能看清项目结构。
        with self.connection:
            self.connection.execute("UPDATE objects SET information='invalid JSON'")
        before_changes = self.connection.total_changes
        before_logs = len(crud.read(self.connection, "change"))
        statements = []
        self.connection.set_trace_callback(statements.append)
        try:
            with patch.object(Path, "open", side_effect=AssertionError("overview must not open configs")):
                result = project_overview(self.connection, self.project_id)
        finally:
            self.connection.set_trace_callback(None)
        self.assertEqual(result["counts"]["objects"], 1)
        self.assertEqual(self.connection.total_changes, before_changes)
        self.assertEqual(len(crud.read(self.connection, "change")), before_logs)
        self.assertFalse(self.connection.in_transaction)
        selects = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
        self.assertEqual(len(selects), 2)
        self.assertFalse(any("information" in sql.lower() or "axis" in sql.lower() for sql in selects))

    def test_existing_transaction_is_not_committed(self):
        self.connection.execute("UPDATE projects SET name='未提交' WHERE id=?", (self.project_id,))
        result = project_overview(self.connection, self.project_id)
        self.assertEqual(result["project"]["name"], "未提交")
        self.assertTrue(self.connection.in_transaction)
        self.connection.rollback()
        self.assertEqual(project_overview(self.connection, self.project_id)["project"]["name"], "项目")

    def test_cycle_is_kept_without_infinite_traversal_or_fake_roots(self):
        root = self.layer("正常根")
        first = self.layer("A")
        second = self.layer("B", father=first)
        child = self.layer("C", father=second)
        self.request("update", "layer", project_id=self.project_id, id=first, data={"father": second})
        result = project_overview(self.connection, self.project_id)
        self.assertEqual(result["counts"]["roots"], 1)
        self.assertEqual(result["counts"]["unplaced_layers"], 3)
        self.assertEqual([row["id"] for row in result["layers"]], [root, first, second, child])
        self.assertEqual([row["depth"] for row in result["layers"]], [0, None, None, None])
        self.assertEqual(result["layers"][1]["father"], second)
        self.assertIn("未归入根层", format_overview(result))
        json.dumps(result, ensure_ascii=False)

    def test_deep_hierarchy_is_iterative_and_json_serializable(self):
        depth = 1100
        with self.connection:
            self.connection.executemany(
                "INSERT INTO layers(project_id,id,name,type,config_ref,father) VALUES (?,?,?,?,?,?)",
                [(self.project_id, i, str(i), "text", "layers/text.toml", i-1 if i>1 else None)
                 for i in range(1, depth+1)],
            )
            self.connection.execute("UPDATE projects SET max_id=? WHERE id=?", (depth, self.project_id))
        result = project_overview(self.connection, self.project_id)
        self.assertEqual(result["counts"]["layers"], depth)
        self.assertEqual(result["layers"][-1]["depth"], depth-1)
        json.dumps(result)

    def test_cli_json_and_missing_database(self):
        self.layer("命令行层")
        with tempfile.TemporaryDirectory(prefix="layerweave-overview-") as directory:
            database = Path(directory) / "project.sqlite3"
            copy = sqlite3.connect(database)
            try:
                self.connection.backup(copy)
            finally:
                copy.close()
            command = [sys.executable, "-X", "utf8", "-B", "-m", "tools.usage.common.project_overview"]
            result = subprocess.run([*command, str(database), str(self.project_id), "--json"],
                                    capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["layers"][0]["name"], "命令行层")
            result = subprocess.run([*command, str(database), "999", "--json"],
                                    capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 1)
            self.assertIsNone(json.loads(result.stdout))
            missing = Path(directory) / "missing.sqlite3"
            result = subprocess.run([*command, str(missing), "1"], capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(missing.exists())

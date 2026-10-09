"""详细展开的四种范围、原值时间筛选、父路径、完整引用及深层结构。"""

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from runtime.api import dispatch, open_database, read_record
from runtime.storage.database import SCHEMA_PATH
from tools.common.project_details import format_details, project_details


class ProjectDetailsTests(unittest.TestCase):
    def setUp(self):
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.project_id = self.create("project", {"name": "详细示例"})

    def create(self, kind, data, *, project_id=None):
        result = dispatch(self.connection, {"action": "create", "kind": kind, "data": data,
                                           **({"project_id": project_id} if project_id is not None else {})}, checker=None)
        self.assertTrue(result["ok"], result)
        return result["id"]

    def layer(self, *, father=None, project_id=None, **data):
        return self.create("layer", {"type": "text", "name": "层", "config_ref": "layers/missing.toml", "father": father, **data},
                           project_id=project_id or self.project_id)

    def obj(self, layer, begin, end, **data):
        return self.create("object", {"layer": layer, "begin": begin, "end": end, "config_ref": "objects/missing.toml",
                                       "name": "对象", "information": {"text": "完整正文", "extra": [1, True, None]}, **data},
                           project_id=self.project_id)

    def fixture(self):
        root = self.layer(axis={"unit": "秒", "precision": 0.001})
        child = self.layer(father=root)
        leaf = self.layer(father=child)
        other = self.layer(axis={"unit": "帧", "precision": 1, "fps": 30})
        empty = self.layer()
        objects = [self.obj(root, 0, 3), self.obj(child, 3, 5), self.obj(leaf, 4, 4), self.obj(other, 1, 7)]
        return (root, child, leaf, other, empty), objects

    def test_whole_project_and_selected_subtree_include_objects_and_empty_layers(self):
        (root, child, leaf, other, empty), objects = self.fixture()
        result = project_details(self.connection, self.project_id)
        self.assertEqual(result["counts"], {"layers": 5, "objects": 4, "unplaced_layers": 0})
        self.assertEqual([layer["id"] for layer in result["layers"]], [root, child, leaf, other, empty])
        selected = project_details(self.connection, self.project_id, layer_id=child)
        self.assertEqual([layer["id"] for layer in selected["layers"]], [child, leaf])
        self.assertEqual([layer["depth"] for layer in selected["layers"]], [0, 1])
        self.assertEqual(selected["layers"][0]["father"], root)
        self.assertEqual(selected["layers"][0]["objects"][0]["information"], {"text": "完整正文", "extra": [1, True, None]})

    def test_subtree_time_filter_keeps_only_hits_and_parent_paths(self):
        (root, child, leaf, other, empty), objects = self.fixture()
        result = project_details(self.connection, self.project_id, layer_id=root, begin=3, end=4)
        self.assertEqual([layer["id"] for layer in result["layers"]], [root, child])
        self.assertEqual(result["layers"][0]["objects"], [])
        self.assertEqual(result["layers"][1]["objects"][0]["id"], objects[1])
        self.assertEqual(result["layers"][1]["objects"][0]["end"], 5)
        point = project_details(self.connection, self.project_id, layer_id=root, begin=4, end=4)
        self.assertEqual(point["counts"]["objects"], 2)
        self.assertEqual([layer["id"] for layer in point["layers"]], [root, child, leaf])

    def test_time_filter_without_layer_searches_all_roots_numerically(self):
        (root, child, leaf, other, empty), objects = self.fixture()
        result = project_details(self.connection, self.project_id, begin=1, end=2)
        self.assertEqual([layer["id"] for layer in result["layers"]], [root, other])
        self.assertEqual([layer["objects"][0]["id"] for layer in result["layers"]], [objects[0], objects[3]])
        self.assertEqual(result["layers"][1]["axis"]["unit"], "帧")

    def test_query_does_not_snap_positions_or_bounds(self):
        layer = self.layer(axis={"precision": 1})
        obj = self.obj(layer, 0.49, 0.51)
        # 模拟旧记录，验证读取不会因新写入规则而暗中重写或量化查询边界。
        self.connection.execute('UPDATE objects SET "begin"=?, "end"=? WHERE project_id=? AND id=?',
                                (0.49, 0.51, self.project_id, obj))
        self.connection.commit()
        self.assertEqual(project_details(self.connection, self.project_id, begin=0, end=0)["layers"], [])
        result = project_details(self.connection, self.project_id, begin=0.5, end=0.5)
        self.assertEqual(result["layers"][0]["objects"][0]["id"], obj)
        self.assertEqual(result["layers"][0]["objects"][0]["begin"], 0.49)

    def test_bindings_remain_references_and_are_scoped_to_returned_owners(self):
        root, child, outside = self.layer(), None, None
        child = self.layer(father=root)
        outside = self.layer()
        included, excluded = self.obj(child, 1, 3), self.obj(child, 5, 7)
        other_project = self.create("project", {})
        foreign = self.layer(project_id=other_project)
        bindings = []
        for kind, source in (("layer", root), ("object", included), ("object", excluded)):
            bindings.append(self.create("bind", {"source_kind": kind, "source_project_id": self.project_id, "source_id": source,
                                                  "target_kind": "layer", "target_project_id": other_project, "target_id": foreign, "tips": "保留引用"}))
        result = project_details(self.connection, self.project_id, layer_id=root, begin=1, end=2)
        self.assertEqual([row["id"] for row in result["layers"]], [root, child])
        self.assertEqual(result["layers"][0]["bind"][0]["id"], bindings[0])
        binding = result["layers"][1]["objects"][0]["bind"][0]
        self.assertEqual(binding["id"], bindings[1])
        self.assertEqual(binding["target_project_id"], other_project)
        self.assertTrue(all(row["project_id"] == self.project_id for row in result["layers"]))

    def test_empty_results_are_distinct_from_missing_project_or_layer(self):
        layer = self.layer()
        self.assertEqual(project_details(self.connection, self.project_id, layer_id=layer)["counts"]["layers"], 1)
        empty = project_details(self.connection, self.project_id, layer_id=layer, begin=10, end=20)
        self.assertEqual(empty["layers"], [])
        self.assertEqual(empty["scope"]["layer_id"], layer)
        self.assertIsNone(project_details(self.connection, 999))
        self.assertIsNone(project_details(self.connection, self.project_id, layer_id=999))

    def test_cycles_do_not_loop_or_duplicate_records(self):
        a = self.layer()
        b = self.layer(father=a)
        dispatch(self.connection, {"action": "update", "kind": "layer", "project_id": self.project_id, "id": a, "data": {"father": b}}, checker=None)
        self.obj(b, 1, 2)
        full = project_details(self.connection, self.project_id)
        self.assertEqual(full["counts"]["unplaced_layers"], 2)
        selected = project_details(self.connection, self.project_id, layer_id=a, begin=1, end=2)
        self.assertEqual([row["id"] for row in selected["layers"]], [a, b])
        self.assertEqual(selected["layers"][0]["father"], b)
        json.dumps(selected)

    def test_deep_tree_bulk_read_is_flat_read_only_and_does_not_load_config(self):
        depth = 1100
        with self.connection:
            self.connection.executemany("INSERT INTO layers(project_id,id,name,type,config_ref,father) VALUES (?,?,?,?,?,?)",
                                        [(self.project_id, i, str(i), "text", "missing.toml", i-1 if i>1 else None) for i in range(1, depth+1)])
            self.connection.execute("UPDATE projects SET max_id=? WHERE id=?", (depth, self.project_id))
        self.obj(depth, 1, 2)
        before = self.connection.total_changes
        statements = []
        self.connection.set_trace_callback(statements.append)
        try:
            with patch.object(Path, "open", side_effect=AssertionError("no config/resource reads")):
                result = project_details(self.connection, self.project_id, layer_id=1, begin=1, end=2)
        finally:
            self.connection.set_trace_callback(None)
        self.assertEqual(result["counts"]["layers"], depth)
        self.assertEqual(result["layers"][-1]["depth"], depth-1)
        self.assertEqual(self.connection.total_changes, before)
        self.assertLessEqual(sum(sql.lstrip().upper().startswith(("SELECT", "WITH")) for sql in statements), 5)
        json.dumps(result)

    def test_transaction_and_cli(self):
        self.fixture()
        self.connection.execute("UPDATE projects SET name='pending'")
        result = project_details(self.connection, self.project_id)
        self.assertTrue(self.connection.in_transaction)
        self.assertEqual(result["project"]["name"], "pending")
        self.connection.rollback()
        with tempfile.TemporaryDirectory(prefix="layerweave-details-") as directory:
            path = Path(directory) / "data.sqlite3"
            copy = sqlite3.connect(path)
            try:
                self.connection.backup(copy)
            finally:
                copy.close()
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", "tools.common.project_details", str(path),
                                     str(self.project_id), "--begin", "3", "--end", "4", "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["counts"]["objects"], 2)
            self.assertIn("完整正文", format_details(data))

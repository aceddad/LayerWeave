"""详细展开的四种范围、原值时间筛选、父路径、完整引用及深层结构。"""

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from runtime.api import dispatch, open_database, read_record, read_project_details
from runtime.storage.database import SCHEMA_PATH
from tools.usage.common.project_details import format_details, project_details


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

    def test_subtree_time_filter_keeps_all_layers_and_only_matching_objects(self):
        (root, child, leaf, other, empty), objects = self.fixture()
        result = project_details(self.connection, self.project_id, layer_id=root, begin=3, end=4)
        self.assertEqual([layer["id"] for layer in result["layers"]], [root, child, leaf])
        self.assertEqual(result["layers"][0]["objects"], [])
        self.assertEqual(result["layers"][1]["objects"][0]["id"], objects[1])
        self.assertEqual(result["layers"][1]["objects"][0]["end"], 5)
        self.assertEqual(result["layers"][2]["objects"], [])
        self.assertEqual([layer["object_count"] for layer in result["layers"]], [0, 1, 0])
        point = project_details(self.connection, self.project_id, layer_id=root, begin=4, end=4)
        self.assertEqual(point["counts"]["objects"], 2)
        self.assertEqual([layer["id"] for layer in point["layers"]], [root, child, leaf])

    def test_time_filter_without_layer_searches_all_roots_numerically(self):
        (root, child, leaf, other, empty), objects = self.fixture()
        result = project_details(self.connection, self.project_id, begin=1, end=2)
        self.assertEqual([layer["id"] for layer in result["layers"]], [root, child, leaf, other, empty])
        self.assertEqual([obj["id"] for layer in result["layers"] for obj in layer["objects"]], [objects[0], objects[3]])
        self.assertEqual(result["layers"][3]["axis"]["unit"], "帧")

    def test_query_does_not_snap_positions_or_bounds(self):
        layer = self.layer(axis={"precision": 1})
        obj = self.obj(layer, 0.49, 0.51)
        # 模拟旧记录，验证读取不会因新写入规则而暗中重写或量化查询边界。
        self.connection.execute('UPDATE objects SET "begin"=?, "end"=? WHERE project_id=? AND id=?',
                                (0.49, 0.51, self.project_id, obj))
        self.connection.commit()
        self.assertEqual(project_details(self.connection, self.project_id, begin=0, end=0)["layers"][0]["objects"], [])
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
        self.assertEqual([row["id"] for row in empty["layers"]], [layer])
        self.assertEqual(empty["layers"][0]["objects"], [])
        self.assertEqual(empty["layers"][0]["object_count"], 0)
        self.assertIn("本范围 0 个直属对象", format_details(empty))
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

    def test_multiple_subtrees_deduplicate_parents_children_and_objects(self):
        (root, child, leaf, other, empty), objects = self.fixture()
        result = project_details(self.connection, self.project_id, layer_ids=[other, leaf, root, child, root], begin=3, end=4)
        self.assertEqual([row["id"] for row in result["layers"]], [root, child, leaf, other])
        self.assertEqual([row["depth"] for row in result["layers"]], [0, 1, 2, 0])
        self.assertEqual([row["object_count"] for row in result["layers"]], [0, 1, 0, 1])
        actual = [obj["id"] for row in result["layers"] for obj in row["objects"]]
        self.assertEqual(actual, [objects[1], objects[3]])
        self.assertEqual(len(actual), len(set(actual)))
        self.assertNotIn(empty, [row["id"] for row in result["layers"]])

    def test_disjoint_subtrees_follow_project_tree_order_not_request_or_id_order(self):
        first = self.layer()
        second = self.layer()
        first_child = self.layer(father=first)
        second_child = self.layer(father=second)
        result = project_details(self.connection, self.project_id, layer_ids=[second, first_child])
        self.assertEqual([row["id"] for row in result["layers"]], [first_child, second, second_child])
        self.assertEqual([row["depth"] for row in result["layers"]], [0, 0, 1])
        self.assertEqual(result["layers"][0]["father"], first)
        self.assertNotIn(first, [row["id"] for row in result["layers"]])

    def test_parent_chosen_after_child_and_reparented_ids_do_not_change_depth(self):
        child = self.layer()
        parent = self.layer()
        grandchild = self.layer(father=child)
        dispatch(self.connection, {"action": "update", "kind": "layer", "project_id": self.project_id,
                                   "id": child, "data": {"father": parent}}, checker=None)
        result = project_details(self.connection, self.project_id, layer_ids=[child, grandchild, parent])
        self.assertEqual([(row["id"], row["depth"]) for row in result["layers"]], [(parent, 0), (child, 1), (grandchild, 2)])

    def test_empty_missing_and_omitted_selections_are_distinct(self):
        layer = self.layer()
        self.assertEqual(project_details(self.connection, self.project_id)["counts"]["layers"], 1)
        empty = project_details(self.connection, self.project_id, layer_ids=[])
        self.assertEqual(empty["layers"], [])
        self.assertEqual(empty["issues"], [])
        self.assertEqual(empty["scope"]["layer_ids"], [])
        missing = project_details(self.connection, self.project_id, layer_ids=[999, layer, 999])
        self.assertEqual([row["id"] for row in missing["layers"]], [layer])
        self.assertEqual(missing["missing_layer_ids"], [999])
        self.assertEqual(missing["status"], "partial")
        self.assertEqual(len(missing["issues"]), 1)
        self.assertEqual(missing["issues"][0]["target"], {"kind": "layer", "project_id": self.project_id, "id": 999})
        self.assertEqual(missing["issues"][0]["severity"], "warn")
        absent = project_details(self.connection, self.project_id, layer_ids=[999])
        self.assertEqual(absent["layers"], [])
        self.assertEqual(absent["missing_layer_ids"], [999])
        self.assertIsNone(project_details(self.connection, 999, layer_ids=[]))
        with self.assertRaises(ValueError):
            project_details(self.connection, self.project_id, layer_id=layer, layer_ids=[])
        for value in ("1,2", [True], [1, "2"]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                project_details(self.connection, self.project_id, layer_ids=value)

    def test_missing_selection_respects_reporting_config_without_hiding_partial_scope(self):
        with tempfile.TemporaryDirectory(prefix="layerweave-details-policy-") as directory:
            root = Path(directory)
            (root / "logging").mkdir()
            (root / "logging/diagnostics.toml").write_text('[levels]\ntarget="none"\n', encoding="utf-8")
            result = project_details(self.connection, self.project_id, layer_ids=[999], config_root=root)
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["missing_layer_ids"], [999])

    def test_compact_keeps_content_falsy_values_and_exact_encapsulation(self):
        layer = self.layer(name="", tips="", axis={})
        information = {"text": "", "number": 0, "flag": False, "items": [], "data": {}, "nothing": None,
                       "metadata": {"name": "", "tips": "", "bind": [], "project_id": 0, "layer": 0}}
        id = self.obj(layer, 0, 0, name="", tips="", config_ref="objects/title.toml", information=information)
        before = project_details(self.connection, self.project_id)
        changes = self.connection.total_changes
        with patch.object(Path, "open", side_effect=AssertionError("valid compact reads do not load configs")):
            result = project_details(self.connection, self.project_id, compact=True)
        row, obj = result["layers"][0], result["layers"][0]["objects"][0]
        self.assertTrue(result["compact"])
        self.assertEqual(result["project"]["id"], self.project_id)
        self.assertEqual(row["axis"], {})
        self.assertEqual(row["depth"], 0)
        self.assertEqual(row["object_count"], 1)
        self.assertEqual(obj["id"], id)
        self.assertEqual(obj["config_ref"], "objects/title.toml")
        self.assertEqual((obj["begin"], obj["end"]), (0, 0))
        self.assertEqual(obj["information"], information)
        for field in ("project_id", "name", "tips", "bind"):
            self.assertNotIn(field, row)
            self.assertNotIn(field, obj)
        self.assertNotIn("layer", obj)
        self.assertNotIn("max_id", result["project"])
        self.assertIn('"flag": false', format_details(result))
        self.assertEqual(project_details(self.connection, self.project_id), before)
        self.assertEqual(self.connection.total_changes, changes)

    def test_compact_keeps_nonempty_notes_and_cross_project_bindings_on_empty_layers(self):
        layer = self.layer(name="原画", tips="需要补内容")
        foreign = self.create("project", {"name": "另一个项目"})
        foreign_layer = self.layer(project_id=foreign)
        binding = self.create("bind", {"source_kind": "layer", "source_project_id": self.project_id, "source_id": layer,
                                       "target_kind": "layer", "target_project_id": foreign, "target_id": foreign_layer, "tips": "参考"})
        obj = self.obj(layer, 1, 2, name="片段", tips="对象说明")
        result = project_details(self.connection, self.project_id, begin=10, end=20, compact=True)
        row = result["layers"][0]
        self.assertEqual(row["objects"], [])
        self.assertEqual(row["object_count"], 0)
        self.assertEqual(row["tips"], "需要补内容")
        self.assertEqual(row["bind"][0], read_record(self.connection, "bind", id=binding))
        self.assertEqual(row["bind"][0]["target_project_id"], foreign)
        full_window = project_details(self.connection, self.project_id, compact=True)
        self.assertEqual(full_window["layers"][0]["objects"][0]["tips"], "对象说明")
        self.assertEqual(full_window["layers"][0]["objects"][0]["id"], obj)
        self.assertIn("本范围 0 个直属对象", format_details(result))

    def test_compact_reduces_repetition_without_changing_selection_or_object_order(self):
        layer = self.layer(name="", tips="")
        ids = [self.obj(layer, begin, begin+2, name="", tips="", information={"text": "正文"}) for begin in (12, 9, 11, 10)]
        full = project_details(self.connection, self.project_id, layer_ids=[layer], begin=10, end=20)
        compact = project_details(self.connection, self.project_id, layer_ids=[layer], begin=10, end=20, compact=True)
        self.assertEqual(compact["counts"], full["counts"])
        self.assertEqual(compact["scope"], full["scope"])
        self.assertEqual([obj["id"] for obj in compact["layers"][0]["objects"]], [ids[1], ids[3], ids[2], ids[0]])
        self.assertEqual(compact["layers"][0]["objects"][0]["begin"], 9)
        encode = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        self.assertLess(len(encode(compact)), len(encode(full)))

    def test_multiple_cycles_are_finite_and_each_record_is_returned_once(self):
        a = self.layer()
        b = self.layer(father=a)
        dispatch(self.connection, {"action": "update", "kind": "layer", "project_id": self.project_id,
                                   "id": a, "data": {"father": b}}, checker=None)
        child = self.layer(father=b)
        self.obj(child, 1, 2)
        result = project_details(self.connection, self.project_id, layer_ids=[b, a, child, a], compact=True)
        self.assertEqual([row["id"] for row in result["layers"]], [a, b, child])
        self.assertEqual(result["counts"]["objects"], 1)

    def test_multiple_layer_bulk_read_uses_one_snapshot_without_loading_configuration(self):
        (root, child, leaf, other, empty), objects = self.fixture()
        self.connection.execute("UPDATE projects SET name='pending'")
        before = self.connection.total_changes
        statements = []
        self.connection.set_trace_callback(statements.append)
        try:
            with patch.object(Path, "open", side_effect=AssertionError("no config reads")):
                result = read_project_details(self.connection, self.project_id, layer_ids=[other, root], begin=10, end=20)
        finally:
            self.connection.set_trace_callback(None)
        self.assertTrue(self.connection.in_transaction)
        self.assertEqual(result["project"]["name"], "pending")
        self.assertEqual({row["id"] for row in result["layers"]}, {root, child, leaf, other})
        self.assertTrue(all(row["objects"] == [] for row in result["layers"]))
        self.assertLessEqual(sum(sql.lstrip().upper().startswith(("SELECT", "WITH")) for sql in statements), 5)
        self.assertEqual(self.connection.total_changes, before)
        self.connection.rollback()

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
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", "tools.usage.common.project_details", str(path),
                                     str(self.project_id), "--begin", "3", "--end", "4", "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["counts"]["objects"], 2)
            self.assertIn("完整正文", format_details(data))
            command = [sys.executable, "-X", "utf8", "-B", "-m", "tools.usage.common.project_details", str(path), str(self.project_id)]
            multi = subprocess.run([*command, "--layer-ids", "1", "4", "999", "--begin", "3", "--end", "4", "--compact", "--json"],
                                   capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(multi.returncode, 0, multi.stderr)
            selected = json.loads(multi.stdout)
            self.assertTrue(selected["compact"])
            self.assertEqual(selected["missing_layer_ids"], [999])
            self.assertEqual(selected["counts"]["objects"], 2)
            self.assertNotIn("project_id", selected["layers"][0])
            plain = subprocess.run([*command, "--layer-ids", "1", "999", "--begin", "10", "--end", "20", "--compact"],
                                   capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(plain.returncode, 0, plain.stderr)
            self.assertIn("本范围 0 个直属对象", plain.stdout)
            self.assertIn("[WARN] layer", plain.stderr)
            empty = subprocess.run([*command, "--layer-ids", "--compact", "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(empty.returncode, 0, empty.stderr)
            self.assertEqual(json.loads(empty.stdout)["layers"], [])

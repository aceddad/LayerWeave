"""子树删除、复制、引用映射与整批撤销；只操作内存/临时数据库。"""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tool.builtin.usage.editing.tree_service import copy_subtree, delete_subtree
from tool.builtin.usage.records.dispatch import dispatch
from support.api import initialize_database, open_database, read_record
from tool.builtin.usage.undo.service import undo_operation
from support.configuration.loader import DEFAULT_ROOT
from support.storage import crud
from support.storage.database import SCHEMA_PATH
from tool.builtin.usage.validation.runner import check_changes
from tool.builtin.usage.editing.subtrees import format_subtree


class SubtreeToolTests(unittest.TestCase):
    def setUp(self):
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.p = self.call("create", "project", data={"name": "作品"})["id"]
        self.parent = self.layer(name="外部父层", axis={"unit": "秒", "precision": 0.001})
        self.root = self.layer(name="歌词", father=self.parent)
        self.child = self.layer(name="标记", father=self.root)
        self.a = self.obj(self.root, "原歌词", information={"text": "歌词", "id": self.root, "target_id": self.child,
                     "extra": [1, 1.0, True, None, "assets/clip.wav"]})
        self.b = self.obj(self.child, "标题", config_ref="objects/title.toml")
        self.outside = self.obj(self.parent, "外部对象")
        self.q = self.call("create", "project", data={"name": "另一项目"})["id"]
        self.layer(project_id=self.q)
        self.peer = self.layer(project_id=self.q)
        self.assertEqual(self.peer, self.root)  # 跨项目同号不能被内部映射误改。
        self.internal = [self.bind("layer", self.root, "layer", self.root),
                         self.bind("layer", self.root, "object", self.b),
                         self.bind("object", self.a, "object", self.b),
                         self.bind("object", self.b, "object", self.a)]
        self.outgoing = [self.bind("object", self.a, "layer", self.parent),
                         self.bind("layer", self.child, "layer", self.peer, target_project=self.q)]
        self.incoming = [self.bind("object", self.outside, "object", self.a),
                         self.bind("layer", self.peer, "layer", self.child, source_project=self.q)]

    def call(self, action, kind, **args):
        if kind in {"layer", "object"}:
            args.setdefault("project_id", self.p)
        result = dispatch(self.c, {"action": action, "kind": kind, **args}, checker=None)
        self.assertTrue(result["ok"], result)
        return result

    def layer(self, project_id=None, **data):
        return self.call("create", "layer", project_id=self.p if project_id is None else project_id,
                         data={"config_ref": "layers/text.toml", **data})["id"]

    def obj(self, layer, name="", **data):
        return self.call("create", "object", data={"config_ref": "objects/text.toml", "layer": layer, "name": name,
                         "begin": 1.125, "end": 2.25, "information": {"text": name}, **data})["id"]

    def bind(self, source_kind, source, target_kind, target, *, source_project=None, target_project=None):
        return self.call("create", "bind", data={"source_kind": source_kind, "source_id": source,
                         "source_project_id": self.p if source_project is None else source_project,
                         "target_kind": target_kind, "target_id": target,
                         "target_project_id": self.p if target_project is None else target_project, "tips": "关系说明"})["id"]

    def row(self, kind, id):
        return read_record(self.c, kind, id=id, **({"project_id": self.p} if kind in {"layer", "object"} else {}))

    def snapshot(self):
        return {table: [tuple(row) for row in self.c.execute(f'SELECT * FROM "{table}" ORDER BY 1, 2')]
                for table in ("projects", "layers", "objects", "binds", "changes", "sqlite_sequence")}

    def source_rows(self):
        return [self.row(kind, id) for kind, ids in (("layer", [self.root, self.child]), ("object", [self.a, self.b]),
                                                   ("bind", [*self.internal, *self.outgoing, *self.incoming])) for id in ids]

    def maps(self, result):
        self.assertTrue(result["ok"], result)
        return {kind: {p["old_id"]: p["new_id"] for p in pairs} for kind, pairs in result["data"]["id_map"].items()}

    def undo(self, result):
        undone = undo_operation(self.c, result["operation_id"])
        self.assertTrue(undone["ok"], undone)
        return undone

    def test_copy_maps_hierarchy_internal_edges_self_edges_and_cycles(self):
        before = self.source_rows()
        result = copy_subtree(self.c, self.p, self.root, name="歌词第二版")
        maps = self.maps(result)
        self.assertEqual(result["data"]["counts"], {"layers": 2, "objects": 2, "binds": 6})
        self.assertEqual(result["checks"]["issues"], [])
        new_root = maps["layer"][self.root]
        self.assertEqual(result["data"]["layer_id"], new_root)
        self.assertEqual(self.row("layer", new_root)["father"], self.parent)
        self.assertEqual(self.row("layer", new_root)["name"], "歌词第二版")
        self.assertEqual(self.row("layer", maps["layer"][self.child])["father"], new_root)
        for old in (self.a, self.b):
            original, copied = self.row("object", old), self.row("object", maps["object"][old])
            self.assertEqual(copied["layer"], maps["layer"][original["layer"]])
            for key in ("config_ref", "name", "begin", "end", "information", "tips"):
                self.assertEqual(copied[key], original[key])
        for id in self.internal:
            old, new = self.row("bind", id), self.row("bind", maps["bind"][id])
            self.assertEqual(new["source_id"], maps[old["source_kind"]][old["source_id"]])
            self.assertEqual(new["target_id"], maps[old["target_kind"]][old["target_id"]])
            self.assertEqual(new["tips"], old["tips"])
        self.assertEqual(self.source_rows(), before)
        logs = read_record(self.c, "change", filters={"operation_id": result["operation_id"]})
        self.assertEqual(len(logs), 10)
        self.assertTrue(all(row["action"] == "create" for row in logs))
        self.assertIn("副本根层", format_subtree(result))

    def test_copy_preserves_external_targets_and_does_not_duplicate_incoming_edges(self):
        result = copy_subtree(self.c, self.p, self.root)
        maps = self.maps(result)
        for id in self.outgoing:
            old, new = self.row("bind", id), self.row("bind", maps["bind"][id])
            self.assertEqual({k: new[k] for k in ("target_kind", "target_project_id", "target_id")},
                             {k: old[k] for k in ("target_kind", "target_project_id", "target_id")})
        self.assertTrue(all(id not in maps["bind"] for id in self.incoming))
        self.assertEqual(self.row("bind", self.incoming[0])["target_id"], self.a)
        self.assertEqual(self.row("layer", maps["layer"][self.root])["name"], "歌词")
        copied_content = self.row("object", maps["object"][self.a])["information"]
        self.assertEqual(copied_content["id"], self.root)
        self.assertEqual(copied_content["target_id"], self.child)
        self.assertIs(copied_content["extra"][2], True)
        self.assertIsInstance(copied_content["extra"][1], float)

    def test_reference_mapping_uses_stored_numeric_identity(self):
        result = copy_subtree(self.c, str(self.p), str(self.root), name="数字编号")
        maps = self.maps(result)
        self.assertEqual(result["data"]["project_id"], self.p)
        self.assertEqual(result["data"]["source_layer_id"], self.root)
        copied_bind = self.row("bind", maps["bind"][self.internal[1]])
        self.assertEqual(copied_bind["target_id"], maps["object"][self.b])
        self.assertEqual(self.row("layer", result["data"]["layer_id"])["name"], "数字编号")
        deleted = delete_subtree(self.c, str(self.p), str(result["data"]["layer_id"]))
        self.assertTrue(deleted["ok"], deleted)
        self.assertEqual(deleted["data"]["project_id"], self.p)

    def test_copy_unknown_or_wrong_kind_reference_is_preserved_for_diagnostics(self):
        wrong = self.bind("layer", self.root, "layer", self.a)
        invalid = self.bind("layer", self.root, "bind", self.internal[0])
        result = copy_subtree(self.c, self.p, self.root)
        maps = self.maps(result)
        self.assertEqual(self.row("bind", maps["bind"][wrong])["target_id"], self.a)
        self.assertEqual(self.row("bind", maps["bind"][invalid])["target_id"], self.internal[0])
        self.assertTrue(any(i["code"] == "bind_kind" for i in result["checks"]["issues"]))

    def test_delete_removes_only_owned_data_and_reports_retained_incoming_edges(self):
        outside = [self.row("layer", self.parent), self.row("object", self.outside)]
        incoming = [self.row("bind", id) for id in self.incoming]
        maximum = self.row("project", self.p)["max_id"]
        result = delete_subtree(self.c, self.p, self.root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["counts"], {"layers": 2, "objects": 2, "binds": 6})
        for kind, ids in (("layer", [self.root, self.child]), ("object", [self.a, self.b]), ("bind", self.internal + self.outgoing)):
            self.assertTrue(all(self.row(kind, id) is None for id in ids))
        self.assertEqual([self.row("bind", id) for id in self.incoming], incoming)
        self.assertEqual([self.row("layer", self.parent), self.row("object", self.outside)], outside)
        self.assertEqual(self.row("project", self.p)["max_id"], maximum)
        self.assertEqual({i["target"]["id"] for i in result["checks"]["issues"]}, set(self.incoming))
        self.assertTrue(all(i["code"] == "bind_reference_missing" for i in result["checks"]["issues"]))
        self.assertEqual(self.c.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_delete_undo_redo_restores_original_ids_data_and_owned_bindings(self):
        original = self.source_rows()
        deleted = delete_subtree(self.c, self.p, self.root)
        restored = self.undo(deleted)
        self.assertEqual(self.source_rows(), original)
        self.assertEqual(restored["checks"]["issues"], [])
        self.undo(restored)
        self.assertIsNone(self.row("layer", self.root))
        self.undo(deleted)
        self.assertEqual(self.source_rows(), original)

    def test_copy_undo_redo_preserves_copied_ids_and_leaves_source_untouched(self):
        original = self.source_rows()
        copied = copy_subtree(self.c, self.p, self.root)
        maps = self.maps(copied)
        snapshot = {kind: [self.row(kind, id) for id in ids.values()] for kind, ids in maps.items()}
        undone = self.undo(copied)
        self.assertTrue(all(self.row(kind, id) is None for kind, ids in maps.items() for id in ids.values()))
        self.undo(undone)
        self.assertEqual({kind: [self.row(kind, id) for id in ids.values()] for kind, ids in maps.items()}, snapshot)
        self.assertEqual(self.source_rows(), original)
        next_layer = self.layer()
        self.assertGreater(next_layer, max([*maps["layer"].values(), *maps["object"].values()]))

    def test_copy_undo_detects_later_edits_without_partially_removing_the_copy(self):
        copied = copy_subtree(self.c, self.p, self.root)
        maps = self.maps(copied)
        self.call("update", "object", id=maps["object"][self.a], data={"name": "后续修改"})
        before = self.snapshot()
        result = undo_operation(self.c, copied["operation_id"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "undo_conflict")
        self.assertEqual(self.snapshot(), before)

    def test_missing_root_never_selects_all_layers(self):
        for function in (copy_subtree, delete_subtree):
            for pid, id in ((self.p, None), (self.p, 99999), (99999, self.root), (self.p, self.a)):
                before = self.snapshot()
                result = function(self.c, pid, id)
                self.assertFalse(result["ok"])
                self.assertFalse(result["applied"])
                self.assertEqual(self.snapshot(), before)

    def test_empty_layer_and_empty_copy_name(self):
        empty = self.layer(axis={})
        result = copy_subtree(self.c, self.p, empty, name="")
        maps = self.maps(result)
        self.assertEqual(result["data"]["counts"], {"layers": 1, "objects": 0, "binds": 0})
        copied = self.row("layer", maps["layer"][empty])
        self.assertEqual(copied["name"], "")
        self.assertEqual(copied["axis"], {})
        self.assertIsNone(copied["father"])
        self.assertTrue(delete_subtree(self.c, self.p, empty)["ok"])

    def test_child_created_before_its_new_parent_still_copies_to_the_new_parent(self):
        later_parent = self.layer(father=self.root)
        self.call("update", "layer", id=self.child, data={"father": later_parent})
        result = copy_subtree(self.c, self.p, self.root)
        maps = self.maps(result)
        self.assertEqual(self.row("layer", maps["layer"][self.child])["father"], maps["layer"][later_parent])

    def test_copy_uses_normal_coordinate_precision_without_changing_source(self):
        self.c.execute('UPDATE objects SET "begin"=?, "end"=? WHERE project_id=? AND id=?', (0.12345, 0.45678, self.p, self.a))
        self.c.commit()
        result = copy_subtree(self.c, self.p, self.root)
        maps = self.maps(result)
        new = self.row("object", maps["object"][self.a])
        self.assertEqual((new["begin"], new["end"]), (0.123, 0.457))
        self.assertEqual(self.row("object", self.a)["begin"], 0.12345)

    def test_broken_config_does_not_block_copying_raw_records(self):
        self.call("update", "object", id=self.a, data={"config_ref": "objects/missing.toml"})
        result = copy_subtree(self.c, self.p, self.root)
        maps = self.maps(result)
        self.assertEqual(self.row("object", maps["object"][self.a])["config_ref"], "objects/missing.toml")
        self.assertEqual(result["operation"]["status"], "committed")
        self.assertEqual(result["checks"]["status"], "partial")

    def test_failure_rolls_back_records_counters_and_logs_in_both_tools(self):
        self.c.execute("CREATE TRIGGER fail_copy BEFORE INSERT ON binds BEGIN SELECT RAISE(ABORT,'test copy failure'); END")
        before = self.snapshot()
        result = copy_subtree(self.c, self.p, self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(self.snapshot(), before)
        self.c.execute("DROP TRIGGER fail_copy")
        self.c.execute("CREATE TRIGGER fail_delete BEFORE DELETE ON layers BEGIN SELECT RAISE(ABORT,'test delete failure'); END")
        before = self.snapshot()
        result = delete_subtree(self.c, self.p, self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(self.snapshot(), before)

    def test_caller_transaction_is_preserved(self):
        self.c.execute("UPDATE projects SET tips='pending' WHERE id=?", (self.p,))
        for function in (copy_subtree, delete_subtree):
            self.assertFalse(function(self.c, self.p, self.root)["ok"])
            self.assertTrue(self.c.in_transaction)
        self.c.rollback()
        self.assertEqual(self.row("project", self.p)["tips"], "")

    def test_checker_runs_once_after_complete_batch_and_custom_root_is_respected(self):
        calls = []
        def checker(changes, read):
            calls.append(changes)
            self.assertFalse(self.c.in_transaction)
            self.assertEqual(len(changes), 10)
            return check_changes(changes, read)
        result = copy_subtree(self.c, self.p, self.root, checker=checker)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(calls), 1)
        with tempfile.TemporaryDirectory(prefix="layerweave-subtree-config-") as folder:
            config = Path(folder) / "configs"
            shutil.copytree(DEFAULT_ROOT, config)
            (config / "logging/diagnostics.toml").write_text('[levels]\nbind_reference_missing="error"\n', encoding="utf-8")
            deleted = delete_subtree(self.c, self.p, self.root, config_root=config)
            self.assertTrue(deleted["ok"], deleted)
            self.assertTrue(all(i["severity"] == "error" for i in deleted["checks"]["issues"]))

    def test_legacy_cycle_can_be_deleted_but_not_copied_or_restored(self):
        with self.c:
            self.c.execute("UPDATE layers SET father=? WHERE project_id=? AND id=?", (self.child, self.p, self.root))
        before = self.snapshot()
        copied = copy_subtree(self.c, self.p, self.root)
        self.assertFalse(copied["ok"])
        self.assertEqual(copied["error"]["code"], "father_cycle")
        self.assertEqual(self.snapshot(), before)
        deleted = delete_subtree(self.c, self.p, self.root)
        self.assertTrue(deleted["ok"], deleted)
        restored = undo_operation(self.c, deleted["operation_id"])
        self.assertFalse(restored["ok"])
        self.assertEqual(restored["error"]["code"], "father_cycle")
        self.assertEqual(self.c.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_deep_tree_uses_iterative_traversal(self):
        from support.api import transaction
        parent = self.root
        with transaction(self.c) as write:
            for _ in range(1100):
                row, _ = crud.create(self.c, "layer", {"config_ref": "layers/text.toml", "type": "text", "father": parent},
                                     project_id=self.p, operation_id=write.operation_id)
                parent = row["id"]
        result = copy_subtree(self.c, self.p, self.root, checker=None)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["counts"]["layers"], 1102)
        deleted = delete_subtree(self.c, self.p, result["data"]["layer_id"], checker=None)
        self.assertTrue(deleted["ok"], deleted)
        self.assertEqual(deleted["data"]["counts"]["layers"], 1102)

    def test_cli_copy_and_delete_use_temporary_database(self):
        with tempfile.TemporaryDirectory(prefix="layerweave-subtree-cli-") as folder:
            path = initialize_database(Path(folder) / "test.sqlite3")
            c = open_database(path)
            self.c.backup(c)
            c.close()
            command = [sys.executable, "-X", "utf8", "-B", "-m", "tool.builtin.usage.editing.subtrees", str(path), str(self.p)]
            copied = subprocess.run([*command, "copy", str(self.root), "--name", "歌词副本", "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(copied.returncode, 0, copied.stderr)
            result = json.loads(copied.stdout)
            self.assertTrue(result["ok"])
            root = result["data"]["layer_id"]
            deleted = subprocess.run([*command, "delete", str(root)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(deleted.returncode, 0, deleted.stderr)
            self.assertIn("删除子树", deleted.stdout)
            missing = subprocess.run([*command, "delete", str(root), "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(missing.returncode, 1)
            self.assertFalse(json.loads(missing.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()

"""对象跨项目搬移复用子树迁移规则，保留源层、精度与整批撤销。"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tool.builtin.usage.records.dispatch import dispatch
from support.api import open_database, read_record
from tool.builtin.usage.editing.tree_service import transfer_objects
from tool.builtin.usage.undo.service import undo_operation
from support.storage.database import SCHEMA_PATH


class ObjectTransferTests(unittest.TestCase):
    def setUp(self):
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.p = self.call("create", "project", data={})["id"]
        self.q = self.call("create", "project", data={})["id"]
        self.a = self.layer(self.p)
        self.b = self.layer(self.p)
        self.dst = self.layer(self.q, axis={"unit": "帧", "precision": 1})
        self.first = self.obj(self.a, 0.1, 0.2)
        self.second = self.obj(self.b, 0.3, 0.4)
        self.unselected = self.obj(self.a, 1, 2)
        self.internal = self.bind(self.p, "object", self.first, self.p, "object", self.second)
        self.self_bind = self.bind(self.p, "object", self.first, self.p, "object", self.first)
        self.outside = self.bind(self.p, "object", self.first, self.p, "object", self.unselected)
        self.to_layer = self.bind(self.p, "object", self.second, self.p, "layer", self.b)
        self.local_in = self.bind(self.p, "object", self.unselected, self.p, "object", self.first)
        self.foreign_in = self.bind(self.q, "layer", self.dst, self.p, "object", self.second)

    def call(self, action, kind, **kwargs):
        result = dispatch(self.c, {"action": action, "kind": kind, **kwargs}, checker=None)
        self.assertTrue(result["ok"], result)
        return result

    def layer(self, project, **kwargs):
        return self.call("create", "layer", project_id=project, data={"config_ref": "layers/text.toml", **kwargs})["id"]

    def obj(self, layer, begin, end):
        return self.call("create", "object", project_id=self.p, data={"layer": layer, "config_ref": "objects/text.toml",
                         "begin": begin, "end": end, "information": {"text": "文字", "source": "assets/a.txt", "id": 42}})["id"]

    def bind(self, sp, sk, si, tp, tk, ti):
        return self.call("create", "bind", data={"source_project_id": sp, "source_kind": sk, "source_id": si,
                         "target_project_id": tp, "target_kind": tk, "target_id": ti})["id"]

    def row(self, kind, id, project=None):
        return read_record(self.c, kind, id=id, **({"project_id": self.p if project is None else project}
                                                if kind in {"layer", "object"} else {}))

    def snapshot(self):
        return {table: [tuple(row) for row in self.c.execute(f'SELECT * FROM "{table}" ORDER BY 1, 2')]
                for table in ("projects", "layers", "objects", "binds", "changes", "sqlite_sequence")}

    def transfer(self, **kwargs):
        return transfer_objects(self.c, self.p, [self.first, self.second], self.q, self.dst, **kwargs)

    def maps(self, result):
        self.assertTrue(result["ok"], result)
        return {kind: {pair["old_id"]: pair["new_id"] for pair in pairs} for kind, pairs in result["data"]["id_map"].items()}

    def test_copy_multiple_layers_deduplicates_and_preserves_raw_values_and_source(self):
        self.c.execute('UPDATE objects SET "begin"=? WHERE project_id=? AND id=?', (0.123456789, self.p, self.first))
        self.c.commit()
        originals = [self.row("object", id) for id in (self.first, self.second)]
        incoming = self.row("bind", self.foreign_in)
        result = transfer_objects(self.c, str(self.p), [self.first, str(self.first), self.second], str(self.q), str(self.dst))
        maps = self.maps(result)
        self.assertEqual(maps["layer"], {})
        self.assertEqual(result["data"]["counts"], {"layers": 0, "objects": 2, "binds": 4})
        self.assertEqual(result["data"]["source_object_ids"], [self.first, self.second])
        for old in originals:
            new = self.row("object", maps["object"][old["id"]], self.q)
            self.assertEqual({k: v for k, v in new.items() if k not in {"project_id", "id", "layer"}},
                             {k: v for k, v in old.items() if k not in {"project_id", "id", "layer"}})
            self.assertEqual(new["layer"], self.dst)
            self.assertEqual(self.row("object", old["id"]), old)
        self.assertEqual(self.row("bind", self.foreign_in), incoming)
        self.assertEqual(result["data"]["redirected_bind_ids"], [])

    def test_internal_self_external_and_layer_targets_are_mapped_by_full_identity(self):
        maps = self.maps(self.transfer())
        for id in (self.internal, self.self_bind, self.outside, self.to_layer):
            old, new = self.row("bind", id), self.row("bind", maps["bind"][id])
            self.assertEqual((new["source_project_id"], new["source_id"]), (self.q, maps["object"][old["source_id"]]))
            if id in (self.internal, self.self_bind):
                self.assertEqual((new["target_project_id"], new["target_id"]), (self.q, maps["object"][old["target_id"]]))
            else:
                self.assertEqual((new["target_project_id"], new["target_kind"], new["target_id"]),
                                 (old["target_project_id"], old["target_kind"], old["target_id"]))

    def test_cut_undo_redo_preserves_source_layers_and_allocation_highwater(self):
        originals = [self.row("object", id) for id in (self.first, self.second)]
        source_max = self.row("project", self.p)["max_id"]
        result = self.transfer(mode="cut")
        maps = self.maps(result)
        dest_max = self.row("project", self.q)["max_id"]
        self.assertEqual(set(result["data"]["redirected_bind_ids"]), {self.local_in, self.foreign_in})
        for id, old_target in ((self.local_in, self.first), (self.foreign_in, self.second)):
            self.assertEqual(self.row("bind", id)["target_id"], maps["object"][old_target])
            self.assertEqual(self.row("bind", id)["target_project_id"], self.q)
        self.assertIsNotNone(self.row("layer", self.a))
        self.assertIsNotNone(self.row("layer", self.b))
        self.assertIsNotNone(self.row("object", self.unselected))
        for id in (self.first, self.second):
            self.assertIsNone(self.row("object", id))
        undone = undo_operation(self.c, result["operation_id"])
        self.assertTrue(undone["ok"], undone)
        for old in originals:
            self.assertEqual(self.row("object", old["id"]), old)
            self.assertIsNone(self.row("object", maps["object"][old["id"]], self.q))
        self.assertEqual(self.row("bind", self.foreign_in)["target_project_id"], self.p)
        self.assertEqual(self.row("project", self.q)["max_id"], dest_max)
        self.assertEqual(self.row("project", self.p)["max_id"], source_max)
        redone = undo_operation(self.c, undone["operation_id"])
        self.assertTrue(redone["ok"], redone)
        self.assertIsNone(self.row("object", self.first))

    def test_missing_targets_bad_mode_and_empty_selection_do_not_write(self):
        cases = [(self.p, [999], self.q, self.dst, "copy"), (999, [], self.q, self.dst, "copy"),
                 (self.p, [self.first], self.p, self.a, "copy"), (self.p, [self.first], self.q, 999, "copy"),
                 (self.p, [None], self.q, self.dst, "copy"), (self.p, [self.first], self.q, self.dst, "move"),
                 (self.p, None, self.q, self.dst, "copy")]
        for source, ids, destination, layer, mode in cases:
            before = self.snapshot()
            result = transfer_objects(self.c, source, ids, destination, layer, mode=mode)
            self.assertFalse(result["ok"], result)
            self.assertEqual(self.snapshot(), before)
        before = self.snapshot()
        result = transfer_objects(self.c, self.p, [], self.q, self.dst, mode="cut")
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["applied"])
        self.assertEqual(self.snapshot(), before)

    def test_failure_after_creation_rolls_back_ids_logs_and_redirects(self):
        for trigger in (f"BEFORE UPDATE ON binds WHEN old.id={self.foreign_in}",
                        f"BEFORE DELETE ON objects WHEN old.id={self.second} AND old.project_id={self.p}"):
            self.c.execute(f"CREATE TRIGGER fail_transfer {trigger} BEGIN SELECT RAISE(ABORT,'test failure'); END")
            before = self.snapshot()
            result = self.transfer(mode="cut")
            self.assertFalse(result["ok"])
            self.assertEqual(self.snapshot(), before)
            self.c.execute("DROP TRIGGER fail_transfer")

    def test_undo_conflict_on_destination_stops_whole_batch(self):
        result = self.transfer(mode="cut")
        maps = self.maps(result)
        self.call("update", "object", project_id=self.q, id=maps["object"][self.first], data={"tips": "later"})
        before = self.snapshot()
        undone = undo_operation(self.c, result["operation_id"])
        self.assertFalse(undone["ok"])
        self.assertEqual(self.snapshot(), before)

    def test_target_compatibility_is_postcommit_and_custom_checker_runs_once(self):
        self.call("update", "layer", project_id=self.q, id=self.dst, data={"config_ref": "layers/image.toml"})
        result = self.transfer()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["applied"])
        self.assertTrue(result["checks"]["issues"])
        calls = []
        def checker(changes, read):
            calls.append(changes)
            self.assertFalse(self.c.in_transaction)
            self.assertIsNone(read("object", project_id=self.p, id=self.first))
            self.assertEqual(read("bind", id=self.foreign_in)["target_project_id"], self.q)
            return []
        self.assertTrue(self.transfer(mode="cut", checker=checker)["ok"])
        self.assertEqual(len(calls), 1)

    def test_cli_copy_and_cut(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "transfer.sqlite3"
            c = open_database(path)
            self.c.backup(c)
            c.close()
            for mode in ("copy", "cut"):
                result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", "tool.builtin.usage.editing.transfer_objects", str(path),
                                         str(self.p), mode, str(self.q), str(self.dst), "--ids", str(self.first), "--json"],
                                        capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()

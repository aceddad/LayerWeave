"""跨项目复制/剪切：重新发号、原数值、引用归属、原子回滚和撤销。"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runtime.api import dispatch, open_database, read_history, read_record, transfer_subtree, undo_operation
from runtime.storage.database import SCHEMA_PATH


class TransferToolsTests(unittest.TestCase):
    def setUp(self):
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.p = self.call("create", "project", data={})["id"]
        self.q = self.call("create", "project", data={})["id"]
        self.parent = self.layer(self.p, axis={"unit": "秒", "precision": 0.001})
        self.root = self.layer(self.p, father=self.parent, name="源子树")
        self.child = self.layer(self.p, father=self.root)
        self.obj = self.call("create", "object", project_id=self.p, data={"config_ref": "objects/text.toml", "layer": self.child,
                            "information": {"text": "内容", "object_id": 4, "source": "assets/file.wav"}, "begin": 0.1, "end": 0.4})["id"]
        self.other = self.layer(self.q, axis={"unit": "帧", "precision": 1})
        self.collision = self.layer(self.q)
        self.assertEqual(self.collision, self.root)
        self.internal = self.bind(self.p, "layer", self.root, self.p, "object", self.obj)
        self.self_bind = self.bind(self.p, "object", self.obj, self.p, "object", self.obj)
        self.outgoing = self.bind(self.p, "object", self.obj, self.p, "layer", self.parent)
        self.foreign = self.bind(self.p, "layer", self.child, self.q, "layer", self.collision)
        self.incoming = self.bind(self.q, "layer", self.other, self.p, "object", self.obj)
        self.local_incoming = self.bind(self.p, "layer", self.parent, self.p, "layer", self.root)

    def call(self, action, kind, **args):
        result = dispatch(self.c, {"action": action, "kind": kind, **args}, checker=None)
        self.assertTrue(result["ok"], result)
        return result

    def layer(self, project, **data):
        return self.call("create", "layer", project_id=project, data={"config_ref": "layers/text.toml", **data})["id"]

    def bind(self, sp, sk, si, tp, tk, ti):
        return self.call("create", "bind", data={"source_project_id": sp, "source_kind": sk, "source_id": si,
                         "target_project_id": tp, "target_kind": tk, "target_id": ti, "tips": "原关联"})["id"]

    def row(self, kind, id, project=None):
        return read_record(self.c, kind, id=id, **({"project_id": self.p if project is None else project} if kind in {"layer", "object"} else {}))

    def snapshot(self):
        return {table: [tuple(row) for row in self.c.execute(f'SELECT * FROM "{table}" ORDER BY 1, 2')]
                for table in ("projects", "layers", "objects", "binds", "changes", "sqlite_sequence")}

    def maps(self, result):
        self.assertTrue(result["ok"], result)
        return {kind: {item["old_id"]: item["new_id"] for item in pairs} for kind, pairs in result["data"]["id_map"].items()}

    def undo(self, result):
        undone = undo_operation(self.c, result["operation_id"])
        self.assertTrue(undone["ok"], undone)
        return undone

    def test_copy_allocates_in_destination_and_preserves_source_and_incoming(self):
        original = self.row("object", self.obj)
        collision = self.row("layer", self.collision, self.q)
        incoming = self.row("bind", self.incoming)
        result = transfer_subtree(self.c, str(self.p), str(self.root), str(self.q), name="副本")
        maps = self.maps(result)
        self.assertEqual(result["data"]["project_id"], self.q)
        root = self.row("layer", maps["layer"][self.root], self.q)
        self.assertIsNone(root["father"])
        self.assertIsNone(root["axis"])
        self.assertEqual(root["name"], "副本")
        self.assertEqual(self.row("layer", maps["layer"][self.child], self.q)["father"], root["id"])
        self.assertEqual(self.row("object", self.obj), original)
        self.assertEqual(self.row("layer", self.collision, self.q), collision)
        self.assertEqual(self.row("bind", self.incoming), incoming)
        self.assertEqual(result["data"]["redirected_bind_ids"], [])
        self.assertGreater(maps["layer"][self.root], self.collision)

    def test_internal_endpoints_move_but_outgoing_external_addresses_are_preserved(self):
        result = transfer_subtree(self.c, self.p, self.root, self.q)
        maps = self.maps(result)
        for id in (self.internal, self.self_bind):
            old, new = self.row("bind", id), self.row("bind", maps["bind"][id])
            for side in ("source", "target"):
                self.assertEqual(new[f"{side}_project_id"], self.q)
                self.assertEqual(new[f"{side}_id"], maps[old[f"{side}_kind"]][old[f"{side}_id"]])
        for id in (self.outgoing, self.foreign):
            old, new = self.row("bind", id), self.row("bind", maps["bind"][id])
            self.assertEqual(new["source_project_id"], self.q)
            self.assertEqual((new["target_project_id"], new["target_kind"], new["target_id"]),
                             (old["target_project_id"], old["target_kind"], old["target_id"]))

    def test_transfer_preserves_raw_numbers_explicit_axis_and_free_content(self):
        self.call("update", "layer", project_id=self.p, id=self.root, data={"axis": {"unit": "自定义", "precision": 0.1}})
        self.c.execute('UPDATE objects SET "begin"=?, "end"=? WHERE project_id=? AND id=?', (0.123456789, 0.987654321, self.p, self.obj))
        self.c.commit()
        original = self.row("object", self.obj)
        result = transfer_subtree(self.c, self.p, self.root, self.q)
        maps = self.maps(result)
        copied = self.row("object", maps["object"][self.obj], self.q)
        self.assertEqual((copied["begin"], copied["end"]), (0.123456789, 0.987654321))
        self.assertEqual(copied["information"], original["information"])
        self.assertEqual(self.row("layer", maps["layer"][self.root], self.q)["axis"], {"unit": "自定义", "precision": 0.1})
        self.assertEqual(self.row("object", self.obj), original)

    def test_cut_redirects_external_incoming_bindings_without_changing_their_identity(self):
        original_incoming = [self.row("bind", id) for id in (self.incoming, self.local_incoming)]
        old_max = self.row("project", self.p)["max_id"]
        result = transfer_subtree(self.c, self.p, self.root, self.q, mode="cut")
        maps = self.maps(result)
        self.assertEqual(set(result["data"]["redirected_bind_ids"]), {self.incoming, self.local_incoming})
        self.assertIsNone(self.row("layer", self.root))
        self.assertIsNone(self.row("object", self.obj))
        self.assertIsNotNone(self.row("layer", self.parent))
        self.assertEqual(self.row("project", self.p)["max_id"], old_max)
        for old in original_incoming:
            new = self.row("bind", old["id"])
            self.assertEqual(new["target_project_id"], self.q)
            self.assertEqual(new["target_id"], maps[old["target_kind"]][old["target_id"]])
            for key in ("id", "source_kind", "source_project_id", "source_id", "tips"):
                self.assertEqual(new[key], old[key])
        self.assertTrue(all(self.row("bind", id) is None for id in (self.internal, self.self_bind, self.outgoing, self.foreign)))
        self.assertEqual(result["checks"]["issues"], [])
        self.assertEqual(self.c.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_cut_undo_redo_restores_both_projects_and_external_references(self):
        original = self.row("object", self.obj)
        incoming = self.row("bind", self.incoming)
        result = transfer_subtree(self.c, self.p, self.root, self.q, mode="cut")
        maps = self.maps(result)
        destination_max = self.row("project", self.q)["max_id"]
        u = self.undo(result)
        self.assertEqual(self.row("object", self.obj), original)
        self.assertEqual(self.row("bind", self.incoming), incoming)
        self.assertIsNone(self.row("object", maps["object"][self.obj], self.q))
        self.assertEqual(self.row("project", self.q)["max_id"], destination_max)
        self.undo(u)
        self.assertIsNone(self.row("object", self.obj))
        self.assertEqual(self.row("bind", self.incoming)["target_id"], maps["object"][self.obj])
        history = read_history(self.c, operation_id=result["operation_id"])["items"][0]
        self.assertEqual(set(history["project_ids"]), {self.p, self.q})

    def test_later_edit_to_redirected_reference_blocks_whole_undo(self):
        moved = transfer_subtree(self.c, self.p, self.root, self.q, mode="cut")
        self.assertTrue(moved["ok"], moved)
        self.call("update", "bind", id=self.incoming, data={"tips": "他人后来修改"})
        before = self.snapshot()
        result = undo_operation(self.c, moved["operation_id"])
        self.assertFalse(result["ok"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(result["error"]["conflicts"][0]["target"]["kind"], "bind")

    def test_invalid_target_or_mode_has_no_effect(self):
        for target, mode in ((self.p, "cut"), (999, "copy"), (None, "cut"), (self.q, "move")):
            before = self.snapshot()
            result = transfer_subtree(self.c, self.p, self.root, target, mode=mode)
            self.assertFalse(result["ok"])
            self.assertEqual(self.snapshot(), before)

    def test_failure_during_reference_update_or_source_delete_rolls_back_everything(self):
        for stage, trigger in (("redirect", f"BEFORE UPDATE ON binds WHEN old.id={self.incoming}"),
                               ("delete", f"BEFORE DELETE ON layers WHEN old.id={self.root} AND old.project_id={self.p}")):
            self.c.execute(f"CREATE TRIGGER fail_transfer {trigger} BEGIN SELECT RAISE(ABORT,'{stage} failure'); END")
            before = self.snapshot()
            result = transfer_subtree(self.c, self.p, self.root, self.q, mode="cut")
            self.assertFalse(result["ok"])
            self.assertEqual(self.snapshot(), before)
            self.c.execute("DROP TRIGGER fail_transfer")

    def test_checker_sees_only_final_state_once_and_caller_transaction_is_preserved(self):
        calls = []
        def checker(changes, read):
            calls.append(changes)
            self.assertFalse(self.c.in_transaction)
            self.assertIsNone(read("layer", project_id=self.p, id=self.root))
            self.assertEqual(read("bind", id=self.incoming)["target_project_id"], self.q)
            return []
        result = transfer_subtree(self.c, self.p, self.root, self.q, mode="cut", checker=checker)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(calls), 1)
        self.c.execute("UPDATE projects SET tips='pending' WHERE id=?", (self.q,))
        failed = transfer_subtree(self.c, self.q, result["data"]["layer_id"], self.p, mode="cut")
        self.assertFalse(failed["ok"])
        self.assertTrue(self.c.in_transaction)
        self.c.rollback()

    def test_cli_copy_and_cut_are_explicit_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "transfer.sqlite3"
            c = open_database(path)
            self.c.backup(c)
            c.close()
            for mode in ("copy", "cut"):
                result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", "tools.common.transfer", str(path), str(self.p), mode,
                                         str(self.root), str(self.q), "--json"], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()

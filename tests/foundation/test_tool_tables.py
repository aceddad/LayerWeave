"""工具表与核心记录共用事务、身份、历史与恢复；仅使用专用临时数据库。"""
from copy import deepcopy
from contextlib import closing
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from layerweave.support.api import initialize_database, open_database, read_record, register_tables, run_operation, table_specs, transaction
from layerweave.support.feedback import format_feedback
from layerweave.support.storage import crud
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.tool.builtin.usage.history.service import read_history
from layerweave.tool.builtin.usage.undo.service import undo_operation


TABLES = {
    "review_note": {
        "fields": {"name": {"type": "TEXT", "default": ""}, "data": {"type": "JSON", "default": {}}, "layer_id": "INTEGER"},
        "references": [{"fields": ["project_id", "layer_id"], "kind": "layer"}],
    },
    "review_reply": {
        "fields": {"note_id": {"type": "INTEGER", "nullable": False}, "body": "TEXT"},
        "references": [{"fields": ["project_id", "note_id"], "kind": "review_note"}],
    },
    "render_job": {"scoped": False, "fields": {"state": {"type": "TEXT", "default": "queued"}, "data": "JSON"}},
}


class ToolTableTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="layerweave-tool-tables-")
        self.addCleanup(temp.cleanup)
        self.path = initialize_database(Path(temp.name) / "project.sqlite3")
        self.c = open_database(self.path)
        self.addCleanup(self.c.close)
        register_tables(self.c, TABLES)
        with transaction(self.c) as write:
            self.p = write.create("project", {"name": "one"})["id"]
            self.q = write.create("project", {"name": "two"})["id"]

    def create(self, kind="review_note", data=None, project_id=None):
        scope = {} if kind == "render_job" else {"project_id": self.p if project_id is None else project_id}
        return dispatch(self.c, {"action": "create", "kind": kind, "data": data or {}, **scope})

    def row(self, kind, id, project_id=None):
        return read_record(self.c, kind, id=id, **({"project_id": self.p if project_id is None else project_id} if table_specs(self.c)[kind]["scoped"] else {}))

    def snapshot(self):
        return list(self.c.iterdump())

    def test_default_values_json_and_shared_project_numbering(self):
        first = self.create(data={"data": {"items": [True, 1, 1.0]}})
        layer = self.create("layer", {"type": "text", "config_ref": "layers/text.toml"})
        second = self.create(project_id=self.q)
        self.assertEqual((first["id"], layer["id"], second["id"]), (1, 2, 1))
        self.assertEqual(first["data"]["data"], {"items": [True, 1, 1.0]})
        self.assertEqual(second["data"]["name"], "")
        self.assertEqual(second["data"]["data"], {})
        self.assertTrue(first["ok"])
        self.assertEqual(first["checks"]["status"], "completed")
        self.assertIn(f"review_note ({self.p}, 1)", format_feedback(first))

    def test_same_local_id_in_two_projects_undo_redo_and_history(self):
        result = dispatch(self.c, [{"action": "create", "kind": "review_note", "project_id": p, "data": {"name": str(p)}} for p in (self.p, self.q)])
        self.assertEqual([r["id"] for r in result["results"]], [1, 1])
        self.assertEqual({r["target"]["project_id"] for r in result["operation"]["changes"]}, {self.p, self.q})
        history = read_history(self.c, self.q, kind="review_note", id=1)
        self.assertEqual(history["items"][0]["change_count"], 2)
        undone = undo_operation(self.c, result["operation_id"])
        self.assertTrue(undone["ok"], undone)
        self.assertIsNone(self.row("review_note", 1, self.p))
        self.assertIsNone(self.row("review_note", 1, self.q))
        redone = undo_operation(self.c, undone["operation_id"])
        self.assertTrue(redone["ok"], redone)
        self.assertEqual(self.row("review_note", 1, self.q)["name"], str(self.q))

    def test_global_ids_are_independent_and_not_recycled_after_undo(self):
        created = self.create("render_job")
        self.assertIsNone(created["operation"]["changes"][0]["target"]["project_id"])
        self.assertEqual(self.row("project", self.p)["max_id"], 0)
        undone = undo_operation(self.c, created["operation_id"])
        self.assertTrue(undone["ok"], undone)
        newer = self.create("render_job")
        self.assertGreater(newer["id"], created["id"])
        self.assertTrue(undo_operation(self.c, undone["operation_id"])["ok"])
        self.assertEqual(self.row("render_job", created["id"])["state"], "queued")

    def test_mixed_table_transaction_failure_rolls_back_all_rows_counters_and_logs(self):
        before = self.snapshot()
        result = dispatch(self.c, [
            {"action": "create", "kind": "layer", "project_id": self.p, "data": {"config_ref": "layers/text.toml"}},
            {"action": "create", "kind": "review_note", "project_id": self.p, "data": {"layer_id": 1}},
            {"action": "create", "kind": "render_job", "data": {}},
            {"action": "create", "kind": "review_reply", "project_id": self.p, "data": {"note_id": 999}},
        ])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "missing_reference")
        self.assertEqual(result["error"]["reference"]["kind"], "review_note")
        self.assertEqual(before, self.snapshot())

    def test_log_failure_rolls_back_tool_record(self):
        before = self.snapshot()
        with patch.object(crud, "append_change", side_effect=RuntimeError("log unavailable")):
            result = self.create()
        self.assertFalse(result["ok"])
        self.assertEqual(before, self.snapshot())

    def test_undo_redo_mixed_project_layer_tool_and_global_batch(self):
        def work(write):
            p = write.create("project", {})["id"]
            layer = write.create("layer", {"type": "text", "config_ref": "layers/text.toml"}, project_id=p)
            note = write.create("review_note", {"layer_id": layer["id"]}, project_id=p)
            write.create("review_reply", {"note_id": note["id"]}, project_id=p)
            job = write.create("render_job", {})
            return p, job["id"]
        result = run_operation(self.c, work)
        undone = undo_operation(self.c, result["operation_id"])
        self.assertTrue(undone["ok"], undone)
        self.assertIsNone(self.row("project", result["data"][0]))
        redone = undo_operation(self.c, undone["operation_id"])
        self.assertTrue(redone["ok"], redone)
        self.assertEqual(self.row("project", result["data"][0])["max_id"], 3)
        self.assertEqual(self.create(project_id=result["data"][0])["id"], 4)

    def test_top_level_undo_preserves_other_fields_and_json_conflicts_are_whole_field(self):
        note = self.create(data={"data": {"a": True, "b": 1}})["id"]
        changed = dispatch(self.c, {"action": "update", "kind": "review_note", "project_id": self.p, "id": note, "data": {"data": {"a": 1, "b": 1}}})
        dispatch(self.c, {"action": "update", "kind": "review_note", "project_id": self.p, "id": note, "data": {"name": "later"}})
        undone = undo_operation(self.c, changed["operation_id"])
        self.assertTrue(undone["ok"], undone)
        self.assertIs(self.row("review_note", note)["data"]["a"], True)
        self.assertEqual(self.row("review_note", note)["name"], "later")
        dispatch(self.c, {"action": "update", "kind": "review_note", "project_id": self.p, "id": note, "data": {"data": {"a": True, "b": 2}}})
        before = self.snapshot()
        conflict = undo_operation(self.c, undone["operation_id"])
        self.assertEqual(conflict["error"]["code"], "undo_conflict")
        self.assertEqual(self.snapshot(), before)

    def test_later_tool_reference_blocks_core_undo_and_delete(self):
        layer = self.create("layer", {"type": "text", "config_ref": "layers/text.toml"})
        note = self.create(data={"layer_id": layer["id"]})
        before = self.snapshot()
        failed = undo_operation(self.c, layer["operation_id"])
        self.assertEqual(failed["error"]["code"], "undo_conflict")
        self.assertEqual(failed["error"]["conflicts"][0]["related"][0]["kind"], "review_note")
        delete = dispatch(self.c, {"action": "delete", "kind": "layer", "project_id": self.p, "id": layer["id"]})
        self.assertEqual(delete["error"]["reference"]["id"], note["id"])
        self.assertEqual(delete["error"]["reference"]["kind"], "review_note")
        self.assertEqual(self.snapshot(), before)

    def test_deferred_failure_identifies_custom_table_before_rollback(self):
        before = self.snapshot()
        def work(write):
            write.defer_references()
            return write.create("review_note", {"layer_id": 999}, project_id=self.p)
        result = run_operation(self.c, work)
        self.assertFalse(result["ok"])
        issue = result["error"]["violations"][0]
        self.assertEqual(issue["target"]["kind"], "review_note")
        self.assertEqual(issue["field"], "layer_id")
        self.assertEqual(issue["reference"], {"kind": "layer", "project_id": self.p, "id": 999})
        self.assertEqual(before, self.snapshot())

    def test_custom_reference_can_cross_project_and_target_global_table(self):
        register_tables(self.c, {"review_link": {"fields": {"owner_project": "INTEGER", "note_id": "INTEGER", "job_id": "INTEGER"},
                        "references": [{"fields": ["owner_project", "note_id"], "kind": "review_note"}, {"fields": ["job_id"], "kind": "render_job"}]}})
        note, job = self.create(), self.create("render_job")
        link = self.create("review_link", {"owner_project": self.p, "note_id": note["id"], "job_id": job["id"]}, project_id=self.q)
        self.assertTrue(link["ok"], link)
        for original in (note, job):
            failed = undo_operation(self.c, original["operation_id"])
            self.assertEqual(failed["error"]["code"], "undo_conflict")
        undone_link = undo_operation(self.c, link["operation_id"])
        self.assertTrue(undone_link["ok"], undone_link)
        self.assertTrue(undo_operation(self.c, note["operation_id"])["ok"])
        failed_restore = undo_operation(self.c, undone_link["operation_id"])
        self.assertFalse(failed_restore["ok"])
        self.assertEqual(failed_restore["error"]["conflicts"][0]["code"], "undo_dependency")

    def test_batch_declarations_support_mutual_references_without_layer_cycle_rules(self):
        register_tables(self.c, {"left_item": {"fields": {"peer": "INTEGER"}, "references": [{"fields": ["project_id", "peer"], "kind": "right_item"}]},
                                "right_item": {"fields": {"peer": "INTEGER"}, "references": [{"fields": ["project_id", "peer"], "kind": "left_item"}]}})
        def work(write):
            write.defer_references()
            a = write.create("left_item", {"peer": 2}, project_id=self.p)
            return a, write.create("right_item", {"peer": a["id"]}, project_id=self.p)
        made = run_operation(self.c, work)
        self.assertTrue(made["ok"], made)
        undone = undo_operation(self.c, made["operation_id"])
        self.assertTrue(undone["ok"], undone)
        self.assertTrue(undo_operation(self.c, undone["operation_id"])["ok"])

    def test_declaration_persists_without_leaking_to_other_databases(self):
        self.create(data={"name": "kept"})
        initialize_database(self.path)
        with closing(open_database(self.path)) as other:
            self.assertEqual(read_record(other, "review_note", project_id=self.p)[0]["name"], "kept")
            changed = run_operation(other, lambda w: w.update("review_note", 1, {"name": "reopened"}, project_id=self.p))
            self.assertTrue(changed["ok"], changed)
        second_path = initialize_database(self.path.parent / "separate.sqlite3")
        other = open_database(second_path)
        try:
            self.assertNotIn("review_note", table_specs(other))
            with self.assertRaisesRegex(ValueError, "未知 kind"):
                read_record(other, "review_note", project_id=self.p)
        finally:
            other.close()

    def test_registration_is_idempotent_and_only_adds_fields(self):
        before = self.snapshot()
        register_tables(self.c, TABLES)
        self.assertEqual(before, self.snapshot())
        changed = deepcopy(TABLES)
        changed["review_note"]["fields"]["name"]["type"] = "INTEGER"
        changed["review_note"]["fields"]["name"]["default"] = 0
        with self.assertRaisesRegex(ValueError, "已有列"):
            register_tables(self.c, changed)
        self.assertEqual(before, self.snapshot())

    def test_add_columns_preserves_rows_and_old_undo_snapshots(self):
        made = self.create(data={"name": "before"})
        changed = deepcopy(TABLES)
        changed["review_note"]["fields"].update({"options": {"type": "JSON", "default": {"enabled": True}}, "weight": {"type": "REAL", "default": 1}})
        register_tables(self.c, changed)
        self.assertEqual(self.row("review_note", made["id"])["options"], {"enabled": True})
        undone = undo_operation(self.c, made["operation_id"])
        self.assertTrue(undone["ok"], undone)
        self.assertTrue(undo_operation(self.c, undone["operation_id"])["ok"])
        self.assertEqual(self.row("review_note", made["id"])["weight"], 1.0)
        original = read_history(self.c, operation_id=made["operation_id"])["items"][0]["changes"][0]["after"]
        self.assertNotIn("options", original)

    def test_migration_rolls_back_new_table_when_later_addition_fails(self):
        before = self.snapshot()
        changed = deepcopy(TABLES["review_note"])
        changed["fields"]["required"] = {"type": "TEXT", "nullable": False}
        with self.assertRaises(ValueError):
            register_tables(self.c, {"new_item": {"fields": {}}, "review_note": changed})
        self.assertEqual(before, self.snapshot())

    def test_invalid_names_builtins_and_unmanaged_tables_are_not_overwritten(self):
        for kind, spec in (("object", {"fields": {}}), ("bad-name", {"fields": {}}), ("custom", {"table": "objects", "fields": {}}),
                           ("custom", {"fields": {"id": "INTEGER"}}), ("custom", {"fields": {"x": {"type": "BLOB"}}})):
            with self.subTest(kind=kind, spec=spec), self.assertRaises(ValueError):
                register_tables(self.c, {kind: spec})
        self.c.execute("CREATE TABLE tool_unmanaged (id INTEGER PRIMARY KEY)")
        self.c.commit()
        with self.assertRaisesRegex(ValueError, "未登记"):
            register_tables(self.c, {"unmanaged": {"fields": {}}})

    def test_registration_preserves_callers_pending_transaction(self):
        self.c.execute("BEGIN")
        with self.assertRaisesRegex(ValueError, "待提交"):
            register_tables(self.c, TABLES)
        self.assertTrue(self.c.in_transaction)
        self.c.rollback()

    def test_project_restore_keeps_high_water_for_deleted_custom_records(self):
        made = self.create()
        self.assertTrue(undo_operation(self.c, made["operation_id"])["ok"])
        deleted = dispatch(self.c, {"action": "delete", "kind": "project", "id": self.p})
        self.assertTrue(undo_operation(self.c, deleted["operation_id"])["ok"])
        self.assertGreater(self.create()["id"], made["id"])

    def test_same_project_identity_cannot_be_restored_into_another_managed_kind(self):
        made = self.create()
        record = {"id": made["id"], "project_id": self.p, "name": "", "type": "text", "config_ref": "layers/text.toml", "father": None, "axis": None, "tips": ""}
        result = run_operation(self.c, lambda w: w.restore("layer", made["id"], record, project_id=self.p))
        self.assertFalse(result["ok"])
        self.assertIn("review_note", result["error"]["message"])

    def test_cli_dispatch_and_history_need_no_tool_registration_code(self):
        note = self.create()
        def cli(module, *args, input=None):
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", module, str(self.path), *args],
                                    input=input, capture_output=True, text=True, encoding="utf-8", cwd=self.path.parent, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            return json.loads(result.stdout)
        read = cli("layerweave.tool.builtin.usage.records.cli", input=json.dumps({"action": "read", "kind": "review_note", "project_id": self.p, "id": note["id"]}))
        self.assertEqual(read["data"]["id"], note["id"])
        history = cli("layerweave.tool.builtin.usage.history.cli", "--kind", "review_note", "--project-id", str(self.p), "--json")
        self.assertEqual(history["change_count"], 1)

    def test_reserved_object_field_names_do_not_add_object_semantics(self):
        register_tables(self.c, {"free_record": {"fields": {"begin": "REAL", "axis": {"type": "JSON", "nullable": False}}}})
        made = self.create("free_record", {"begin": 0.123456789, "axis": None})
        self.assertTrue(made["ok"], made)
        self.assertEqual(made["data"]["begin"], 0.123456789)
        self.assertIsNone(made["data"]["axis"])
        undone = undo_operation(self.c, made["operation_id"])
        self.assertTrue(undo_operation(self.c, undone["operation_id"])["ok"])

    def test_undo_releases_replaced_identity_before_restoring_old_kind(self):
        note = self.create()["data"]
        layer = {"id": note["id"], "project_id": self.p, "name": "", "type": "text", "config_ref": "layers/text.toml", "father": None, "axis": None, "tips": ""}
        def work(write):
            write.delete("review_note", note["id"], project_id=self.p)
            return write.restore("layer", note["id"], layer, project_id=self.p)
        replaced = run_operation(self.c, work)
        self.assertTrue(replaced["ok"], replaced)
        undone = undo_operation(self.c, replaced["operation_id"])
        self.assertTrue(undone["ok"], undone)
        self.assertEqual(self.row("review_note", note["id"]), note)
        self.assertIsNone(self.row("layer", note["id"]))


if __name__ == "__main__":
    unittest.main()

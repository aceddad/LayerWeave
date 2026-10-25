"""BLOB 贯穿写入/JSON/日志/恢复，退出托管保留数据与历史；只用临时数据库。"""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from layerweave.support.api import (initialize_database, open_database, register_tables, unregister_tables,
    retired_tables, table_specs, transaction, run_operation, read_record, read_changes, numbering_entries,
    register_numbering, allocate)
from layerweave.support.serialization import binary_json_default
from layerweave.support.storage.retirement import RETIRED_CATALOG
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.tool.builtin.usage.history.service import read_history
from layerweave.tool.builtin.usage.history.cli import format_history
from layerweave.tool.builtin.usage.undo.service import undo_operation
from layerweave.tool.builtin.usage.undo.cli import format_undo
from layerweave.tool.builtin.usage.exchange.exporting import export_project
from layerweave.tool.builtin.usage.exchange.importing import import_project
from layerweave.tool.builtin.usage.exchange.files import save_document, load_document


class BinaryRetirementTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="layerweave-binary-retirement-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = initialize_database(self.root / "project.sqlite3")
        self.c = open_database(self.path)
        self.addCleanup(self.c.close)
        self.definition = {"fields": {"payload": "BLOB", "label": "TEXT", "data": "JSON"}}
        register_tables(self.c, {"binary_cache": self.definition})
        with transaction(self.c) as write:
            self.p = write.create("project", {"name": "binary"})["id"]

    def create(self, value=b"\x00\x01\xff", **fields):
        return run_operation(self.c, lambda write: write.create("binary_cache", {"payload": value, **fields}, project_id=self.p))

    def update(self, id, data):
        return run_operation(self.c, lambda write: write.update("binary_cache", id, data, project_id=self.p))

    def row(self, id):
        return read_record(self.c, "binary_cache", project_id=self.p, id=id)

    def test_binary_types_null_empty_and_storage(self):
        for value in (b"\x00\xff", bytearray(b"\x80"), memoryview(b"ab"), b"", None):
            with self.subTest(value=value):
                result = self.create(value)
                self.assertTrue(result["ok"], result)
                row = result["data"]
                self.assertEqual(row["payload"], None if value is None else bytes(value))
                self.assertIs(type(row["payload"]), type(None) if value is None else bytes)
                stored = self.c.execute("SELECT typeof(payload) FROM tool_binary_cache WHERE id=?", (row["id"],)).fetchone()[0]
                self.assertEqual(stored, "null" if value is None else "blob")

    def test_raw_writes_reject_strings_other_types_and_rollback(self):
        for value in ("AAH/", 4, [], {}, True):
            with self.subTest(value=value):
                result = self.create(value)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], "blob_type")
        self.assertEqual(read_record(self.c, "binary_cache", project_id=self.p), [])
        self.assertEqual(read_record(self.c, "project", id=self.p)["max_id"], 0)
        made = self.create()["data"]
        self.assertFalse(self.update(made["id"], {"payload": "AAH/"})["ok"])
        result = run_operation(self.c, lambda write: write.restore("binary_cache", made["id"],
            {**made, "payload": "AAH/"}, project_id=self.p))
        self.assertEqual(result["error"]["code"], "blob_type")
        self.assertEqual(self.row(made["id"])["payload"], b"\x00\x01\xff")

    def test_defaults_required_columns_and_append_nullable(self):
        for default in (b"", b"x", "", 0):
            with self.subTest(default=default), self.assertRaisesRegex(ValueError, "BLOB 默认值"):
                register_tables(self.c, {"bad": {"fields": {"v": {"type": "BLOB", "default": default}}}})
        with self.assertRaisesRegex(ValueError, "非空列"):
            register_tables(self.c, {"bad": {"fields": {"v": {"type": "BLOB", "nullable": False, "default": None}}}})
        register_tables(self.c, {"required": {"fields": {"v": {"type": "BLOB", "nullable": False}}}})
        failed = run_operation(self.c, lambda w: w.create("required", {}, project_id=self.p))
        self.assertEqual(failed["error"]["code"], "null_field")
        with transaction(self.c) as w:
            self.assertEqual(w.create("required", {"v": b""}, project_id=self.p)["v"], b"")
        made = self.create()
        spec = deepcopy(self.definition)
        spec["fields"]["later"] = {"type": "BLOB", "default": None}
        register_tables(self.c, {"binary_cache": spec})
        self.assertIsNone(self.row(made["data"]["id"])["later"])
        old = read_history(self.c, operation_id=made["operation_id"])["items"][0]["changes"][0]["after"]
        self.assertNotIn("later", old)
        undone = undo_operation(self.c, made["operation_id"])
        self.assertTrue(undone["ok"], undone)
        redone = undo_operation(self.c, undone["operation_id"])
        self.assertTrue(redone["ok"], redone)
        self.assertIsNone(self.row(made["data"]["id"])["later"])

    def test_same_bytes_no_change_and_field_undo_redo(self):
        made = self.create(label="old")
        id = made["data"]["id"]
        same = self.update(id, {"payload": memoryview(b"\x00\x01\xff")})
        self.assertTrue(same["ok"], same)
        self.assertFalse(same["applied"])
        changed = self.update(id, {"payload": b"new"})
        self.update(id, {"label": "keep"})
        undone = undo_operation(self.c, changed["operation_id"])
        self.assertTrue(undone["ok"], undone)
        self.assertEqual(self.row(id)["payload"], b"\x00\x01\xff")
        self.assertEqual(self.row(id)["label"], "keep")
        self.assertTrue(undo_operation(self.c, undone["operation_id"])["ok"])
        self.assertEqual(self.row(id)["payload"], b"new")
        self.update(id, {"payload": b"later"})
        failed = undo_operation(self.c, changed["operation_id"])
        self.assertEqual(failed["error"]["code"], "undo_conflict")
        json.dumps(failed, default=binary_json_default)
        self.assertIn("冲突", format_undo(failed))

    def test_journal_feed_history_preserve_binary_and_plain_json(self):
        ordinary = {"payload": "AAH/", "_layerweave_binary": {"data": "AAH/"}}
        made = self.create(label="AAH/", data=ordinary)
        stored = self.c.execute("SELECT after_data FROM changes WHERE operation_id=?", (made["operation_id"],)).fetchone()[0]
        self.assertEqual(json.loads(stored)["payload"], "AAH/")
        for row in (read_record(self.c, "change", filters={"operation_id": made["operation_id"]})[0],
                    read_changes(self.c)["changes"][-1]):
            self.assertEqual(row["after_data"]["payload"], b"\x00\x01\xff")
            self.assertEqual(row["after_data"]["label"], "AAH/")
            self.assertEqual(row["after_data"]["data"], ordinary)
        history = read_history(self.c, operation_id=made["operation_id"])
        self.assertIn("AAH/", format_history(history))
        # Arbitrary binary inside JSON remains unsupported.
        self.assertFalse(self.create(data={"nested": b"x"})["ok"])

    def test_dispatch_json_input_invalid_base64_and_filters(self):
        request = {"action": "create", "kind": "binary_cache", "project_id": self.p,
                   "data": {"payload": "AAH/", "label": "AAH/"}}
        made = dispatch(self.c, request)
        self.assertTrue(made["ok"], made)
        self.assertEqual(made["data"]["payload"], b"\x00\x01\xff")
        for invalid in ("!bad", "中文", "a"):
            result = dispatch(self.c, {**request, "data": {"payload": invalid}})
            self.assertEqual(result["error"]["code"], "blob_base64")
        for value in ("AAH/", b"\x00\x01\xff", None):
            failed = dispatch(self.c, {"action": "read", "kind": "binary_cache", "project_id": self.p,
                                       "filters": {"payload": value}})
            self.assertEqual(failed["error"]["code"], "unknown_filter")
            self.assertNotIn("payload", failed["error"]["allowed"])
        self.assertEqual(len(read_record(self.c, "binary_cache", project_id=self.p, filters={"label": "AAH/"})), 1)

    def test_json_exchange_file_copy_and_baseline(self):
        made = self.create()
        document = export_project(self.c, self.p, include_baseline=True)
        self.assertEqual(document["records"][0]["data"]["payload"], "AAH/")
        path = self.root / "exchange.json"
        save_document(document, path)
        self.assertEqual(load_document(path), document)
        unchanged = import_project(self.c, document)
        self.assertTrue(unchanged["ok"], unchanged)
        self.assertFalse(unchanged["applied"])
        document["records"][0]["data"]["payload"] = "eA=="
        changed = import_project(self.c, document)
        self.assertTrue(changed["ok"], changed)
        self.assertEqual(self.row(made["data"]["id"])["payload"], b"x")
        stale = import_project(self.c, document)
        self.assertEqual(stale["data"]["issues"][0]["code"], "source_changed")
        copy = export_project(self.c, self.p, op="add")
        target = open_database(initialize_database(self.root / "copy.sqlite3"))
        self.addCleanup(target.close)
        copied = import_project(target, json.loads(json.dumps(copy)), new_project=True)
        self.assertTrue(copied["ok"], copied)
        rows = read_record(target, "binary_cache", project_id=copied["data"]["project_id"])
        self.assertEqual(rows[0]["payload"], b"x")

    def test_retirement_keeps_data_history_and_numbering(self):
        made = self.create()
        before = self.c.execute("SELECT COUNT(*) FROM changes").fetchone()[0]
        high = read_record(self.c, "project", id=self.p)["max_id"]
        result = unregister_tables(self.c, ["binary_cache"])
        self.assertEqual(result["retired"][0]["table"], "tool_binary_cache")
        self.assertNotIn("binary_cache", table_specs(self.c))
        self.assertEqual(self.c.execute("SELECT payload FROM tool_binary_cache").fetchone()[0], b"\x00\x01\xff")
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM changes").fetchone()[0], before)
        self.assertNotIn("binary_cache", numbering_entries(self.c)["project_entities"]["members"])
        self.assertEqual(read_record(self.c, "project", id=self.p)["max_id"], high)
        with transaction(self.c):
            next_id = allocate("project_entities", data={"project_id": self.p})["id"]
        self.assertGreater(next_id, high)
        for action in ("read", "create", "update", "delete"):
            request = {"action": action, "kind": "binary_cache", "project_id": self.p}
            if action in {"update", "delete"}:
                request["id"] = made["data"]["id"]
            if action in {"update", "create"}:
                request["data"] = {"payload": "AAH/"}
            self.assertEqual(dispatch(self.c, request)["error"]["code"], "retired_kind")
        history = read_history(self.c, self.p, kind="binary_cache", id=made["data"]["id"], detail=True)
        self.assertEqual(history["items"][0]["changes"][0]["after"]["payload"], b"\x00\x01\xff")
        self.assertEqual(read_changes(self.c)["changes"][-1]["after_data"]["payload"], b"\x00\x01\xff")
        self.assertEqual(export_project(self.c, self.p)["records"], [])

    def test_external_drop_restart_history_and_kind_reservation(self):
        made = self.create()
        unregister_tables(self.c, ["binary_cache"])
        self.c.execute("DROP TABLE tool_binary_cache")  # External owner controls physical deletion.
        self.c.commit()
        reopened = open_database(self.path)
        self.addCleanup(reopened.close)
        old = read_history(reopened, operation_id=made["operation_id"])
        self.assertEqual(old["items"][0]["changes"][0]["after"]["payload"], b"\x00\x01\xff")
        with self.assertRaisesRegex(ValueError, "不能复用"):
            register_tables(reopened, {"binary_cache": self.definition})
        replacement = {**self.definition, "table": "tool_binary_cache"}
        register_tables(reopened, {"new_cache": replacement})
        self.assertIn("new_cache", table_specs(reopened))
        self.assertIn("binary_cache", retired_tables(reopened))
        self.assertEqual(read_history(reopened, kind="binary_cache")["operation_count"], 1)

    def test_existing_unmanaged_physical_table_not_adopted(self):
        unregister_tables(self.c, ["binary_cache"])
        with self.assertRaisesRegex(ValueError, "未登记"):
            register_tables(self.c, {"new_cache": {**self.definition, "table": "tool_binary_cache"}})

    def test_reused_physical_name_reports_latest_retired_kind(self):
        unregister_tables(self.c, ["binary_cache"])
        self.c.execute("DROP TABLE tool_binary_cache")
        self.c.commit()
        register_tables(self.c, {"aaa_new": {**self.definition, "table": "tool_binary_cache"}})
        with transaction(self.c) as write:
            write.create("aaa_new", {"payload": b"x"}, project_id=self.p)
        unregister_tables(self.c, ["aaa_new"])
        failed = run_operation(self.c, lambda w: w.delete("project", self.p))
        self.assertEqual(failed["error"]["reference"]["kind"], "aaa_new")

    def test_batch_dependencies_and_atomic_archive(self):
        for logical in (False, True):
            kind = "logical_child" if logical else "hard_child"
            register_tables(self.c, {kind: {"fields": {"ref": "INTEGER"},
                "logical_references" if logical else "references": [{"fields": ["project_id", "ref"], "kind": "binary_cache"}]}})
        before = list(self.c.iterdump())
        with self.assertRaisesRegex(ValueError, "依赖"):
            unregister_tables(self.c, ["binary_cache"])
        self.assertEqual(list(self.c.iterdump()), before)
        with patch("layerweave.support.numbering.registry.persist_entries", side_effect=RuntimeError("rollback")):
            with self.assertRaisesRegex(RuntimeError, "rollback"):
                unregister_tables(self.c, ["binary_cache", "hard_child", "logical_child"])
        self.assertEqual(list(self.c.iterdump()), before)
        retired = unregister_tables(self.c, ["binary_cache", "hard_child", "logical_child"])
        self.assertEqual(len(retired["retired"]), 3)
        again = unregister_tables(self.c, ["binary_cache", "never_registered", "binary_cache"])
        self.assertEqual(again["already_retired"], ["binary_cache"])
        self.assertEqual(again["not_registered"], ["never_registered"])
        self.assertFalse(again["retired"])

    def test_counter_source_dependency_and_empty_rule_retained(self):
        register_tables(self.c, {"counter_source": {"scoped": False, "fields": {"high": {"type": "INTEGER", "default": 0}}},
                                "member": {"scoped": False, "fields": {}}})
        register_numbering(self.c, {"custom": {"rule": "project_entity", "counter": {
            "kind": "counter_source", "field": "high", "key": {"id": 1}}, "members": ["member"]}})
        with self.assertRaisesRegex(ValueError, "计数来源"):
            unregister_tables(self.c, ["counter_source", "member"])
        unregister_tables(self.c, ["member"])
        self.assertEqual(numbering_entries(self.c)["custom"]["members"], [])
        with self.assertRaisesRegex(ValueError, "计数来源"):
            unregister_tables(self.c, ["counter_source"])

    def test_mixed_undo_rejected_even_with_cancelled_retired_changes(self):
        def operation(write):
            write.update("project", self.p, {"tips": "preserve"})
            made = write.create("binary_cache", {"payload": b"x"}, project_id=self.p)
            write.delete("binary_cache", made["id"], project_id=self.p)
        made = run_operation(self.c, operation)
        unregister_tables(self.c, ["binary_cache"])
        before = list(self.c.iterdump())
        failed = undo_operation(self.c, made["operation_id"])
        self.assertEqual(failed["error"]["code"], "retired_kind")
        self.assertEqual(list(self.c.iterdump()), before)
        # Unrelated project operations still work, including undo.
        other = run_operation(self.c, lambda w: w.update("project", self.p, {"name": "new"}))
        self.assertTrue(undo_operation(self.c, other["operation_id"])["ok"])

    def test_old_database_read_only_catalog_and_builtin_rejection(self):
        self.assertFalse(retired_tables(self.c))
        self.assertIsNone(self.c.execute("SELECT name FROM sqlite_master WHERE name=?", (RETIRED_CATALOG,)).fetchone())
        for kind in ("project", "layer", "object", "bind", "change"):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "内置"):
                unregister_tables(self.c, ["binary_cache", kind])
        self.assertIn("binary_cache", table_specs(self.c))
        self.c.execute("BEGIN")
        with self.assertRaisesRegex(ValueError, "待提交"):
            unregister_tables(self.c, ["binary_cache"])
        self.assertTrue(self.c.in_transaction)
        self.c.rollback()

    def test_retired_foreign_key_explained_immediate_deferred_and_restoration(self):
        self.create()
        unregister_tables(self.c, ["binary_cache"])
        for deferred in (False, True):
            def delete(write):
                if deferred:
                    write.defer_references()
                write.delete("project", self.p)
            result = run_operation(self.c, delete)
            self.assertFalse(result["ok"])
            self.assertIn("已退出托管", result["error"]["message"])
            self.assertIn("tool_binary_cache", result["error"]["message"])
            self.assertIsNotNone(read_record(self.c, "project", id=self.p))
        restored = run_operation(self.c, lambda w: w.restore("project", self.p, None))
        self.assertIn("已退出托管", restored["error"]["message"])
        # Keeping the table but removing its FK is an external operation.
        self.c.executescript("CREATE TABLE replacement (project_id INTEGER, id INTEGER, payload BLOB); "
            "INSERT INTO replacement SELECT project_id,id,payload FROM tool_binary_cache; "
            "DROP TABLE tool_binary_cache; ALTER TABLE replacement RENAME TO tool_binary_cache;")
        result = run_operation(self.c, lambda w: w.delete("project", self.p))
        self.assertTrue(result["ok"], result)

    def test_retired_hard_references_to_layer_and_object(self):
        register_tables(self.c, {
            "layer_notes": {"fields": {"owner": "INTEGER"},
                "references": [{"fields": ["project_id", "owner"], "kind": "layer"}]},
            "object_notes": {"fields": {"owner": "INTEGER"},
                "references": [{"fields": ["project_id", "owner"], "kind": "object"}]}})
        with transaction(self.c) as w:
            empty_layer = w.create("layer", {"type": "text", "config_ref": "layers/text.toml"}, project_id=self.p)
            layer = w.create("layer", {"type": "text", "config_ref": "layers/text.toml"}, project_id=self.p)
            obj = w.create("object", {"layer": layer["id"], "config_ref": "objects/text.toml"}, project_id=self.p)
            w.create("layer_notes", {"owner": empty_layer["id"]}, project_id=self.p)
            w.create("object_notes", {"owner": obj["id"]}, project_id=self.p)
        unregister_tables(self.c, ["layer_notes", "object_notes"])
        for kind, id, note_kind in (("layer", empty_layer["id"], "layer_notes"), ("object", obj["id"], "object_notes")):
            result = run_operation(self.c, lambda w: w.delete(kind, id, project_id=self.p))
            self.assertIn("已退出托管", result["error"]["message"])
            self.assertEqual(result["error"]["reference"]["kind"], note_kind)

    def test_successful_core_write_does_not_scan_retired_references(self):
        self.create()
        unregister_tables(self.c, ["binary_cache"])
        statements = []
        self.c.set_trace_callback(statements.append)
        try:
            result = run_operation(self.c, lambda w: w.update("project", self.p, {"tips": "ok"}))
        finally:
            self.c.set_trace_callback(None)
        self.assertTrue(result["ok"], result)
        self.assertFalse(any("foreign_key" in sql.lower() or RETIRED_CATALOG in sql for sql in statements))

    def test_external_schema_change_does_not_change_history_decoding(self):
        made = self.create()
        unregister_tables(self.c, ["binary_cache"])
        self.c.executescript("DROP TABLE tool_binary_cache; CREATE TABLE tool_binary_cache (payload TEXT);")
        history = read_history(self.c, operation_id=made["operation_id"])
        self.assertEqual(history["items"][0]["changes"][0]["after"]["payload"], b"\x00\x01\xff")

    def test_invalid_base64_batch_rolls_back_prior_valid_writes(self):
        result = dispatch(self.c, [
            {"action": "update", "kind": "project", "id": self.p, "data": {"name": "rollback"}},
            {"action": "create", "kind": "binary_cache", "project_id": self.p, "data": {"payload": "???"}}])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["request_index"], 1)
        self.assertEqual(read_record(self.c, "project", id=self.p)["name"], "binary")

    def test_project_restore_after_external_cleanup_preserves_counter(self):
        made = self.create()["data"]
        unregister_tables(self.c, ["binary_cache"])
        self.c.execute("DROP TABLE tool_binary_cache")
        self.c.commit()
        deleted = run_operation(self.c, lambda w: w.delete("project", self.p))
        self.assertTrue(deleted["ok"], deleted)
        self.assertTrue(undo_operation(self.c, deleted["operation_id"])["ok"])
        with transaction(self.c):
            new_id = allocate("project_entities", data={"project_id": self.p})["id"]
        self.assertGreater(new_id, made["id"])

    def test_retired_schema_cannot_be_reimported(self):
        self.create()
        document = export_project(self.c, self.p)
        unregister_tables(self.c, ["binary_cache"])
        result = import_project(self.c, document)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "retired_kind")

    def test_cli_input_output_history_and_conflicts(self):
        request = self.root / "request.json"
        request.write_text(json.dumps({"action": "create", "kind": "binary_cache", "project_id": self.p,
                                      "data": {"payload": "AAH/"}}), encoding="utf-8")
        def call(module, *args):
            return subprocess.run([sys.executable, "-B", "-X", "utf8", "-m", module, str(self.path), *args],
                                  capture_output=True, text=True, encoding="utf-8", timeout=30)
        made = call("layerweave.tool.builtin.usage.records.cli", "--request", str(request))
        self.assertEqual(made.returncode, 0, made.stderr)
        result = json.loads(made.stdout)
        self.assertEqual(result["data"]["payload"], "AAH/")
        history = call("layerweave.tool.builtin.usage.history.cli", "--operation-id", result["operation_id"])
        self.assertEqual(history.returncode, 0, history.stderr)
        self.assertIn("AAH/", history.stdout)
        changed = self.update(result["id"], {"payload": b"new"})
        self.update(result["id"], {"payload": b"later"})
        conflict = call("layerweave.tool.builtin.usage.undo.cli", changed["operation_id"])
        self.assertNotEqual(conflict.returncode, 0)
        self.assertIn("冲突", conflict.stdout)


if __name__ == "__main__":
    unittest.main()

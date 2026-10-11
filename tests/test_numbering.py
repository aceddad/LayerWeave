"""自定义 ID、可登记发号规则、簇范围及恢复；只操作临时数据库。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import tempfile
from threading import Barrier
import unittest

from layerweave.support.api import (allocate, increment, initialize_database, open_database, read_record,
    register_numbering, register_numbering_rule, numbering_entries, register_tables, run_operation, transaction)
from layerweave.support.numbering.service import RULES
from layerweave.support.numbering.registry import CATALOG
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.tool.builtin.usage.undo.service import undo_operation
from layerweave.tool.builtin.usage.history.service import read_history


class NumberingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="layerweave-numbering-")
        self.addCleanup(temporary.cleanup)
        self.path = initialize_database(Path(temporary.name) / "data.sqlite3")
        self.c = open_database(self.path)
        self.addCleanup(self.c.close)
        with transaction(self.c) as w:
            self.p = w.create("project", {"name": "first"})["id"]
            self.q = w.create("project", {"name": "second"})["id"]

    def layer(self):
        return self.ok(run_operation(self.c, lambda w: w.create("layer", {
            "type": "text", "config_ref": "layers/text.toml"}, project_id=self.p)))["data"]

    def ok(self, result):
        self.assertTrue(result["ok"], result)
        return result

    def view_table(self, reference=False):
        definition = {"id_source": "provided", "fields": {"collapsed": {"type": "INTEGER", "default": 0},
                                                         "data": {"type": "JSON", "default": {}}}}
        if reference:
            definition["references"] = [{"fields": ["project_id", "id"], "kind": "layer"}]
        register_tables(self.c, {"view_state": definition})

    def make(self, kind, data, project_id=None):
        return self.ok(run_operation(self.c, lambda w: w.create(kind, data, project_id=project_id)))

    def custom_cluster(self, *, provided=False, scoped=True, name="jobs", rule=None):
        register_tables(self.c, {
            "counter_state": {"scoped": False, "id_source": "provided", "fields": {
                "max_num": {"type": "INTEGER", "default": 0}, "other_max": {"type": "INTEGER", "default": 0},
                "name": {"type": "TEXT", "default": "initial"}}},
            "job_a": {"scoped": scoped, "id_source": "provided" if provided else "auto", "fields": {"body": "TEXT"}},
            "job_b": {"scoped": scoped, "id_source": "provided" if provided else "auto", "fields": {"body": "TEXT"}},
        })
        self.make("counter_state", {"id": self.p})
        self.make("counter_state", {"id": self.q})
        definition = {"rule": rule or ("project_entity" if scoped else "number_only"),
                      "counter": {"kind": "counter_state", "field": "max_num", "key": {"id": "project_id" if scoped else self.p}},
                      "members": ["job_a", "job_b"]}
        register_numbering(self.c, {name: definition})
        return definition

    def test_provided_view_reuses_layer_key_without_consuming_project_counter(self):
        self.view_table(reference=True)
        layer = self.layer()
        result = dispatch(self.c, {"action": "create", "kind": "view_state", "project_id": self.p,
                                  "data": {"id": layer["id"], "collapsed": 1}})
        self.ok(result)
        self.assertEqual(result["id"], layer["id"])
        self.assertEqual(read_record(self.c, "project", id=self.p)["max_id"], layer["id"])
        self.assertNotIn("view_state", numbering_entries(self.c)["project_entities"]["members"])
        self.assertEqual(read_record(self.c, "view_state", project_id=self.p, id=layer["id"])["collapsed"], 1)

    def test_provided_create_requires_positive_integer_and_still_enforces_own_primary_key(self):
        self.view_table()
        for value in (None, 0, -1, True, "8", 1.5):
            result = run_operation(self.c, lambda w: w.create("view_state", {"id": value}, project_id=self.p))
            self.assertFalse(result["ok"], value)
            self.assertEqual(result["error"]["code"], "provided_id")
        self.make("view_state", {"id": 8}, self.p)
        result = run_operation(self.c, lambda w: w.create("view_state", {"id": 8}, project_id=self.p))
        self.assertFalse(result["ok"])
        self.assertEqual(len(read_record(self.c, "view_state", project_id=self.p)), 1)

    def test_global_provided_id_supports_read_update_delete_history_and_undo(self):
        register_tables(self.c, {"external_item": {"scoped": False, "id_source": "provided", "fields": {"body": "TEXT"}}})
        made = self.make("external_item", {"id": 42, "body": "one"})
        self.ok(run_operation(self.c, lambda w: w.update("external_item", 42, {"body": "two"})))
        deleted = self.ok(run_operation(self.c, lambda w: w.delete("external_item", 42)))
        self.assertIsNone(read_record(self.c, "external_item", id=42))
        self.ok(undo_operation(self.c, deleted["operation_id"]))
        self.assertEqual(read_record(self.c, "external_item", id=42)["body"], "two")
        self.assertEqual(read_history(self.c, kind="external_item", id=42)["operation_count"], 4)
        self.assertEqual(made["data"]["id"], 42)

    def test_view_restore_and_redo_ignore_other_table_with_same_id(self):
        self.view_table(reference=True)
        layer = self.layer()
        made = self.make("view_state", {"id": layer["id"]}, self.p)
        undone = self.ok(undo_operation(self.c, made["operation_id"]))
        self.ok(undo_operation(self.c, undone["operation_id"]))
        self.assertIsNotNone(read_record(self.c, "layer", project_id=self.p, id=layer["id"]))
        self.assertEqual(read_record(self.c, "view_state", project_id=self.p, id=layer["id"])["id"], layer["id"])

    def test_custom_id_does_not_raise_project_high_water_when_project_is_restored(self):
        self.view_table()
        self.make("view_state", {"id": 5000}, self.p)
        deleted = self.ok(run_operation(self.c, lambda w: (w.delete("view_state", 5000, project_id=self.p), w.delete("project", self.p))))
        self.ok(undo_operation(self.c, deleted["operation_id"]))
        self.assertEqual(read_record(self.c, "project", id=self.p)["max_id"], 0)
        self.assertEqual(self.layer()["id"], 1)

    def test_thin_allocate_has_implicit_connection_and_does_not_create_business_rows(self):
        with transaction(self.c):
            self.assertEqual(allocate("project_entities", data={"project_id": self.p}), {"project_id": self.p, "id": 1})
        self.assertEqual(read_record(self.c, "layer", project_id=self.p), [])
        self.assertEqual(read_record(self.c, "object", project_id=self.p), [])
        self.assertEqual(self.layer()["id"], 2)
        self.assertIsNotNone(self.c.execute("SELECT name FROM sqlite_master WHERE name=?", (CATALOG,)).fetchone())
        with self.assertRaisesRegex(RuntimeError, "写会话"):
            allocate("project_entities", data={"project_id": self.p})

    def test_allocation_and_metadata_rollback_with_failed_business_operation(self):
        before = read_record(self.c, "project", id=self.p)
        logs = read_record(self.c, "change")
        def fail(w):
            allocate("project_entities", data={"project_id": self.p})
            raise RuntimeError("test rollback")
        result = run_operation(self.c, fail)
        self.assertFalse(result["ok"])
        self.assertEqual(read_record(self.c, "project", id=self.p), before)
        self.assertEqual(read_record(self.c, "change"), logs)
        self.assertIsNone(self.c.execute("SELECT name FROM sqlite_master WHERE name=?", (CATALOG,)).fetchone())

    def test_custom_cluster_uses_its_counter_and_is_independent_between_projects(self):
        self.custom_cluster()
        a = self.make("job_a", {}, self.p)["data"]
        b = self.make("job_b", {}, self.p)["data"]
        q = self.make("job_a", {}, self.q)["data"]
        self.assertEqual((a["id"], b["id"], q["id"]), (1, 2, 1))
        self.assertEqual(read_record(self.c, "project", id=self.p)["max_id"], 0)
        self.assertEqual(read_record(self.c, "counter_state", id=self.p)["max_num"], 2)
        self.assertEqual(self.layer()["id"], 1)

    def test_global_cluster_can_share_one_counter_across_two_global_tables(self):
        self.custom_cluster(scoped=False)
        self.assertEqual(self.make("job_a", {})["data"]["id"], 1)
        self.assertEqual(self.make("job_b", {})["data"]["id"], 2)

    def test_two_clusters_can_use_different_columns_of_the_same_counter_row(self):
        definition = self.custom_cluster()
        first = deepcopy(definition)
        first["members"] = ["job_a"]
        second = deepcopy(definition)
        second["counter"]["field"] = "other_max"
        second["members"] = ["job_b"]
        register_numbering(self.c, {"jobs": first, "other_jobs": second})
        self.assertEqual(self.make("job_a", {}, self.p)["data"]["id"], 1)
        self.assertEqual(self.make("job_b", {}, self.p)["data"]["id"], 1)

    def test_provided_member_can_write_a_preallocated_identity(self):
        self.custom_cluster(provided=True)
        with transaction(self.c) as w:
            identity = allocate("jobs", data={"project_id": self.p})
            row = w.create("job_a", {"id": identity["id"]}, project_id=identity["project_id"])
        self.assertEqual(row["id"], 1)
        self.assertEqual(read_record(self.c, "counter_state", id=self.p)["max_num"], 1)

    def test_same_cluster_conflict_rolls_back_but_final_state_allows_releasing_old_occupant(self):
        self.custom_cluster(provided=True)
        self.make("job_a", {"id": 8}, self.p)
        result = run_operation(self.c, lambda w: w.create("job_b", {"id": 8}, project_id=self.p))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "id_conflict")
        self.assertIsNone(read_record(self.c, "job_b", project_id=self.p, id=8))
        with transaction(self.c) as w:
            w.create("job_b", {"id": 8}, project_id=self.p)
            w.delete("job_a", 8, project_id=self.p)
        self.assertIsNotNone(read_record(self.c, "job_b", project_id=self.p, id=8))

    def test_restore_retains_id_and_advances_its_own_counter_only(self):
        self.custom_cluster()
        row = {"project_id": self.p, "id": 80, "body": "snapshot"}
        self.ok(run_operation(self.c, lambda w: w.restore("job_a", 80, row, project_id=self.p)))
        self.assertEqual(self.make("job_b", {}, self.p)["data"]["id"], 81)
        self.assertEqual(read_record(self.c, "project", id=self.p)["max_id"], 0)

    def test_undo_reports_later_same_cluster_occupant(self):
        self.custom_cluster(provided=True)
        self.make("job_a", {"id": 8}, self.p)
        deleted = self.ok(run_operation(self.c, lambda w: w.delete("job_a", 8, project_id=self.p)))
        self.make("job_b", {"id": 8}, self.p)
        result = undo_operation(self.c, deleted["operation_id"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["conflicts"][0]["code"], "undo_id_conflict")

    def test_counter_update_cannot_rewind_and_undo_ignores_later_allocation(self):
        self.custom_cluster()
        changed = self.ok(run_operation(self.c, lambda w: w.update("counter_state", self.p, {"name": "renamed"})))
        self.make("job_a", {}, self.p)
        self.ok(undo_operation(self.c, changed["operation_id"]))
        counter = read_record(self.c, "counter_state", id=self.p)
        self.assertEqual((counter["name"], counter["max_num"]), ("initial", 1))
        result = run_operation(self.c, lambda w: w.update("counter_state", self.p, {"max_num": 0}))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "counter_rewind")

    def test_restoring_an_old_counter_snapshot_keeps_deleted_members_high_water(self):
        self.custom_cluster()
        original = read_record(self.c, "counter_state", id=self.p)
        row = self.make("job_a", {}, self.p)["data"]
        with transaction(self.c) as w:
            w.delete("job_a", row["id"], project_id=self.p)
            w.delete("counter_state", self.p)
        self.ok(run_operation(self.c, lambda w: w.restore("counter_state", self.p, original)))
        self.assertEqual(read_record(self.c, "counter_state", id=self.p)["max_num"], 1)
        self.assertEqual(self.make("job_b", {}, self.p)["data"]["id"], 2)

    def test_counter_and_member_delete_undo_redo_share_one_operation(self):
        self.custom_cluster()
        row = self.make("job_a", {}, self.p)["data"]
        deleted = self.ok(run_operation(self.c, lambda w: (w.delete("job_a", row["id"], project_id=self.p),
                                                          w.delete("counter_state", self.p))))
        restored = self.ok(undo_operation(self.c, deleted["operation_id"]))
        self.assertIsNotNone(read_record(self.c, "job_a", project_id=self.p, id=row["id"]))
        self.assertEqual(read_record(self.c, "counter_state", id=self.p)["max_num"], row["id"])
        self.ok(undo_operation(self.c, restored["operation_id"]))

    def test_custom_function_is_dispatched_and_failure_rolls_back_counter(self):
        def custom(entry, data):
            return {"project_id": data["project_id"], "id": increment(entry, data)}
        register_numbering_rule("test_custom_rule", custom)
        self.addCleanup(RULES.pop, "test_custom_rule", None)
        self.custom_cluster(rule="test_custom_rule")
        row = self.make("job_a", {}, self.p)["data"]
        def broken(entry, data):
            increment(entry, data)
            raise ValueError("test rule failure")
        register_numbering_rule("test_custom_rule", broken)
        result = run_operation(self.c, lambda w: w.create("job_b", {}, project_id=self.p))
        self.assertFalse(result["ok"])
        self.assertEqual(read_record(self.c, "counter_state", id=self.p)["max_num"], row["id"])

    def test_unknown_rule_blocks_new_allocation_but_not_reading_or_undo(self):
        register_numbering_rule("test_removed_rule", lambda entry, data: {"project_id": data["project_id"], "id": increment(entry, data)})
        self.addCleanup(RULES.pop, "test_removed_rule", None)
        self.custom_cluster(rule="test_removed_rule")
        created = self.make("job_a", {}, self.p)
        RULES.pop("test_removed_rule")
        self.assertIsNotNone(read_record(self.c, "job_a", project_id=self.p, id=created["data"]["id"]))
        self.ok(undo_operation(self.c, created["operation_id"]))
        result = run_operation(self.c, lambda w: w.create("job_a", {}, project_id=self.p))
        self.assertFalse(result["ok"])

    def test_registration_persists_and_cannot_silently_reassign_existing_history(self):
        definition = self.custom_cluster()
        self.make("job_a", {}, self.p)
        register_numbering(self.c, {"jobs": definition})
        with closing(open_database(self.path)) as connection:
            self.assertEqual(numbering_entries(connection)["jobs"], definition)
            result = run_operation(connection, lambda w: w.create("job_b", {}, project_id=self.p))
            self.assertEqual(self.ok(result)["data"]["id"], 2)
        changed = deepcopy(definition)
        changed["counter"]["field"] = "other_max"
        with self.assertRaisesRegex(ValueError, "迁移"):
            register_numbering(self.c, {"jobs": changed})
        self.assertEqual(numbering_entries(self.c)["jobs"], definition)

    def test_numbering_registration_preserves_callers_pending_transaction(self):
        self.c.execute("UPDATE projects SET name='pending' WHERE id=?", (self.p,))
        with self.assertRaisesRegex(ValueError, "待提交"):
            register_numbering(self.c, {})
        self.assertTrue(self.c.in_transaction)
        self.c.rollback()

    def test_concurrent_connections_get_distinct_numbers(self):
        barrier = Barrier(2)
        def create():
            with closing(open_database(self.path)) as connection:
                barrier.wait(timeout=10)
                with transaction(connection) as w:
                    return w.create("layer", {"type": "text", "config_ref": "layers/text.toml"}, project_id=self.p)["id"]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: create(), range(2)))
        self.assertEqual(sorted(results), [1, 2])

    def test_custom_scope_field_defaults_are_available_to_allocation_and_restore(self):
        definition = self.custom_cluster()
        register_tables(self.c, {"bucket_job": {"fields": {"bucket_id": {"type": "INTEGER", "default": self.p}}}})
        definition["counter"]["key"] = {"id": "bucket_id"}
        definition["members"] = ["bucket_job"]
        register_numbering(self.c, {"bucket_jobs": definition})
        first = self.make("bucket_job", {}, self.p)["data"]
        second = self.make("bucket_job", {}, self.q)["data"]
        self.assertEqual((first["id"], second["id"]), (1, 2))
        bad = {**second, "id": first["id"]}
        result = run_operation(self.c, lambda w: w.restore("bucket_job", first["id"], bad, project_id=self.q))
        self.assertFalse(result["ok"], result)
        deleted = self.ok(run_operation(self.c, lambda w: w.delete("bucket_job", first["id"], project_id=self.p)))
        self.ok(undo_operation(self.c, deleted["operation_id"]))

    def test_alias_entries_sharing_one_counter_still_share_numbering_scope(self):
        definition = self.custom_cluster(provided=True)
        other = deepcopy(definition)
        other["members"] = ["job_b"]
        definition["members"] = ["job_a"]
        register_numbering(self.c, {"jobs": definition, "alias_jobs": other})
        self.make("job_a", {"id": 6}, self.p)
        result = run_operation(self.c, lambda w: w.create("job_b", {"id": 6}, project_id=self.p))
        self.assertFalse(result["ok"])

    def test_legacy_declarations_without_id_source_keep_project_cluster(self):
        register_tables(self.c, {"legacy_note": {"fields": {"body": "TEXT"}}})
        with transaction(self.c) as w:
            before = w.create("legacy_note", {"body": "old"}, project_id=self.p)
        # 模拟新字段及词条登记出现之前的数据库格式，仅修改本测试库。
        with self.c:
            self.c.execute("UPDATE _layerweave_tables SET definition=json_remove(definition,'$.id_source')")
            self.c.execute("DROP TABLE _layerweave_numbering")
        self.assertIn("legacy_note", numbering_entries(self.c)["project_entities"]["members"])
        newer = self.make("legacy_note", {}, self.p)["data"]
        self.assertGreater(newer["id"], before["id"])

    def test_failed_multi_entry_registration_is_atomic(self):
        definition = self.custom_cluster()
        before = numbering_entries(self.c)
        invalid = deepcopy(definition)
        invalid["counter"]["field"] = "missing_column"
        with self.assertRaisesRegex(ValueError, "计数列"):
            register_numbering(self.c, {"first": definition, "invalid": invalid})
        self.assertEqual(numbering_entries(self.c), before)


if __name__ == "__main__":
    unittest.main()

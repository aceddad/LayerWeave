"""声明缓存的查询成本、快照隔离、可变副本及维护失效；业务计数始终即时读取。"""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from layerweave.support.api import (initialize_database, open_database, transaction, read_snapshot,
    table_specs, register_tables, unregister_tables, retired_tables, read_record, read_changes,
    run_operation, numbering_entries, register_numbering, register_numbering_rule, increment, allocate)
from layerweave.support.records import writable_fields
from layerweave.support.numbering.registry import persist_entries
from layerweave.support.numbering.service import RULES
from layerweave.tool.builtin.usage.history.service import read_history


class MetadataCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="layerweave-metadata-tests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = initialize_database(self.root / "project.sqlite3")
        self.c = open_database(self.path)
        self.addCleanup(self.c.close)
        self.definition = {"fields": {"payload": "BLOB", "data": {"type": "JSON", "default": {"items": []}}}}
        register_tables(self.c, {"cache": self.definition})
        with transaction(self.c) as w:
            self.p = w.create("project", {"name": "metadata"})["id"]

    @contextmanager
    def catalog_reads(self, connection=None):
        connection = connection or self.c
        counts = {name: 0 for name in ("_layerweave_tables", "_layerweave_retired_tables", "_layerweave_numbering")}
        def trace(sql):
            if sql.lstrip().upper().startswith("SELECT"):
                for name in counts:
                    if f'FROM "{name}"' in sql:
                        counts[name] += 1
        connection.set_trace_callback(trace)
        try:
            yield counts
        finally:
            connection.set_trace_callback(None)

    def test_batch_loads_catalogs_once_not_per_record(self):
        register_tables(self.c, {f"other_{i}": {"fields": {}} for i in range(19)})
        with self.catalog_reads() as counts:
            with transaction(self.c) as w:
                rows = [w.create("cache", {"payload": bytes([i])}, project_id=self.p) for i in range(100)]
                for i, row in enumerate(rows):
                    self.assertEqual(w.read("cache", project_id=self.p, id=row["id"])["payload"], bytes([i]))
        self.assertEqual(counts["_layerweave_tables"], 1)
        self.assertEqual(counts["_layerweave_numbering"], 1)
        self.assertEqual(len({row["id"] for row in rows}), 100)
        self.assertEqual(read_record(self.c, "project", id=self.p)["max_id"], 100)

    def test_history_and_change_feed_reuse_active_and_retired_declarations(self):
        register_tables(self.c, {"other": self.definition})
        with transaction(self.c) as w:
            for i in range(80):
                w.create("cache" if i % 2 else "other", {"payload": bytes([i])}, project_id=self.p)
            operation = w.operation_id
        unregister_tables(self.c, ["cache"])
        readers = [lambda: read_changes(self.c, limit=10),
                   lambda: read_history(self.c, operation_id=operation),
                   lambda: read_record(self.c, "change", filters={"operation_id": operation})]
        for reader in readers:
            with self.subTest(reader=reader), self.catalog_reads() as counts:
                result = reader()
                self.assertTrue(result)
            self.assertEqual(counts["_layerweave_tables"], 1)
            self.assertEqual(counts["_layerweave_retired_tables"], 1)
        self.assertEqual(read_changes(self.c, limit=10)["changes"][-1]["after_data"]["payload"], bytes([79]))

    def test_public_results_are_independent_deep_copies(self):
        register_tables(self.c, {"retire_me": self.definition})
        unregister_tables(self.c, ["retire_me"])
        with transaction(self.c) as w:
            specs = table_specs(self.c)
            specs["cache"]["columns"]["data"]["default"]["items"].append("polluted")
            specs["cache"]["fields"].append("extra")
            specs["cache"]["references"].clear()
            writable_fields("cache", connection=self.c).append("extra")
            numbering_entries(self.c)["project_entities"]["members"].clear()
            archive = retired_tables(self.c)
            archive["retire_me"]["definition"]["columns"]["payload"]["type"] = "TEXT"
            self.assertNotIn("extra", table_specs(self.c)["cache"]["fields"])
            self.assertEqual(retired_tables(self.c)["retire_me"]["definition"]["columns"]["payload"]["type"], "BLOB")
            self.assertIn("cache", numbering_entries(self.c)["project_entities"]["members"])
            record = w.create("cache", {"payload": b"x"}, project_id=self.p)
            self.assertEqual(record["data"], {"items": []})
            with self.assertRaisesRegex(ValueError, "不能写入"):
                w.update("cache", record["id"], {"extra": 1}, project_id=self.p)

    def test_same_connection_nested_reads_share_one_cache(self):
        with self.catalog_reads() as counts:
            with read_snapshot(self.c):
                for _ in range(10):
                    with read_snapshot(self.c):
                        table_specs(self.c)
                        numbering_entries(self.c)
                        read_record(self.c, "cache", project_id=self.p)
        self.assertEqual(counts["_layerweave_tables"], 1)
        self.assertEqual(counts["_layerweave_numbering"], 1)

    def test_different_connections_and_databases_do_not_share_declarations(self):
        other = open_database(initialize_database(self.root / "other.sqlite3"))
        self.addCleanup(other.close)
        register_tables(other, {"cache": {"fields": {"payload": "TEXT"}}})
        with self.catalog_reads() as first, self.catalog_reads(other) as second:
            with read_snapshot(self.c):
                self.assertEqual(table_specs(self.c)["cache"]["columns"]["payload"]["type"], "BLOB")
                with read_snapshot(other):
                    for _ in range(5):
                        self.assertEqual(table_specs(other)["cache"]["columns"]["payload"]["type"], "TEXT")
                        self.assertEqual(table_specs(self.c)["cache"]["columns"]["payload"]["type"], "BLOB")
                self.assertEqual(table_specs(self.c)["cache"]["columns"]["payload"]["type"], "BLOB")
        self.assertEqual(first["_layerweave_tables"], 1)
        self.assertEqual(second["_layerweave_tables"], 1)

    def test_wal_snapshot_sees_old_schema_then_next_scope_sees_external_commit(self):
        self.c.execute("PRAGMA journal_mode=WAL")
        other = open_database(self.path)
        self.addCleanup(other.close)
        with read_snapshot(self.c):
            self.assertNotIn("new_table", table_specs(self.c))
            register_tables(other, {"new_table": {"fields": {"extra": "TEXT"}}})
            self.assertNotIn("new_table", table_specs(self.c))
            self.assertIn("new_table", table_specs(other))
        with read_snapshot(self.c):
            self.assertIn("new_table", table_specs(self.c))
            self.assertIn("cache", table_specs(self.c))
            unregister_tables(other, ["cache"])
            self.assertIn("cache", table_specs(self.c))
            self.assertEqual(read_record(self.c, "cache", project_id=self.p), [])
        with self.assertRaisesRegex(ValueError, "退出托管"):
            read_record(self.c, "cache", project_id=self.p)
        self.assertIn("cache", retired_tables(self.c))

    def test_metadata_queries_outside_scope_are_fresh(self):
        other = open_database(self.path)
        self.addCleanup(other.close)
        self.assertNotIn("new_table", table_specs(self.c))
        register_tables(other, {"new_table": {"fields": {}}})
        self.assertIn("new_table", table_specs(self.c))
        self.assertFalse(self.c.in_transaction)
        with self.catalog_reads() as counts:
            table_specs(self.c)
            table_specs(self.c)
        self.assertEqual(counts["_layerweave_tables"], 2)

    def test_borrowed_transaction_stays_open_after_snapshot_exception(self):
        self.c.execute("BEGIN")
        try:
            with self.assertRaisesRegex(RuntimeError, "stop"):
                with read_snapshot(self.c):
                    table_specs(self.c)
                    raise RuntimeError("stop")
            self.assertTrue(self.c.in_transaction)
            with self.catalog_reads() as counts:
                with read_snapshot(self.c):
                    table_specs(self.c)
            self.assertEqual(counts["_layerweave_tables"], 1)
        finally:
            self.c.rollback()

    def test_rollback_drops_scope_and_does_not_cache_business_values(self):
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with transaction(self.c) as w:
                w.create("cache", {"payload": b"x"}, project_id=self.p)
                self.assertEqual(w.read("project", id=self.p)["max_id"], 1)
                raise RuntimeError("rollback")
        with self.catalog_reads() as counts:
            with transaction(self.c) as w:
                first = w.create("cache", {"payload": b"y"}, project_id=self.p)
                self.assertEqual(first["id"], 1)
                w.update("cache", first["id"], {"payload": b"new"}, project_id=self.p)
                self.assertEqual(w.read("cache", id=first["id"], project_id=self.p)["payload"], b"new")
                second = w.create("cache", {"payload": b"z"}, project_id=self.p)
                self.assertEqual(second["id"], 2)
        self.assertEqual(counts["_layerweave_tables"], 1)

    def test_registration_refreshes_members_and_new_column_defaults(self):
        register_tables(self.c, {"new_table": {"fields": {}}})
        raw = self.c.execute("SELECT definition FROM _layerweave_numbering WHERE name='project_entities'").fetchone()[0]
        self.assertIn("new_table", json.loads(raw)["members"])
        with transaction(self.c) as w:
            id = w.create("cache", {"payload": b"x"}, project_id=self.p)["id"]
        changed = deepcopy(self.definition)
        changed["fields"]["later"] = {"type": "TEXT", "default": "new"}
        register_tables(self.c, {"cache": changed})
        self.assertEqual(read_record(self.c, "cache", project_id=self.p, id=id)["later"], "new")
        unregister_tables(self.c, ["new_table"])
        self.assertNotIn("new_table", numbering_entries(self.c)["project_entities"]["members"])

    def test_failed_registration_and_retirement_cannot_leave_cached_ghosts(self):
        def fail_after_observing(connection, entries):
            table_specs(connection)
            retired_tables(connection)
            raise RuntimeError("rollback metadata")
        with patch("layerweave.support.numbering.registry.persist_entries", side_effect=fail_after_observing):
            with self.assertRaisesRegex(RuntimeError, "rollback metadata"):
                register_tables(self.c, {"ghost": {"fields": {}}})
            with self.assertRaisesRegex(RuntimeError, "rollback metadata"):
                unregister_tables(self.c, ["cache"])
        self.assertNotIn("ghost", table_specs(self.c))
        self.assertIn("cache", table_specs(self.c))
        self.assertNotIn("cache", retired_tables(self.c))
        self.assertIn("cache", numbering_entries(self.c)["project_entities"]["members"])

    def test_rule_receives_detached_nested_declaration(self):
        def rule(entry, data):
            self.assertEqual(entry["counter"]["key"], {"id": "project_id"})
            result = {"project_id": data["project_id"], "id": increment(entry, data)}
            entry["counter"]["key"]["id"] = "broken"
            entry["members"].clear()
            return result
        register_numbering_rule("metadata_copy_test", rule)
        self.addCleanup(RULES.pop, "metadata_copy_test", None)
        entry = numbering_entries(self.c)["project_entities"]
        entry["rule"] = "metadata_copy_test"
        register_numbering(self.c, {"project_entities": entry})
        with transaction(self.c) as w:
            first = w.create("cache", {"payload": b"x"}, project_id=self.p)
            second = w.create("cache", {"payload": b"y"}, project_id=self.p)
            self.assertGreater(second["id"], first["id"])
            self.assertIn("cache", numbering_entries(self.c)["project_entities"]["members"])

    def test_persisted_rule_change_invalidates_in_current_session(self):
        with self.assertRaisesRegex(ValueError, "发号规则未加载"):
            with transaction(self.c):
                entries = numbering_entries(self.c)
                entries["project_entities"]["rule"] = "missing_rule"
                persist_entries(self.c, entries)
                allocate("project_entities", data={"project_id": self.p})
        self.assertEqual(numbering_entries(self.c)["project_entities"]["rule"], "project_entity")
        with transaction(self.c):
            self.assertEqual(allocate("project_entities", data={"project_id": self.p})["id"], 1)


if __name__ == "__main__":
    unittest.main()

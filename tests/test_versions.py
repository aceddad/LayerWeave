"""版本工具真实扫描、托管记录、范围核对与恢复；仅用临时数据库。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch

from layerweave.support.api import initialize_database, open_database, read_record, table_specs, transaction
from layerweave.support.paths import BUILTIN_ROOT, PACKAGE_ROOT
from layerweave.support.storage import crud
from layerweave.tool.builtin.developer.versions import manage_versions, read_versions, sync_versions
from layerweave.tool.builtin.developer.versions.discovery import path_key
from layerweave.tool.builtin.usage.history.service import read_history
from layerweave.tool.builtin.usage.undo.service import undo_operation


class VersionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="layerweave-versions-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.database = initialize_database(self.root / "data.sqlite3")
        self.c = open_database(self.database)
        self.addCleanup(self.c.close)

    def declare(self, folder="demo", *, name="demo", version="0.1.0", **fields):
        directory = self.tools / folder
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "component.toml"
        data = {"name": name, "version": version, **fields}
        path.write_text("\n".join(f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in data.items()), encoding="utf-8")
        return path

    def sync(self, roots=None):
        result = sync_versions(self.c, roots=[self.tools] if roots is None else roots)
        self.assertTrue(result["ok"], result)
        return result

    def rows(self):
        return read_versions(self.c)["items"]

    def test_read_does_not_create_a_table_or_write_even_on_read_only_connection(self):
        self.c.execute("PRAGMA query_only = ON")
        result = manage_versions(self.c, "read")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["operation"]["status"], "read")
        self.assertEqual(result["data"]["items"], [])
        self.assertFalse(result["data"]["registered"])
        self.assertNotIn("component_version", table_specs(self.c))

    def test_default_scan_registers_every_complete_package_and_itself(self):
        result = manage_versions(self.c)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["status"], "completed")
        rows = self.rows()
        expected = {"foundation", "records", "query", "editing", "history", "undo", "validation", "text",
                    "help", "database", "skills", "keys", "versions", "view"}   # view：visualization 分支的视图工具包
        self.assertEqual({row["name"] for row in rows}, {"layerweave." + name for name in expected})
        self.assertEqual(len(rows), 14)
        self.assertTrue(all(row["status"] == "online" and row["version"] for row in rows))
        self.assertEqual(next(row for row in rows if row["name"] == "layerweave.foundation")["version"], "0.4.0")
        self.assertEqual(next(row for row in rows if row["name"] == "layerweave.view")["version"], "0.18.0")
        self.assertEqual(sum(row["kind"] == "tool" for row in rows), 13)
        self.assertEqual(sum(row["kind"] == "foundation" for row in rows), 1)
        self.assertEqual(len(list(BUILTIN_ROOT.rglob("component.toml"))), 13)
        self.assertTrue((PACKAGE_ROOT / "component.toml").is_file())

    def test_scan_is_static_ignores_undeclared_code_and_uses_defaults(self):
        (self.tools / "__init__.py").write_text("raise AssertionError('must not execute')", encoding="utf-8")
        self.assertEqual(self.sync()["data"]["items"], [])
        source = self.declare()
        self.sync()
        row = self.rows()[0]
        self.assertEqual(row["kind"], "tool")
        self.assertEqual(row["description"], "")
        self.assertEqual(row["sources"], {path_key(source): "online"})
        self.assertEqual(row["status"], "online")
        self.assertTrue(row["checked_at"].endswith("+00:00"))
        self.assertFalse(table_specs(self.c)["component_version"]["scoped"])

    def test_repeat_sync_reuses_id_and_updates_description(self):
        self.declare(description="old")
        first = self.sync()
        record_id = self.rows()[0]["id"]
        self.declare(description="new", changes="first change")
        self.sync()
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0]["id"], record_id)
        self.assertEqual(self.rows()[0]["description"], "new")
        self.assertEqual(self.rows()[0]["changes"], "first change")
        history = read_history(self.c, kind="component_version", id=record_id)
        self.assertEqual(history["operation_count"], 2)
        self.assertTrue(first["applied"])

    def test_exact_version_match_keeps_old_row_and_marks_it_inactive(self):
        self.declare(version="0.1")
        self.sync()
        old_id = self.rows()[0]["id"]
        self.declare(version="0.1.0")
        self.sync()
        by_version = {row["version"]: row for row in self.rows()}
        self.assertEqual(by_version["0.1"]["status"], "inactive")
        self.assertEqual(by_version["0.1"]["id"], old_id)
        self.assertEqual(by_version["0.1.0"]["status"], "online")
        self.assertGreater(by_version["0.1.0"]["id"], old_id)

    def test_two_versions_can_both_be_online(self):
        self.declare("old", version="0.1.0")
        self.declare("new", version="0.2.0")
        self.sync()
        self.assertEqual(read_versions(self.c)["counts"]["online"], 2)

    def test_deleted_directory_becomes_inactive_and_reappearance_reuses_id(self):
        source = self.declare()
        self.sync()
        record_id = self.rows()[0]["id"]
        source.unlink()
        source.parent.rmdir()
        self.sync([source.parent])
        self.assertEqual(self.rows()[0]["status"], "inactive")
        self.declare()
        self.sync()
        self.assertEqual((self.rows()[0]["id"], self.rows()[0]["status"]), (record_id, "online"))

    def test_renamed_component_is_a_new_identity(self):
        self.declare(name="first")
        self.sync()
        self.declare(name="second")
        self.sync()
        self.assertEqual({row["name"]: row["status"] for row in self.rows()}, {"first": "inactive", "second": "online"})

    def test_multiple_copies_merge_and_local_scan_preserves_other_locations(self):
        first = self.declare("a")
        second = self.declare("b")
        self.sync()
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(len(self.rows()[0]["sources"]), 2)
        first.unlink()
        self.sync([first])
        self.assertEqual(self.rows()[0]["status"], "online")
        self.assertEqual(self.rows()[0]["sources"][path_key(first)], "inactive")
        self.assertEqual(self.rows()[0]["sources"][path_key(second)], "online")
        second.unlink()
        self.sync([second])
        self.assertEqual(self.rows()[0]["status"], "inactive")

    def test_local_scan_leaves_unrelated_records_exactly_unchanged(self):
        first = self.declare("a", name="first")
        second = self.declare("b", name="second")
        self.sync()
        old = read_versions(self.c, name="second")["items"]
        second.unlink()
        self.sync([first])
        self.assertEqual(read_versions(self.c, name="second")["items"], old)

    def test_overlapping_roots_do_not_duplicate_rows_or_sources(self):
        source = self.declare()
        self.sync([self.tools, source.parent, source, self.tools])
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(len(self.rows()[0]["sources"]), 1)

    def test_broken_declaration_is_reported_and_other_components_continue(self):
        bad = self.declare("a", name="broken")
        self.declare("b", name="good")
        self.sync()
        bad.write_text("name = [", encoding="utf-8")
        result = self.sync()
        self.assertEqual(result["data"]["status"], "partial")
        self.assertEqual(len(result["data"]["issues"]), 1)
        self.assertEqual({row["name"]: row["status"] for row in self.rows()}, {"broken": "unknown", "good": "online"})
        self.declare("a", name="broken")
        self.sync()
        self.assertEqual(read_versions(self.c)["counts"]["online"], 2)

    def test_unreadable_scan_directory_does_not_claim_components_deleted(self):
        self.declare()
        self.sync()

        def fail_walk(root, onerror):
            onerror(PermissionError(13, "test permission", str(root)))
            return iter(())

        with patch("layerweave.tool.builtin.developer.versions.discovery.os.walk", side_effect=fail_walk):
            result = self.sync()
        self.assertEqual(result["data"]["status"], "partial")
        self.assertEqual(self.rows()[0]["status"], "unknown")

    def test_read_filters_and_connection_reopen_preserve_records(self):
        self.declare()
        self.sync()
        with closing(open_database(self.database)) as connection:
            result = manage_versions(connection, "read", name="demo", status="online")
            self.assertTrue(result["ok"], result)
            self.assertEqual(len(result["data"]["items"]), 1)
            self.assertEqual(read_versions(connection, status="inactive")["items"], [])

    def test_upgrade_sync_can_be_undone_and_redone_as_one_operation(self):
        self.declare()
        self.sync()
        before = self.rows()
        self.declare(version="0.2.0")
        result = self.sync()
        after = self.rows()
        self.assertEqual(len(result["operation"]["changes"]), 2)
        undone = undo_operation(self.c, result["operation_id"])
        self.assertTrue(undone["ok"], undone)
        self.assertEqual(self.rows(), before)
        self.assertTrue(undo_operation(self.c, undone["operation_id"])["ok"])
        self.assertEqual(self.rows(), after)

    def test_version_ids_do_not_consume_project_numbering(self):
        with transaction(self.c) as write:
            project = write.create("project", {"name": "keep"})
        self.declare()
        self.sync()
        self.assertEqual(read_record(self.c, "project", id=project["id"]), project)

    def test_log_failure_rolls_back_all_sync_rows(self):
        self.declare()
        self.sync()
        rows_before = self.rows()
        logs_before = read_record(self.c, "change")
        self.declare(version="0.2.0")
        original = crud.append_change
        calls = []

        def fail_second(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError("test log failure")
            return original(*args, **kwargs)

        with patch.object(crud, "append_change", side_effect=fail_second):
            result = sync_versions(self.c, roots=[self.tools])
        self.assertFalse(result["ok"], result)
        self.assertEqual(self.rows(), rows_before)
        self.assertEqual(read_record(self.c, "change"), logs_before)

    def test_concurrent_syncs_do_not_duplicate_registration(self):
        self.declare()
        barrier = Barrier(2)

        def sync_separately():
            with closing(open_database(self.database)) as connection:
                barrier.wait(timeout=10)
                return sync_versions(connection, roots=[self.tools])

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: sync_separately(), range(2)))
        self.assertTrue(all(result["ok"] for result in results), results)
        self.assertEqual(len(self.rows()), 1)

    def test_cli_sync_read_and_help_from_external_directory(self):
        self.declare()
        command = [sys.executable, "-X", "utf8", "-B", "-m", "layerweave.tool.builtin.developer.versions.cli"]
        for args in ([str(self.database), "sync", "--root", str(self.tools), "--json"],
                     [str(self.database), "read", "--name", "demo", "--json"]):
            result = subprocess.run(command + args, cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["data"]["items"][0]["name"], "demo")
        result = subprocess.run(command + [str(self.database), "read"], cwd=self.root,
                                capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("在线", result.stdout)
        self.assertIn("核对时间", result.stdout)
        help_result = subprocess.run(command + ["--help"], cwd=self.root,
                                     capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("component.toml", help_result.stdout)


if __name__ == "__main__":
    unittest.main()

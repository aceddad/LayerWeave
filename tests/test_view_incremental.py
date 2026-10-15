"""视图增量：同快照、完整操作、跨项目关联、工具状态及撤销。只用临时数据库。"""
from contextlib import closing
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen

from layerweave.support.api import initialize_database, open_database, transaction, register_tables, change_cursor
from layerweave.tool.builtin.usage.undo.service import undo_operation
from layerweave.tool.builtin.view.data import project_view
from layerweave.tool.builtin.view.fold import TABLE
from layerweave.tool.builtin.view.notes.reads import READ_TABLE
from layerweave.tool.builtin.view.incremental import project_snapshot, project_delta
from layerweave.tool.builtin.view.server import make_server


class ViewIncrementalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-view-incremental-")
        self.addCleanup(self.temp.cleanup)
        self.path = initialize_database(Path(self.temp.name) / "view.sqlite3")
        self.c = open_database(self.path)
        self.addCleanup(self.c.close)
        self.c.execute("PRAGMA journal_mode=WAL")
        register_tables(self.c, {**TABLE, **READ_TABLE})
        with transaction(self.c) as w:
            self.p = w.create("project", {"name": "one"})["id"]
            self.q = w.create("project", {"name": "two"})["id"]
            self.layer = w.create("layer", {"type": "text", "config_ref": "layers/text.toml", "name": "root", "axis": {"unit": "s"}}, project_id=self.p)["id"]
            self.obj = w.create("object", {"config_ref": "objects/text.toml", "layer": self.layer, "begin": 0, "end": 3,
                                           "information": {"text": "old"}}, project_id=self.p)["id"]
        self.cursor = change_cursor(self.c)

    def delta(self, **kw):
        return project_delta(self.c, self.path, self.p, after=self.cursor, **kw)

    def test_snapshot_cursor_excludes_commit_after_its_data_read(self):
        real = project_view
        def interleave(connection, database, project_id):
            data = real(connection, database, project_id)
            with closing(open_database(self.path)) as other, transaction(other) as w:
                w.update("object", self.obj, {"information": {"text": "new"}}, project_id=self.p)
            return data
        with patch("layerweave.tool.builtin.view.incremental.project_view", side_effect=interleave):
            snapshot = project_snapshot(self.c, self.path, self.p)
        self.assertEqual(snapshot["next_cursor"], self.cursor)
        self.assertEqual(snapshot["data"]["layers"][0]["objects"][0]["text"], "old")
        self.assertEqual(self.delta()["changes"][0]["after"]["text"], "new")

    def test_object_projection_uses_each_log_snapshot_not_current_row(self):
        with transaction(self.c) as w:
            w.update("object", self.obj, {"information": {"text": "first"}}, project_id=self.p)
            w.update("object", self.obj, {"information": {"text": "second"}}, project_id=self.p)
        with transaction(self.c) as w:
            w.update("object", self.obj, {"information": {"text": "later"}}, project_id=self.p)
        page = self.delta(limit=1)
        self.assertEqual(page["mode"], "delta")
        self.assertEqual([c["after"]["text"] for c in page["changes"]], ["first", "second"])
        self.assertTrue(page["has_more"])
        self.assertEqual(page["changes"][0]["after_layer"], self.layer)
        self.assertEqual(page["changes"][0]["after"]["end"], 3)

    def test_unrelated_rows_still_advance_global_cursor(self):
        with transaction(self.c) as w:
            w.update("project", self.q, {"name": "elsewhere"})
        page = self.delta()
        self.assertEqual(page["changes"], [])
        self.assertGreater(page["next_cursor"], self.cursor)

    def test_cross_project_bind_enter_and_exit_check_both_snapshots(self):
        with transaction(self.c) as w:
            b = w.create("bind", {"source_kind": "object", "source_project_id": self.q, "source_id": 100,
                                  "target_kind": "object", "target_project_id": self.p, "target_id": self.obj})["id"]
        self.assertEqual(self.delta()["changes"][0]["after"]["target"]["project"], self.p)
        self.cursor = change_cursor(self.c)
        with transaction(self.c) as w:
            w.update("bind", b, {"target_project_id": self.q})
        self.assertIsNone(self.delta()["changes"][0]["after"])

    def test_tool_rows_and_undo_project_to_same_protocol(self):
        with transaction(self.c) as w:
            w.create("view_layer", {"id": self.layer, "user_fold": "reader"}, project_id=self.p)
            w.create("view_note", {"id": self.obj, "reads": '{"reader": 9}'}, project_id=self.p)
        op = w.operation_id
        page = self.delta()
        self.assertEqual([c["kind"] for c in page["changes"]], ["view_layer", "view_note"])
        self.assertEqual(page["changes"][1]["after"], {"reader": 9})
        self.cursor = page["next_cursor"]
        self.assertTrue(undo_operation(self.c, op)["ok"])
        changes = self.delta()["changes"]
        self.assertTrue(all(c["after"] is None and c["undo_of"] == op for c in changes))

    def test_layer_changes_return_snapshot_through_current_head(self):
        with transaction(self.c) as w:
            w.update("layer", self.layer, {"name": "renamed"}, project_id=self.p)
        with transaction(self.c) as w:
            w.update("object", self.obj, {"end": 9}, project_id=self.p)
        page = self.delta(limit=1)
        self.assertEqual(page["mode"], "snapshot")
        self.assertEqual(page["next_cursor"], change_cursor(self.c))
        self.assertEqual(page["data"]["roots"][0]["extent"], [0, 9])
        self.assertFalse(page["has_more"])

    def test_deleted_project_and_ahead_cursor_have_explicit_snapshot(self):
        with transaction(self.c) as w:
            w.delete("object", self.obj, project_id=self.p)
            w.delete("layer", self.layer, project_id=self.p)
            w.delete("project", self.p)
        self.assertIsNone(self.delta()["data"])
        self.assertEqual(project_delta(self.c, self.path, self.q, after=99999)["mode"], "snapshot")

    def test_empty_project_delete_then_undo_restores_a_full_snapshot(self):
        # 没有层可触发结构回退：项目本身的恢复也必须恢复 data=null 的客户端。
        initial = project_snapshot(self.c, self.path, self.q)
        self.assertEqual(initial["data"]["layers"], [])
        with transaction(self.c) as w:
            w.delete("project", self.q)
        removed = project_delta(self.c, self.path, self.q, after=initial["next_cursor"])
        self.assertIsNone(removed["data"])
        self.assertTrue(undo_operation(self.c, w.operation_id)["ok"])
        restored = project_delta(self.c, self.path, self.q, after=removed["next_cursor"])
        self.assertEqual(restored["mode"], "snapshot")
        self.assertEqual(restored["data"]["project"]["id"], self.q)
        self.assertEqual(restored["data"]["layers"], [])
        self.assertGreater(restored["next_cursor"], removed["next_cursor"])

    def test_media_projection_checks_only_changed_objects(self):
        image = Path(self.temp.name) / "image.png"
        image.write_bytes(b"test")
        with transaction(self.c) as w:
            w.update("object", self.obj, {"information": {"source": "image.png"}}, project_id=self.p)
        page = self.delta()
        self.assertEqual(page["changes"][0]["after"]["media"], {
            "kind": "image", "source": "image.png", "available": True, "url": f"/media/{self.p}/{self.obj}"})

    def test_http_snapshot_and_delta_keep_existing_project_endpoint(self):
        server, url = make_server(self.path, state_root=Path(self.temp.name) / "state")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            def get(path):
                with urlopen(url.rstrip("/") + path, timeout=5) as response:
                    return json.load(response)
            self.assertIn("layers", get(f"/api/project/{self.p}"))
            snapshot = get(f"/api/project/{self.p}/snapshot")
            with transaction(self.c) as w:
                w.update("object", self.obj, {"name": "http"}, project_id=self.p)
            delta = get(f"/api/project/{self.p}/delta?after={snapshot['next_cursor']}")
            self.assertEqual(delta["changes"][0]["after"]["name"], "http")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

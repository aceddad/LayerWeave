"""复查、历史、整批撤销/重做及旧库迁移；仅使用内存或临时数据库。"""

from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

from runtime.api import (dispatch, initialize_database, open_database, read_history, read_record,
                         recheck, save_layer, save_object, undo_operation)
from runtime.configuration.loader import DEFAULT_ROOT
from runtime.storage.database import SCHEMA_PATH, upgrade_history
from tools.common.history import format_history
from tools.common.recheck import format_recheck
from tools.common.undo import format_undo


class HistoryToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-history-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.p = self.call("create", "project", data={"name": "项目"})["id"]
        self.l = self.layer()

    def call(self, action, kind, **kw):
        if kind in {"layer", "object"}:
            kw.setdefault("project_id", self.p)
        result = dispatch(self.c, {"action": action, "kind": kind, **kw}, checker=None)
        self.assertTrue(result["ok"], result)
        return result

    def layer(self, **data):
        return self.call("create", "layer", data={"config_ref": "layers/text.toml", **data})["id"]

    def obj(self, **data):
        return self.call("create", "object", data={"config_ref": "objects/text.toml", "layer": self.l,
                         "information": {"text": "原文"}, **data})

    def bind(self, source=None, target=None, target_project=None):
        return self.call("create", "bind", data={"source_kind": "layer", "source_project_id": self.p,
                         "source_id": self.l if source is None else source, "target_kind": "layer",
                         "target_project_id": self.p if target_project is None else target_project,
                         "target_id": self.l if target is None else target})

    def row(self, kind, id, project_id=None):
        return read_record(self.c, kind, id=id, **({"project_id": self.p if project_id is None else project_id} if kind in {"layer", "object"} else {}))

    def undo(self, operation_id, **kw):
        result = undo_operation(self.c, operation_id, **kw)
        self.assertTrue(result["ok"], result)
        return result

    def snapshot(self):
        return {table: [tuple(row) for row in self.c.execute(f'SELECT * FROM "{table}" ORDER BY 1, 2')]
                for table in ("projects", "layers", "objects", "binds", "changes", "sqlite_sequence")}

    def test_recheck_subtrees_are_deduplicated_and_other_content_is_not_checked(self):
        child = self.layer(father=self.l)
        outside = self.layer()
        self.obj(layer=child, information={"text": 12})
        other = self.obj(layer=outside, information={"text": False})["id"]
        before = self.snapshot()
        result = recheck(self.c, self.p, layer_ids=[self.l, child, self.l, 999])
        self.assertEqual(result["counts"], {"layers": 2, "objects": 1})
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["issue_counts"], {"error": 1, "warn": 1})
        self.assertFalse(any(i["target"].get("id") == other for i in result["issues"]))
        self.assertEqual(self.snapshot(), before)
        self.assertIn("部分检查未完成", format_recheck(result))

    def test_recheck_project_includes_incoming_bindings_and_errors_are_not_execution_failure(self):
        other_project = self.call("create", "project", data={})["id"]
        self.bind(target_project=other_project, target=999)
        result = recheck(self.c, other_project)
        self.assertEqual(result["status"], "completed")
        self.assertTrue(any(i["code"] == "bind_reference_missing" for i in result["issues"]))
        bad = self.obj(information={"text": 1})
        result = recheck(self.c, self.p, object_ids=[bad["id"], bad["id"]])
        self.assertEqual(result["counts"], {"layers": 0, "objects": 1})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["issue_counts"]["error"], 1)

    def test_recheck_empty_missing_and_changed_configuration(self):
        self.assertEqual(recheck(self.c, self.p, object_ids=[])["issues"], [])
        self.assertEqual(recheck(self.c, 999)["status"], "partial")
        self.assertEqual(recheck(self.c, self.p, object_ids=[999])["status"], "partial")
        with self.assertRaises(ValueError):
            recheck(self.c, self.p, layer_ids=[], object_ids=[])
        obj = self.obj()
        configs = self.root / "configs"
        shutil.copytree(DEFAULT_ROOT, configs)
        path = configs / "objects/text.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('text = { type = "str"', 'text = { type = "int"'), encoding="utf-8")
        result = recheck(self.c, self.p, object_ids=[obj["id"]], config_root=configs)
        self.assertTrue(any(i["code"] == "field_type" for i in result["issues"]))

    def test_history_counts_operations_not_rows_and_pages_whole_operations(self):
        obj = self.obj()
        batch = dispatch(self.c, [{"action": "update", "kind": "object", "project_id": self.p, "id": obj["id"], "data": {"name": name}} for name in ("a", "b")], checker=None)
        deleted = self.call("delete", "object", id=obj["id"])
        result = read_history(self.c, self.p, kind="object", id=obj["id"], limit=1)
        self.assertEqual((result["operation_count"], result["change_count"]), (3, 4))
        self.assertEqual(result["items"][0]["operation_id"], deleted["operation_id"])
        second = read_history(self.c, self.p, kind="object", id=obj["id"], limit=1, before=result["next_cursor"])
        self.assertEqual(second["items"][0]["operation_id"], batch["operation_id"])
        self.assertEqual(len(second["items"][0]["changes"]), 2)
        third = read_history(self.c, self.p, kind="object", id=obj["id"], limit=1, before=second["next_cursor"])
        self.assertIsNone(third["next_cursor"])
        self.assertIn("3 次操作", format_history(result))

    def test_history_cross_project_selection_still_expands_whole_batch(self):
        other = self.call("create", "project", data={})["id"]
        op = dispatch(self.c, [{"action": "update", "kind": "project", "id": pid, "data": {"tips": "批次"}} for pid in (self.p, other)], checker=None)
        row = read_history(self.c, self.p, limit=1)["items"][0]
        self.assertEqual((row["matched_change_count"], row["change_count"]), (1, 2))
        self.assertEqual(row["project_ids"], [self.p, other])
        full = read_history(self.c, operation_id=op["operation_id"])
        self.assertIn("before", full["items"][0]["changes"][0])
        self.undo(op["operation_id"])
        self.assertEqual([self.row("project", pid)["tips"] for pid in (self.p, other)], ["", ""])

    def test_history_matches_both_bind_endpoints_and_preserves_json_value_types(self):
        other = self.call("create", "project", data={})["id"]
        b = self.bind(target_project=other, target=8)
        self.assertEqual(read_history(self.c, other, kind="bind")["items"][0]["operation_id"], b["operation_id"])
        o = self.obj(information={"text": "a", "n": 1, "gone": None})
        op = self.call("update", "object", id=o["id"], data={"information": {"text": "b", "n": True, "new": None}})
        fields = read_history(self.c, operation_id=op["operation_id"])["items"][0]["changes"][0]["fields"]
        by_path = {tuple(item["path"]): item for item in fields}
        self.assertTrue(by_path[("information", "gone")]["before_present"])
        self.assertFalse(by_path[("information", "gone")]["after_present"])
        self.assertIs(by_path[("information", "n")]["after"], True)

    def test_history_rejects_ambiguous_filters(self):
        for kwargs in ({"kind": "object", "id": 2}, {"id": 2}, {"limit": 0}, {"kind": "change"}, {"before": 0}):
            with self.assertRaises(ValueError):
                read_history(self.c, **kwargs)
        with self.assertRaises(ValueError):
            read_history(self.c, self.p, operation_id="x")
        self.assertEqual(read_history(self.c, operation_id="x")["items"], [])

    def test_create_delete_undo_redo_preserve_identity_counter_and_history(self):
        obj = self.obj(begin=1, end=2)
        original = self.row("object", obj["id"])
        undid = self.undo(obj["operation_id"])
        self.assertIsNone(self.row("object", obj["id"]))
        next_obj = self.obj()
        self.assertGreater(next_obj["id"], obj["id"])
        self.undo(undid["operation_id"])
        self.assertEqual(self.row("object", obj["id"]), original)
        self.assertEqual(self.row("project", self.p)["max_id"], next_obj["id"])
        op = read_history(self.c, operation_id=undid["operation_id"])["items"][0]
        self.assertEqual(op["undo_of"], obj["operation_id"])
        self.assertIn("撤销自", format_history({"operation_count": 1, "change_count": 1, "items": [op], "next_cursor": None}))

    def test_batch_updates_collapse_to_original_and_restore_exact_json(self):
        obj = self.obj(information={"text": "a", "n": 1.0})
        original = self.row("object", obj["id"])
        op = dispatch(self.c, [{"action": "update", "kind": "object", "project_id": self.p, "id": obj["id"], "data": {"information": info}} for info in ({"text": "b"}, {"text": "c", "n": True})], checker=None)
        u = self.undo(op["operation_id"])
        self.assertEqual(u["data"]["restored_records"], 1)
        self.assertEqual(self.row("object", obj["id"]), original)
        self.undo(u["operation_id"])
        self.assertIs(self.row("object", obj["id"])["information"]["n"], True)

    def test_composite_save_undo_and_redo_restore_same_layer_and_object_ids(self):
        data = {"config_ref": "layers/text.toml", "objects": [
            {"config_ref": "objects/title.toml", "information": {"text": "标题"}},
            {"config_ref": "objects/text.toml", "information": {"text": "正文"}}]}
        saved = save_layer(self.c, self.p, data)
        self.assertTrue(saved["ok"], saved)
        original = saved["data"]
        u = self.undo(saved["operation_id"])
        self.assertIsNone(self.row("layer", original["id"]))
        self.assertTrue(all(self.row("object", obj["id"]) is None for obj in original["objects"]))
        self.undo(u["operation_id"])
        self.assertEqual(self.row("layer", original["id"])["config_ref"], "layers/text.toml")
        self.assertEqual([self.row("object", obj["id"])["information"] for obj in original["objects"]],
                         [{"text": "标题"}, {"text": "正文"}])

    def test_deleted_empty_project_restores_allocation_high_water_across_redo(self):
        pid = self.call("create", "project", data={})["id"]
        layer = self.call("create", "layer", project_id=pid, data={"config_ref": "layers/text.toml"})["id"]
        obj = self.call("create", "object", project_id=pid, data={"config_ref": "objects/text.toml", "layer": layer})["id"]
        self.call("delete", "object", project_id=pid, id=obj)
        self.call("delete", "layer", project_id=pid, id=layer)
        deleted = self.call("delete", "project", id=pid)
        u = self.undo(deleted["operation_id"])
        self.assertEqual(self.row("project", pid)["max_id"], obj)
        self.undo(u["operation_id"])
        redo = self.undo(deleted["operation_id"])
        self.assertTrue(redo["ok"])
        next_layer = self.call("create", "layer", project_id=pid, data={"config_ref": "layers/text.toml"})["id"]
        self.assertGreater(next_layer, obj)

    def test_batch_can_restore_moved_children_and_deleted_parent(self):
        old = self.layer()
        obj = self.obj(layer=old)
        operation = dispatch(self.c, [
            {"action": "update", "kind": "object", "project_id": self.p, "id": obj["id"], "data": {"layer": self.l}},
            {"action": "delete", "kind": "layer", "project_id": self.p, "id": old}], checker=None)
        self.assertTrue(operation["ok"], operation)
        u = self.undo(operation["operation_id"])
        self.assertEqual(self.row("object", obj["id"])["layer"], old)
        self.undo(u["operation_id"])
        self.assertIsNone(self.row("layer", old))
        self.assertEqual(self.row("object", obj["id"])["layer"], self.l)

    def test_restoration_rejects_cross_kind_id_collision(self):
        obj = self.obj()
        deleted = self.call("delete", "object", id=obj["id"])
        # 模拟绕过发号器的直接 SQL；恢复不能制造层/对象同号。
        self.c.execute("INSERT INTO layers (project_id,id,type,config_ref) VALUES (?,?,'text','layers/text.toml')", (self.p, obj["id"]))
        self.c.commit()
        before = self.snapshot()
        result = undo_operation(self.c, deleted["operation_id"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["conflicts"][0]["code"], "undo_id_conflict")
        self.assertEqual(self.snapshot(), before)

    def test_conflicts_report_all_records_and_leave_everything_unchanged(self):
        a, b = self.obj(), self.obj()
        op = dispatch(self.c, [{"action": "update", "kind": "object", "project_id": self.p, "id": obj["id"], "data": {"name": "批次"}} for obj in (a, b)], checker=None)
        for obj in (a, b):
            self.call("update", "object", id=obj["id"], data={"name": "后续修改"})
        before = self.snapshot()
        result = undo_operation(self.c, op["operation_id"])
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["error"]["conflicts"]), 2)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("当前记录", format_undo(result))
        self.assertFalse(self.c.in_transaction)

    def test_later_operation_can_be_undone_then_earlier_undo_is_allowed(self):
        o = self.obj()
        later = self.call("update", "object", id=o["id"], data={"name": "后来"})
        self.undo(later["operation_id"])
        self.undo(o["operation_id"])
        self.assertIsNone(self.row("object", o["id"]))

    def test_new_dependents_block_deleting_created_parent(self):
        op = self.call("create", "layer", data={"config_ref": "layers/text.toml"})
        obj = self.obj(layer=op["id"])
        before = self.snapshot()
        result = undo_operation(self.c, op["operation_id"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["conflicts"][0]["related"][0]["id"], obj["id"])
        self.assertEqual(self.snapshot(), before)

    def test_missing_parent_blocks_restore_without_implicitly_restoring_it(self):
        o = self.obj()
        deleted = self.call("delete", "object", id=o["id"])
        self.call("delete", "layer", id=self.l)
        before = self.snapshot()
        result = undo_operation(self.c, deleted["operation_id"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["conflicts"][0]["field"], "layer")
        self.assertEqual(self.snapshot(), before)

    def test_restore_full_deleted_project_with_layers_objects_bindings_and_high_water(self):
        child = self.layer(father=self.l)
        o = self.obj(layer=child)
        b = self.bind(source=child)
        high = self.obj()["id"]
        self.call("delete", "object", id=high)
        original = {kind: self.row(kind, id) for kind, id in (("project", self.p), ("layer", child), ("object", o["id"]), ("bind", b["id"]))}
        delete = [{"action": "delete", "kind": kind, "id": id, **({"project_id": self.p} if kind in {"layer", "object"} else {})} for kind, id in (("bind", b["id"]), ("object", o["id"]), ("layer", child), ("layer", self.l), ("project", self.p))]
        op = dispatch(self.c, delete, checker=None)
        self.assertTrue(op["ok"], op)
        u = self.undo(op["operation_id"])
        for kind, row in original.items():
            self.assertEqual(self.row(kind, row["id"]), row)
        self.assertGreater(self.obj()["id"], high)
        self.assertGreater(self.bind()["id"], b["id"])
        self.assertEqual(self.c.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertTrue(u["applied"])

    def test_restoring_coordinates_does_not_snap_them_to_current_axis(self):
        self.call("update", "layer", id=self.l, data={"axis": {"precision": 0.001}})
        o = self.obj(begin=0.123, end=0.456)
        deleted = self.call("delete", "object", id=o["id"])
        self.call("update", "layer", id=self.l, data={"axis": {"precision": 1}})
        self.undo(deleted["operation_id"])
        self.assertEqual((self.row("object", o["id"])["begin"], self.row("object", o["id"])["end"]), (0.123, 0.456))

    def test_max_id_growth_does_not_conflict_with_project_content_undo(self):
        op = self.call("update", "project", id=self.p, data={"name": "new"})
        latest = self.obj()["id"]
        self.undo(op["operation_id"])
        self.assertEqual(self.row("project", self.p)["name"], "项目")
        self.assertEqual(self.row("project", self.p)["max_id"], latest)

    def test_restore_is_checked_with_current_configuration_after_commit(self):
        o = self.obj(information={"text": 9})
        deleted = self.call("delete", "object", id=o["id"])
        result = self.undo(deleted["operation_id"])
        self.assertEqual(result["operation"]["status"], "committed")
        self.assertTrue(any(i["code"] == "field_type" for i in result["checks"]["issues"]))

    def test_repeated_undo_and_missing_operations_do_not_make_new_changes(self):
        o = self.obj()
        self.undo(o["operation_id"])
        before = self.snapshot()
        for operation_id in (o["operation_id"], "absent"):
            self.assertFalse(undo_operation(self.c, operation_id)["ok"])
            self.assertEqual(self.snapshot(), before)

    def test_no_net_change_operation_is_a_noop_and_keeps_counter(self):
        op = dispatch(self.c, [{"action": "update", "kind": "project", "id": self.p, "data": {"name": name}} for name in ("temp", "项目")], checker=None)
        before = self.snapshot()
        result = self.undo(op["operation_id"])
        self.assertFalse(result["applied"])
        self.assertEqual(self.snapshot(), before)

    def test_mid_restore_failure_rolls_back_rows_logs_and_sequences(self):
        a, b = self.obj(name="a"), self.obj(name="b")
        op = dispatch(self.c, [{"action": "delete", "kind": "object", "project_id": self.p, "id": obj["id"]} for obj in (a, b)], checker=None)
        self.c.execute("CREATE TRIGGER fail_restore BEFORE INSERT ON objects WHEN new.name='b' BEGIN SELECT RAISE(ABORT, 'blocked'); END")
        before = self.snapshot()
        result = undo_operation(self.c, op["operation_id"])
        self.assertFalse(result["ok"])
        self.assertEqual(self.snapshot(), before)

    def test_caller_transaction_is_not_committed_by_undo(self):
        o = self.obj()
        self.c.execute("UPDATE projects SET tips='pending'")
        result = undo_operation(self.c, o["operation_id"])
        self.assertFalse(result["ok"])
        self.assertTrue(self.c.in_transaction)
        self.c.rollback()
        self.assertEqual(self.row("project", self.p)["tips"], "")

    def test_new_binds_do_not_reuse_deleted_or_restored_ids(self):
        a = self.bind()
        deleted = self.call("delete", "bind", id=a["id"])
        b = self.bind()
        self.assertGreater(b["id"], a["id"])
        self.undo(deleted["operation_id"])
        self.assertGreater(self.bind()["id"], b["id"])

    def test_cli_tools_share_json_and_text_and_use_no_live_database(self):
        path = initialize_database(self.root / "cli.sqlite3")
        c = open_database(path)
        self.addCleanup(c.close)
        pid = dispatch(c, {"action": "create", "kind": "project", "data": {}})["id"]
        layer = save_layer(c, pid, {"config_ref": "layers/text.toml"})["data"]["id"]
        obj = save_object(c, pid, {"config_ref": "objects/text.toml", "layer": layer, "information": {"text": "test"}})
        commands = [("recheck", [str(pid), "--layer-ids", str(layer)]), ("history", ["--project-id", str(pid)]), ("undo", [obj["operation_id"]])]
        for module, args in commands:
            run = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", f"tools.common.{module}", str(path), *args, "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertIsInstance(result, dict)
        run = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", "tools.common.undo", str(path), result["operation_id"]], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("写入成功", run.stdout)


class HistoryMigrationTests(unittest.TestCase):
    def test_legacy_bind_ids_seed_from_deleted_history_and_custom_index_survives(self):
        c = open_database(":memory:")
        self.addCleanup(c.close)
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        schema = schema.replace("id                  INTEGER PRIMARY KEY AUTOINCREMENT,", "id                  INTEGER PRIMARY KEY,")
        schema = schema.replace("after_data      TEXT,", "after_data      TEXT").replace("    undo_of         TEXT            -- 撤销所针对的 operation_id；普通操作为 NULL\n", "")
        c.executescript(schema)
        c.execute("CREATE INDEX custom_bind_tips ON binds(tips)")
        c.execute("INSERT INTO binds VALUES (5,'layer',1,1,'object',1,2,'keep')")
        c.execute("INSERT INTO changes (operation_id,created_at,kind,project_id,target_id,action) VALUES ('legacy','time','bind',1,50,'delete')")
        c.commit()
        upgrade_history(c)
        upgrade_history(c)
        self.assertEqual(c.execute("SELECT tips FROM binds WHERE id=5").fetchone()[0], "keep")
        self.assertIsNotNone(c.execute("SELECT name FROM sqlite_master WHERE name='custom_bind_tips'").fetchone())
        self.assertIsNone(c.execute("SELECT undo_of FROM changes").fetchone()[0])
        result = dispatch(c, {"action": "create", "kind": "bind", "data": {"source_kind": "layer", "source_project_id": 1, "source_id": 1, "target_kind": "object", "target_project_id": 1, "target_id": 2}}, checker=None)
        self.assertEqual(result["id"], 51)
        c.execute("UPDATE binds SET tips='pending'")
        with self.assertRaisesRegex(ValueError, "待提交"):
            upgrade_history(c)
        self.assertTrue(c.in_transaction)
        c.rollback()
        self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()

"""公共事务内接口、异常传播和领号反馈；只使用内存数据库。"""
from contextlib import closing
import unittest

from layerweave.models import Text, TextLayer
from layerweave.support.api import (open_database, transaction, run_operation, read_record, allocate, increment,
                                   numbering_entries, format_feedback, save_layer_in_session, save_object_in_session)
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.tool.builtin.usage.editing.objects import (
    append_object, append_object_in_session, copy_object_in_session)
from layerweave.tool.builtin.usage.editing.positions import (
    align_objects_in_session, arrange_objects_in_session, set_duration_in_session)
from layerweave.tool.builtin.usage.editing.timeline import (
    shift_objects_in_session, split_object_in_session, insert_gap_in_session)
from layerweave.tool.builtin.usage.editing.tree_service import (
    copy_subtree_in_session, delete_subtree_in_session, transfer_subtree_in_session, transfer_objects_in_session)
from layerweave.tool.builtin.usage.records.dispatch import dispatch, dispatch_in_session
from layerweave.tool.builtin.usage.records import save as checked_save
from layerweave.tool.builtin.usage.undo.service import undo_operation, undo_operation_in_session
from layerweave.tool.builtin.usage.history.service import read_history
from layerweave.tool.builtin.usage.history.cli import format_history
from layerweave.support.commands import command_help


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        with transaction(self.c) as w:
            self.p = w.create("project", {"name": "source"})["id"]
            self.q = w.create("project", {"name": "target"})["id"]
            self.layer = w.create("layer", {"type": "text", "config_ref": "layers/text.toml"}, project_id=self.p)["id"]
            self.other = w.create("layer", {"type": "text", "config_ref": "layers/text.toml"}, project_id=self.q)["id"]

    def payload(self, text="hello"):
        return {"config_ref": "objects/text.toml", "information": {"text": text}}

    def obj(self, begin=0, end=2):
        with transaction(self.c) as w:
            return w.create("object", {**self.payload(), "layer": self.layer, "begin": begin, "end": end}, project_id=self.p)

    def snapshot(self):
        return list(self.c.iterdump())

    def test_append_and_shift_commit_once_and_checker_runs_once_after_commit(self):
        checked = []
        def checker(changes, read):
            self.assertFalse(self.c.in_transaction)
            checked.append(changes)
            return []
        def work(w):
            w.update("project", self.p, {"tips": "one operation"})
            first = append_object_in_session(w, self.p, self.layer, self.payload(), duration=2)
            second = append_object_in_session(w, self.p, self.layer, self.payload("second"), duration=3)
            moved = shift_objects_in_session(w, self.p, [first["id"], second["id"]], offset=1)
            return moved
        result = run_operation(self.c, work, checker=checker)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(checked), 1)
        self.assertEqual([(row["begin"], row["end"]) for row in result["data"]], [(1, 3), (3, 6)])
        logs = read_record(self.c, "change", filters={"operation_id": result["operation_id"]})
        self.assertEqual(len(logs), 5)
        self.assertEqual(len(result["operation"]["numbering"]), 2)
        self.assertTrue(undo_operation(self.c, result["operation_id"])["ok"])
        self.assertEqual(read_record(self.c, "object", project_id=self.p), [])

    def test_later_session_tool_failure_rolls_back_records_numbers_and_logs(self):
        before = self.snapshot()
        def work(w):
            w.update("project", self.p, {"tips": "must rollback"})
            append_object_in_session(w, self.p, self.layer, self.payload(), duration=2)
            set_duration_in_session(w, self.p, 99999, 4)
        result = run_operation(self.c, work)
        self.assertFalse(result["ok"])
        self.assertNotIn("data", result)
        self.assertNotIn("numbering", result["operation"])
        self.assertEqual(self.snapshot(), before)

    def test_accidentally_nested_standalone_tool_propagates_and_rolls_back_outer(self):
        before = self.snapshot()
        def work(w):
            w.update("project", self.p, {"tips": "outer"})
            return append_object(self.c, self.p, self.layer, self.payload(), duration=2)
        result = run_operation(self.c, work)
        self.assertFalse(result["ok"], result)
        self.assertIn("_in_session", result["error"]["message"])
        self.assertEqual(self.snapshot(), before)

    def test_transaction_context_receives_nested_error_directly(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "_in_session"):
            with transaction(self.c) as w:
                w.update("project", self.p, {"tips": "outer"})
                dispatch(self.c, {"action": "read", "kind": "project", "id": self.p})
        self.assertEqual(self.snapshot(), before)

    def test_external_pending_transaction_still_returns_failure_without_committing_it(self):
        self.c.execute("UPDATE projects SET tips='pending' WHERE id=?", (self.p,))
        result = append_object(self.c, self.p, self.layer, self.payload(), duration=1)
        self.assertFalse(result["ok"])
        self.assertTrue(self.c.in_transaction)
        self.c.rollback()

    def test_closed_or_foreign_session_is_rejected(self):
        with transaction(self.c) as old:
            pass
        with self.assertRaisesRegex(ValueError, "写会话"):
            append_object_in_session(old, self.p, self.layer, self.payload(), duration=1)
        with closing(open_database(":memory:")) as other:
            other.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            with transaction(other):
                with self.assertRaisesRegex(ValueError, "写会话"):
                    append_object_in_session(old, self.p, self.layer, self.payload(), duration=1)

    def test_allocation_only_is_committed_and_does_not_create_business_history(self):
        before = read_record(self.c, "project", id=self.p)["max_id"]
        result = run_operation(self.c, lambda w: allocate("project_entities", data={"project_id": self.p}))
        self.assertTrue(result["ok"] and result["applied"])
        self.assertEqual(result["operation"]["status"], "committed")
        self.assertEqual(result["operation"]["changes"], [])
        detail = result["operation"]["numbering"][0]
        self.assertEqual(detail, {"counter": {"kind": "project", "project_id": None, "id": self.p, "field": "max_id"},
                                 "before": before, "after": before + 1, "entry": "project_entities",
                                 "rule": "project_entity", "identity": {"project_id": self.p, "id": before + 1}})
        self.assertEqual(read_record(self.c, "change", filters={"operation_id": result["operation_id"]}), [])
        self.assertEqual(result["checks"]["reason"], "no_changes")
        text = format_feedback(result)
        self.assertIn("[发号成功]", text)
        self.assertNotIn("[无变化]", text)
        self.assertIn("不会回收编号", text)

    def test_direct_increment_is_also_reported(self):
        entry = numbering_entries(self.c)["project_entities"]
        result = run_operation(self.c, lambda w: increment(entry, {"project_id": self.p}))
        self.assertTrue(result["applied"])
        self.assertIn("[发号成功]", format_feedback(result))
        self.assertNotIn("identity", result["operation"]["numbering"][0])

    def test_read_request_after_explicit_allocation_preserves_outer_applied(self):
        def request(read):
            allocate("project_entities", data={"project_id": self.p})
            return {"action": "read", "kind": "project", "id": self.p}
        result = dispatch(self.c, request)
        self.assertTrue(result["applied"])
        self.assertEqual(result["action"], "read")
        self.assertEqual(result["operation"]["status"], "committed")

    def test_numbering_property_is_snapshot_and_unchanged_operations_stay_unchanged(self):
        with transaction(self.c) as w:
            allocate("project_entities", data={"project_id": self.p})
            exposed = w.numbering
            exposed[0]["after"] = -1
            exposed.clear()
            self.assertGreater(w.numbering[0]["after"], 0)
        result = run_operation(self.c, lambda w: {"ok": False, "meaning": "ordinary business data"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["operation"], {"status": "unchanged", "changes": []})

    def test_dispatch_in_session_returns_data_and_composes_with_editing(self):
        def work(w):
            layer = dispatch_in_session(w, {"action": "create", "kind": "layer", "project_id": self.p,
                                            "data": {"config_ref": "layers/text.toml"}})
            obj = append_object_in_session(w, self.p, layer["id"], self.payload(), duration=1)
            records = dispatch_in_session(w, [
                {"action": "update", "kind": "object", "project_id": self.p, "id": obj["id"], "data": {"tips": "changed"}},
                {"action": "read", "kind": "object", "project_id": self.p, "id": obj["id"]}])
            return records
        result = run_operation(self.c, work)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"][0], result["data"][1])
        self.assertEqual(result["data"][1]["tips"], "changed")

    def test_session_model_saving_returns_ids_without_mutating_input(self):
        obj = Text(layer=self.layer, information={"text": "child"})
        layer = TextLayer(objects=[obj])
        def work(w):
            saved = save_layer_in_session(w, self.p, layer)
            self.assertIsNone(layer.id)
            self.assertIsNone(obj.id)
            extra = save_object_in_session(w, self.p, {**self.payload("extra"), "layer": saved["id"]})
            return saved, extra
        result = run_operation(self.c, work)
        self.assertTrue(result["ok"], result)
        self.assertIsNone(layer.id)
        self.assertIsNone(obj.id)
        self.assertEqual(result["data"][1]["layer"], result["data"][0]["id"])

    def test_failed_session_model_save_does_not_backfill_rolled_back_ids(self):
        layer = TextLayer(objects=[Text(layer=self.layer, information={"text": "child"})])
        before = self.snapshot()
        def work(w):
            save_layer_in_session(w, self.p, layer)
            raise RuntimeError("later failure")
        self.assertFalse(run_operation(self.c, work)["ok"])
        self.assertIsNone(layer.id)
        self.assertIsNone(layer.objects[0].id)
        self.assertEqual(self.snapshot(), before)

    def test_checked_save_names_are_explicit_and_standalone_backfill_remains(self):
        self.assertFalse(hasattr(checked_save, "save_layer"))
        self.assertFalse(hasattr(checked_save, "save_object"))
        layer = TextLayer()
        result = checked_save.save_layer_with_checks(self.c, self.p, layer)
        self.assertTrue(result["ok"], result)
        self.assertEqual(layer.id, result["data"]["id"])
        bad = checked_save.save_object_with_checks(self.c, self.p, {**self.payload(42), "layer": layer.id})
        self.assertTrue(bad["ok"])
        self.assertTrue(bad["checks"]["issues"])

    def test_position_and_copy_session_functions(self):
        first, second = self.obj(0, 2), self.obj(4, 5)
        def work(w):
            clone = copy_object_in_session(w, self.p, first["id"], begin=8)
            changed = set_duration_in_session(w, self.p, clone["id"], 3)
            self.assertEqual(changed["end"], 11)
            arranged = arrange_objects_in_session(w, self.p, self.layer,
                                                  object_ids=[first["id"], second["id"], clone["id"]], start=0)
            self.assertEqual([row["begin"] for row in arranged], [0, 2, 3])
            aligned = align_objects_in_session(w, self.p, [clone["id"]], position=10)
            self.assertEqual(aligned[0]["end"], 13)
            return clone
        self.assertTrue(run_operation(self.c, work)["ok"])

    def test_split_and_gap_can_share_the_same_operation(self):
        row = self.obj(0, 4)
        def work(w):
            split = split_object_in_session(w, self.p, row["id"], first_information={"text": "first"},
                                            cuts=[{"at": 2, "information": {"text": "second"}}])
            gap = insert_gap_in_session(w, self.p, at=2, length=1, layer_id=self.layer)
            return split, gap
        result = run_operation(self.c, work)
        self.assertTrue(result["ok"], result)
        self.assertEqual([(r["begin"], r["end"]) for r in read_record(self.c, "object", project_id=self.p)], [(0, 2), (3, 5)])
        self.assertTrue(undo_operation(self.c, result["operation_id"])["ok"])
        self.assertEqual(len(read_record(self.c, "object", project_id=self.p)), 1)

    def test_subtree_copy_transfer_delete_session_functions(self):
        self.obj()
        def work(w):
            copied = copy_subtree_in_session(w, self.p, self.layer, name="copy")
            transferred = transfer_subtree_in_session(w, self.p, copied["layer_id"], self.q, mode="cut")
            deleted = delete_subtree_in_session(w, self.q, transferred["layer_id"])
            return deleted
        result = run_operation(self.c, work)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(read_record(self.c, "layer", project_id=self.p)), 1)
        self.assertEqual(len(read_record(self.c, "layer", project_id=self.q)), 1)

    def test_object_transfer_and_undo_in_session(self):
        row = self.obj()
        transferred = run_operation(self.c, lambda w: transfer_objects_in_session(
            w, self.p, [row["id"]], self.q, self.other, mode="cut"))
        self.assertTrue(transferred["ok"], transferred)
        def work(w):
            restored = undo_operation_in_session(w, transferred["operation_id"])
            w.update("project", self.p, {"tips": "restored"})
            return restored
        result = run_operation(self.c, work)
        self.assertTrue(result["ok"], result)
        self.assertIsNotNone(read_record(self.c, "object", project_id=self.p, id=row["id"]))
        history = read_history(self.c, operation_id=result["operation_id"])
        self.assertIsNone(history["items"][0]["undo_of"])
        self.assertEqual(history["items"][0]["undo_of_operations"], [transferred["operation_id"]])
        self.assertIn("本操作包含撤销", format_history(history))

    def test_post_commit_checker_failure_does_not_undo_session_tools(self):
        def checker(changes, read):
            raise ValueError("test checker failure")
        result = run_operation(self.c, lambda w: append_object_in_session(
            w, self.p, self.layer, self.payload(), duration=1), checker=checker)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["checks"]["status"], "failed")
        self.assertIsNotNone(read_record(self.c, "object", project_id=self.p, id=result["data"]["id"]))

    def test_multiple_undo_targets_keep_each_origin_and_can_be_redone_together(self):
        first = run_operation(self.c, lambda w: w.update("project", self.p, {"tips": "first"}))
        second = run_operation(self.c, lambda w: w.update("project", self.p, {"tips": "second"}))
        def work(w):
            undo_operation_in_session(w, second["operation_id"])
            undo_operation_in_session(w, first["operation_id"])
        combined = run_operation(self.c, work)
        self.assertTrue(combined["ok"], combined)
        self.assertEqual(read_record(self.c, "project", id=self.p)["tips"], "")
        history = read_history(self.c, operation_id=combined["operation_id"])["items"][0]
        self.assertIsNone(history["undo_of"])
        self.assertEqual(history["undo_of_operations"], sorted([first["operation_id"], second["operation_id"]]))
        self.assertEqual([row["undo_of"] for row in history["changes"]], [second["operation_id"], first["operation_id"]])
        self.assertTrue(undo_operation(self.c, combined["operation_id"])["ok"])
        self.assertEqual(read_record(self.c, "project", id=self.p)["tips"], "second")

    def test_help_parameters_match_initialization_and_actual_discovery_root(self):
        from importlib import import_module
        from inspect import signature
        initialize = command_help("initialize_database")["items"][0]
        self.assertTrue(initialize["parameters"]["path"]["required"])
        self.assertNotIn("database", initialize["parameters"])
        self.assertIn("database", initialize["parameters"]["path"]["description"])
        help_entry = command_help("command_help")["items"][0]
        self.assertIn("tool/builtin", help_entry["parameters"]["source_root"]["description"])
        session_route = command_help("append_object")["items"][0]["session_entrypoint"]
        self.assertEqual(session_route, "layerweave.tool.builtin.usage.editing.objects:append_object_in_session")
        entries = command_help([item["name"] for item in command_help()["items"]])["items"]
        routes = [entry["session_entrypoint"] for entry in entries if "session_entrypoint" in entry]
        self.assertEqual(len(routes), 16)
        for route in routes:
            module, name = route.split(":")
            self.assertEqual(next(iter(signature(getattr(import_module(module), name)).parameters)), "write", route)


if __name__ == "__main__":
    unittest.main()

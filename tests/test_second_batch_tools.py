"""第二批写入工具：位置含义、原子修改、编号、并发接续与命令行。"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from functools import partial
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from threading import Barrier
import unittest

from tool.builtin.usage.records.dispatch import dispatch
from support.api import open_database, read_record
from support.configuration.loader import DEFAULT_ROOT
from support.storage.database import SCHEMA_PATH
from tool.builtin.usage.validation.runner import check_changes
from tool.builtin.usage.editing.objects import append_object, copy_object
from tool.builtin.usage.editing.positions import align_objects, arrange_objects, set_duration, shift_objects


class SecondBatchToolsTests(unittest.TestCase):
    def setUp(self):
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-write-tools-")
        self.addCleanup(self.temp.cleanup)
        self.project_id = self.create("project", {})["id"]
        self.layer_id = self.layer()

    def create(self, kind, data, *, project_id=None):
        result = dispatch(self.connection, {"action": "create", "kind": kind, "data": data,
                                           **({"project_id": project_id} if project_id is not None else {})}, checker=None)
        self.assertTrue(result["ok"], result)
        return result["data"]

    def layer(self, *, project_id=None, **data):
        return self.create("layer", {"type": "Layer", "config_ref": "layers/base.toml", **data},
                           project_id=project_id or self.project_id)["id"]

    def obj(self, begin=0, end=0, *, project_id=None, layer_id=None, **data):
        return self.create("object", {"layer": layer_id or self.layer_id, "config_ref": "objects/text.toml",
                                       "begin": begin, "end": end, "information": {"text": "内容"}, **data},
                           project_id=project_id or self.project_id)["id"]

    def row(self, id, *, project_id=None):
        return read_record(self.connection, "object", project_id=project_id or self.project_id, id=id)

    def span(self, id):
        row = self.row(id)
        return row["begin"], row["end"]

    def logs(self, result):
        return read_record(self.connection, "change", filters={"operation_id": result["operation_id"]})

    def new_data(self):
        return {"config_ref": "objects/text.toml", "information": {"text": "新增"}}

    def test_append_empty_and_maximum_end_not_last_start(self):
        first = append_object(self.connection, self.project_id, self.layer_id, self.new_data(), duration=2)
        self.assertEqual((first["data"]["begin"], first["data"]["end"]), (0, 2))
        self.obj(0, 10)
        self.obj(5, 7)
        data = self.new_data()
        result = append_object(self.connection, self.project_id, self.layer_id, data, duration=3)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.span(result["id"]), (10, 13))
        self.assertNotIn("id", data)
        self.assertEqual(len(self.logs(result)), 1)

    def test_append_negative_positions_and_explicit_anchor(self):
        first = append_object(self.connection, self.project_id, self.layer_id, self.new_data(), duration=2, empty_start=-8)
        second = append_object(self.connection, self.project_id, self.layer_id, self.new_data(), duration=1)
        self.assertEqual(self.span(second["id"]), (-6, -5))
        self.obj(0, 20)
        result = append_object(self.connection, self.project_id, self.layer_id, self.new_data(), duration=1, after_id=first["id"])
        self.assertEqual(self.span(result["id"]), (-6, -5))

    def test_append_rejects_foreign_layer_anchor_without_allocating(self):
        other = self.layer()
        anchor = self.obj(layer_id=other)
        before = read_record(self.connection, "project", id=self.project_id)["max_id"]
        for after_id in (anchor, 999):
            result = append_object(self.connection, self.project_id, self.layer_id, self.new_data(), duration=1, after_id=after_id)
            self.assertFalse(result["ok"])
            self.assertEqual(self.logs(result), [])
        self.assertEqual(read_record(self.connection, "project", id=self.project_id)["max_id"], before)

    def test_arrange_current_order_and_requested_subset_order(self):
        a, b, untouched = self.obj(2, 4), self.obj(8, 11), self.obj(100, 105)
        result = arrange_objects(self.connection, self.project_id, self.layer_id, object_ids=[a, b])
        self.assertTrue(result["ok"], result)
        self.assertEqual((self.span(a), self.span(b), self.span(untouched)), ((2, 4), (4, 7), (100, 105)))
        result = arrange_objects(self.connection, self.project_id, self.layer_id, object_ids=[b, a, str(b)], start=-2)
        self.assertEqual([item["id"] for item in result["results"]], [b, a])
        self.assertEqual((self.span(b), self.span(a)), ((-2, 1), (1, 3)))
        self.assertEqual(self.span(untouched), (100, 105))
        result = arrange_objects(self.connection, self.project_id, self.layer_id)
        self.assertEqual([item["id"] for item in result["results"]], [b, a, untouched])
        self.assertEqual(self.span(untouched), (3, 8))

    def test_shift_selection_duration_metadata_and_bindings_are_preserved(self):
        a, b, untouched = self.obj(1, 4, tips="保留"), self.obj(5, 5), self.obj(10, 12)
        bind = self.create("bind", {"source_kind": "object", "source_project_id": self.project_id, "source_id": a,
                                    "target_kind": "object", "target_project_id": self.project_id, "target_id": b})
        before = self.row(a)
        result = shift_objects(self.connection, self.project_id, [a, b, a], offset=-3)
        self.assertTrue(result["ok"], result)
        self.assertEqual((self.span(a), self.span(b), self.span(untouched)), ((-2, 1), (2, 2), (10, 12)))
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual({k: v for k, v in self.row(a).items() if k not in {"begin", "end"}},
                         {k: v for k, v in before.items() if k not in {"begin", "end"}})
        self.assertEqual(read_record(self.connection, "bind", id=bind["id"]), bind)

    def test_layer_selection_and_project_scope(self):
        a = self.obj(1, 3)
        other_project = self.create("project", {})["id"]
        other_layer = self.layer(project_id=other_project)
        foreign = self.obj(10, 12, project_id=other_project, layer_id=other_layer)
        self.assertEqual(a, foreign)
        result = shift_objects(self.connection, self.project_id, offset=2, layer_id=self.layer_id)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.span(a), (3, 5))
        self.assertEqual(self.row(foreign, project_id=other_project)["begin"], 10)
        self.assertFalse(shift_objects(self.connection, self.project_id, offset=1)["ok"])

    def test_align_start_and_end_across_explicitly_selected_layers(self):
        a = self.obj(1, 4)
        other = self.layer()
        b = self.obj(6, 8, layer_id=other)
        start = align_objects(self.connection, self.project_id, [a, b], position=10)
        self.assertTrue(start["ok"], start)
        self.assertEqual((self.span(a), self.span(b)), ((10, 13), (10, 12)))
        end = align_objects(self.connection, self.project_id, [a, b], position=10, edge="end")
        self.assertTrue(end["ok"], end)
        self.assertEqual((self.span(a), self.span(b)), ((7, 10), (8, 10)))

    def test_duration_keeps_start_and_uses_post_commit_rules(self):
        a, b = self.obj(5, 9), self.obj(10, 12)
        zero = set_duration(self.connection, self.project_id, a, 0)
        self.assertTrue(zero["ok"], zero)
        self.assertEqual(self.span(a), (5, 5))
        negative = set_duration(self.connection, self.project_id, a, -2)
        self.assertTrue(negative["ok"], negative)
        self.assertTrue(negative["applied"])
        self.assertEqual(self.span(a), (5, 3))
        self.assertTrue(any(issue["rule"] == "begin_le_end" for issue in negative["checks"]["issues"]))
        self.assertEqual(self.span(b), (10, 12))

    def test_instant_tail_and_alignment_report_overlap_without_guessing_gap(self):
        configs = Path(self.temp.name) / "configs"
        shutil.copytree(DEFAULT_ROOT, configs)
        (configs / "layers/track.toml").write_text('[layer]\ntype="track"\nclass="fixture_types:TrackLayer"\nextends="base.toml"\n[layer.constraint]\noverlap=false\n', encoding="utf-8")
        checker = partial(check_changes, config_root=configs)
        track = self.layer(type="track", config_ref="layers/track.toml")
        self.obj(3, 3, layer_id=track)
        result = append_object(self.connection, self.project_id, track, self.new_data(), duration=2, checker=checker)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.span(result["id"]), (3, 5))
        self.assertTrue(any(issue["rule"] == "overlap" for issue in result["checks"]["issues"]))
        aligned = align_objects(self.connection, self.project_id, position=10, layer_id=track, checker=checker)
        self.assertTrue(aligned["ok"], aligned)
        self.assertTrue(any(issue["rule"] == "overlap" for issue in aligned["checks"]["issues"]))

    def test_noops_empty_selections_and_invalid_calculation_inputs(self):
        a = self.obj(1, 4)
        logs = len(read_record(self.connection, "change"))
        for result in (shift_objects(self.connection, self.project_id, [a], offset=0),
                       shift_objects(self.connection, self.project_id, [], offset=10),
                       arrange_objects(self.connection, self.project_id, self.layer_id),
                       set_duration(self.connection, self.project_id, a, 3)):
            self.assertTrue(result["ok"], result)
            self.assertFalse(result["applied"])
            self.assertEqual(result["checks"]["reason"], "no_changes")
        for offset in (True, "3", float("inf"), float("nan")):
            self.assertFalse(shift_objects(self.connection, self.project_id, [a], offset=offset)["ok"])
        self.assertFalse(shift_objects(self.connection, self.project_id, str(a), offset=1)["ok"])
        self.assertFalse(align_objects(self.connection, self.project_id, [a], position=2, edge="both")["ok"])
        self.assertEqual(len(read_record(self.connection, "change")), logs)

    def test_missing_or_uncalculable_object_does_not_partially_edit_selection(self):
        a, bad = self.obj(1, 3), self.obj("bad", 4)
        for ids in ([a, 999], [a, bad]):
            result = shift_objects(self.connection, self.project_id, ids, offset=10)
            self.assertFalse(result["ok"])
            self.assertEqual(self.span(a), (1, 3))
            self.assertEqual(self.logs(result), [])
        other = self.layer()
        foreign = self.obj(layer_id=other)
        self.assertFalse(arrange_objects(self.connection, self.project_id, self.layer_id, object_ids=[a, foreign])["ok"])

    def test_later_log_failure_rolls_back_entire_operation(self):
        a, b = self.obj(1, 3), self.obj(4, 6)
        self.connection.execute(
            f"CREATE TRIGGER reject_second BEFORE INSERT ON changes WHEN NEW.kind='object' AND NEW.target_id={b} "
            "BEGIN SELECT RAISE(ABORT, 'test failure'); END"
        )
        result = shift_objects(self.connection, self.project_id, [a, b], offset=10)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["request_index"], 1)
        self.assertEqual((self.span(a), self.span(b)), ((1, 3), (4, 6)))
        self.assertEqual(self.logs(result), [])

    def test_checker_once_after_commit_and_shared_operation_id(self):
        a, b = self.obj(1, 3), self.obj(4, 6)
        calls = []
        def checker(changes, read):
            self.assertFalse(self.connection.in_transaction)
            calls.append(changes)
            self.assertEqual(read("object", project_id=self.project_id, id=a)["begin"], 11)
            raise RuntimeError("checker failed")
        result = shift_objects(self.connection, self.project_id, [a, b], offset=10, checker=checker)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["checks"]["status"], "failed")
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.logs(result)), 2)
        self.assertEqual({change["operation_id"] for change in calls[0]}, {result["operation_id"]})

    def test_copy_preserves_content_config_and_allocates_id_without_bindings(self):
        source = self.obj(2, 5, name="原件", tips="说明", config_ref="objects/missing-alias.toml",
                          information={"text": "原文", "extra": [1, True, {"nested": "值"}]})
        binding = self.create("bind", {"source_kind": "object", "source_project_id": self.project_id, "source_id": source,
                                       "target_kind": "layer", "target_project_id": self.project_id, "target_id": self.layer_id})
        before = self.row(source)
        result = copy_object(self.connection, self.project_id, source)
        self.assertTrue(result["ok"], result)
        self.assertNotEqual(result["id"], source)
        self.assertEqual({k: v for k, v in result["data"].items() if k != "id"}, {k: v for k, v in before.items() if k != "id"})
        self.assertEqual(result["checks"]["status"], "partial")
        self.assertEqual(read_record(self.connection, "bind"), [binding])
        self.assertEqual(self.row(source), before)
        dispatch(self.connection, {"action": "update", "kind": "object", "project_id": self.project_id,
                                   "id": result["id"], "data": {"information": {"text": "副本修改"}}}, checker=None)
        self.assertEqual(self.row(source)["information"]["text"], "原文")

    def test_copy_new_start_destination_and_append(self):
        source = self.obj(5, 8)
        target_layer = self.layer()
        self.obj(0, 10, layer_id=target_layer)
        copy = copy_object(self.connection, self.project_id, source, layer_id=target_layer, begin=-2, name="副本")
        self.assertEqual(self.span(copy["id"]), (-2, 1))
        self.assertEqual(copy["data"]["name"], "副本")
        appended = copy_object(self.connection, self.project_id, source, layer_id=target_layer, append=True)
        self.assertEqual(self.span(appended["id"]), (10, 13))
        self.assertEqual(self.span(source), (5, 8))
        self.assertFalse(copy_object(self.connection, self.project_id, source, begin=1, append=True)["ok"])
        counter = read_record(self.connection, "project", id=self.project_id)["max_id"]
        self.assertFalse(copy_object(self.connection, self.project_id, source, layer_id=999)["ok"])
        self.assertEqual(read_record(self.connection, "project", id=self.project_id)["max_id"], counter)

    def test_request_factory_holds_write_transaction_and_preserves_caller_transaction(self):
        a = self.obj(1, 3)
        statements, calls = [], []
        def plan(read):
            self.assertTrue(self.connection.in_transaction)
            calls.append(True)
            return {"action": "update", "kind": "object", "project_id": self.project_id, "id": a,
                    "data": {"begin": read("object", project_id=self.project_id, id=a)["begin"] + 1}}
        self.connection.set_trace_callback(statements.append)
        result = dispatch(self.connection, plan)
        self.connection.set_trace_callback(None)
        self.assertTrue(result["ok"], result)
        self.assertEqual(calls, [True])
        self.assertEqual(statements[0], "BEGIN IMMEDIATE")
        self.connection.execute("UPDATE projects SET tips='pending'")
        result = dispatch(self.connection, plan)
        self.assertFalse(result["ok"])
        self.assertEqual(calls, [True])
        self.assertTrue(self.connection.in_transaction)
        self.connection.rollback()

    def test_concurrent_appends_read_tail_inside_the_write_transaction(self):
        database = Path(self.temp.name) / "concurrent.sqlite3"
        with closing(sqlite3.connect(database)) as copy:
            self.connection.backup(copy)
        barrier = Barrier(2)
        def append_once(index):
            with closing(open_database(database)) as connection:
                barrier.wait(timeout=10)
                return append_object(connection, self.project_id, self.layer_id,
                                     {"config_ref": "objects/text.toml", "name": str(index)}, duration=2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(append_once, (1, 2)))
        self.assertTrue(all(result["ok"] for result in results), results)
        self.assertEqual(sorted((result["data"]["begin"], result["data"]["end"]) for result in results), [(0, 2), (2, 4)])
        self.assertEqual(len({result["id"] for result in results}), 2)

    def test_write_cli_success_failure_and_noop_exit_codes(self):
        source = self.obj(1, 3)
        database = Path(self.temp.name) / "cli.sqlite3"
        with closing(sqlite3.connect(database)) as copy:
            self.connection.backup(copy)
        data_file = Path(self.temp.name) / "data.json"
        data_file.write_text(json.dumps(self.new_data(), ensure_ascii=False), encoding="utf-8")
        def run(module, *args):
            return subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", module,
                                   str(database), str(self.project_id), *map(str, args)],
                                  capture_output=True, text=True, encoding="utf-8")
        moved = run("tool.builtin.usage.editing.positions", "shift", "--ids", source, "--offset", 2)
        self.assertEqual(moved.returncode, 0, moved.stderr)
        self.assertEqual(json.loads(moved.stdout)["results"][0]["data"]["begin"], 3)
        noop = run("tool.builtin.usage.editing.positions", "shift", "--ids", source, "--offset", 0)
        self.assertEqual(noop.returncode, 0)
        self.assertFalse(json.loads(noop.stdout)["applied"])
        failed = run("tool.builtin.usage.editing.positions", "duration", 999, 1)
        self.assertEqual(failed.returncode, 1)
        self.assertFalse(json.loads(failed.stdout)["ok"])
        appended = run("tool.builtin.usage.editing.objects", "append", self.layer_id, 2, "--data-file", data_file)
        self.assertEqual(appended.returncode, 0, appended.stderr)
        self.assertEqual(json.loads(appended.stdout)["data"]["begin"], 5)
        copied = run("tool.builtin.usage.editing.objects", "copy", source, "--append")
        self.assertEqual(copied.returncode, 0, copied.stderr)
        self.assertEqual(json.loads(copied.stdout)["data"]["begin"], 7)

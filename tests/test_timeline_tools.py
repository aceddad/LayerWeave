"""分割、范围平移与真实空档的边界、显式内容、事务和命令行回归。"""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tool.builtin.usage.records.dispatch import dispatch
from tool.builtin.usage.editing.timeline import insert_gap, shift_objects, split_object
from support.api import open_database, read_record
from tool.builtin.usage.undo.service import undo_operation
from support.configuration.loader import DEFAULT_ROOT
from support.storage.database import SCHEMA_PATH
from tool.builtin.usage.editing.gaps import format_gap


class TimelineToolsTests(unittest.TestCase):
    def setUp(self):
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.p = self.call("create", "project", data={})["id"]
        self.l = self.layer()

    def call(self, action, kind, **args):
        if kind in {"layer", "object"}:
            args.setdefault("project_id", self.p)
        result = dispatch(self.c, {"action": action, "kind": kind, **args}, checker=None)
        self.assertTrue(result["ok"], result)
        return result

    def layer(self, **data):
        return self.call("create", "layer", data={"config_ref": "layers/text.toml", "axis": {"precision": 0.001}, **data})["id"]

    def obj(self, begin=10, end=20, **data):
        return self.call("create", "object", data={"layer": self.l, "config_ref": "objects/text.toml", "name": "原对象", "tips": "备注",
                         "begin": begin, "end": end, "information": {"text": "原内容"}, **data})["id"]

    def row(self, id):
        return read_record(self.c, "object", project_id=self.p, id=id)

    def span(self, id):
        row = self.row(id)
        return row["begin"], row["end"]

    def snapshot(self):
        return {table: [tuple(row) for row in self.c.execute(f'SELECT * FROM "{table}" ORDER BY 1, 2')]
                for table in ("projects", "layers", "objects", "binds", "changes", "sqlite_sequence")}

    def split(self, id, cuts, **kw):
        return split_object(self.c, self.p, id, first_information={"text": "A"}, cuts=cuts, **kw)

    def undo(self, result):
        undone = undo_operation(self.c, result["operation_id"])
        self.assertTrue(undone["ok"], undone)
        return undone

    def test_multi_cut_preserves_first_identity_all_bindings_and_metadata(self):
        id = self.obj()
        bind = self.call("create", "bind", data={"source_kind": "object", "source_project_id": self.p, "source_id": id,
                         "target_kind": "object", "target_project_id": self.p, "target_id": id})["data"]
        original = self.row(id)
        result = self.split(id, [{"at": 14, "information": {"text": "B"}}, {"at": 17, "information": {"text": "C"}}])
        self.assertTrue(result["ok"], result)
        rows = result["data"]["segments"]
        self.assertEqual(rows[0]["id"], id)
        self.assertEqual([(r["begin"], r["end"], r["information"]["text"]) for r in rows], [(10, 14, "A"), (14, 17, "B"), (17, 20, "C")])
        self.assertEqual(len({r["id"] for r in rows}), 3)
        for row in rows:
            self.assertEqual({k: row[k] for k in ("layer", "config_ref", "name", "tips")}, {k: original[k] for k in ("layer", "config_ref", "name", "tips")})
        self.assertEqual(read_record(self.c, "bind"), [bind])
        u = self.undo(result)
        self.assertEqual(self.row(id), original)
        self.undo(u)
        self.assertEqual([self.row(r["id"]) for r in rows], rows)

    def test_cuts_snap_and_cannot_be_outside_unsorted_or_merged_on_grid(self):
        id = self.obj(0, 1)
        for values in ([0], [1], [-1], [2], [0.8, 0.3], [0.4, 0.40001], [0.00001], [True], [float("inf")]):
            before = self.snapshot()
            result = self.split(id, [{"at": at, "information": {"text": "B"}} for at in values])
            self.assertFalse(result["ok"], result)
            self.assertEqual(self.snapshot(), before)
        result = self.split(id, [{"at": 0.30000000000000004, "information": {"text": "B"}}])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["cuts"][0]["actual"], 0.3)
        self.assertEqual(self.span(id), (0, 0.3))

    def test_empty_cuts_noop_and_missing_information_never_silently_copies(self):
        id = self.obj()
        before = self.snapshot()
        self.assertFalse(split_object(self.c, self.p, id, cuts=[])["applied"])
        for kwargs in ({"cuts": [{"at": 14, "information": {"text": "B"}}]},
                       {"first_information": {"text": "A"}, "cuts": [{"at": 14}]},
                       {"first_information": {"text": "A"}, "cuts": [{"at": 14, "information": None}]}):
            self.assertFalse(split_object(self.c, self.p, id, **kwargs)["ok"])
        self.assertEqual(self.snapshot(), before)
        instant = self.obj(3, 3)
        self.assertFalse(self.split(instant, [{"at": 3, "information": {}}])["ok"])

    def test_content_type_diagnostics_do_not_cancel_a_valid_partition(self):
        id = self.obj()
        result = split_object(self.c, self.p, id, first_information={}, cuts=[{"at": 14, "information": {"text": 12}}])
        self.assertTrue(result["ok"], result)
        self.assertEqual({i["code"] for i in result["checks"]["issues"]}, {"missing_field", "field_type"})

    def test_gap_moves_boundary_instants_but_leaves_objects_ending_at_cut(self):
        before = self.obj(20, 30)
        instant = self.obj(30, 30)
        later = self.obj(30, 35)
        result = insert_gap(self.c, self.p, at=30, length=2, layer_id=self.l)
        self.assertTrue(result["ok"], result)
        self.assertEqual((self.span(before), self.span(instant), self.span(later)), ((20, 30), (32, 32), (32, 37)))
        self.assertEqual(result["data"]["splits"], [])
        self.undo(result)
        self.assertEqual(self.span(later), (30, 35))

    def test_gap_requires_all_crossing_contents_and_reports_each_without_writes(self):
        a, b = self.obj(28, 34), self.obj(29, 35)
        self.obj(31, 32)
        before = self.snapshot()
        result = insert_gap(self.c, self.p, at=30, length=2, whole_project=True)
        self.assertFalse(result["ok"])
        self.assertEqual({r["object_id"] for r in result["error"]["required_splits"]}, {a, b})
        self.assertIn(f"对象 {a}", format_gap(result))
        self.assertEqual(self.snapshot(), before)

    def test_gap_splits_and_shifts_in_one_operation_with_undo_redo(self):
        crossing, later = self.obj(28, 34), self.obj(34, 40)
        original = [self.row(crossing), self.row(later)]
        result = insert_gap(self.c, self.p, at=30, length=2, split_contents=[
            {"object_id": crossing, "first_information": {"text": "前"}, "second_information": {"text": "后"}}], whole_project=True)
        self.assertTrue(result["ok"], result)
        parts = result["data"]["splits"][0]["segments"]
        self.assertEqual([(r["begin"], r["end"]) for r in parts], [(28, 30), (32, 36)])
        self.assertEqual(self.span(later), (36, 42))
        self.assertEqual(len(read_record(self.c, "change", filters={"operation_id": result["operation_id"]})), 3)
        u = self.undo(result)
        self.assertEqual([self.row(crossing), self.row(later)], original)
        self.undo(u)
        self.assertEqual(self.span(parts[1]["id"]), (32, 36))

    def test_gap_bad_or_stale_contents_and_failed_writes_roll_back_all(self):
        crossing, later = self.obj(28, 34), self.obj(34, 40)
        for supplied in ([{"object_id": crossing, "first_information": {}, "second_information": None}],
                         [{"object_id": later, "first_information": {}, "second_information": {}}]):
            before = self.snapshot()
            self.assertFalse(insert_gap(self.c, self.p, at=30, length=2, split_contents=supplied, whole_project=True)["ok"])
            self.assertEqual(self.snapshot(), before)
        self.c.execute(f"CREATE TRIGGER reject_later BEFORE UPDATE ON objects WHEN old.id={later} BEGIN SELECT RAISE(ABORT,'stop'); END")
        before = self.snapshot()
        result = insert_gap(self.c, self.p, at=30, length=2, split_contents=[{"object_id": crossing, "first_information": {}, "second_information": {}}], whole_project=True)
        self.assertFalse(result["ok"])
        self.assertEqual(self.snapshot(), before)

    def test_gap_and_shift_subtree_scopes_deduplicate_and_do_not_move_crossing_objects_by_filter(self):
        child = self.layer(father=self.l, axis=None)
        outside = self.layer()
        cross = self.obj(28, 34)
        a, b, other = self.obj(30, 32), self.obj(31, 33, layer=child), self.obj(30, 32, layer=outside)
        result = shift_objects(self.c, self.p, offset=2, layer_ids=[self.l, child], from_position=30)
        self.assertTrue(result["ok"], result)
        self.assertEqual({r["id"] for r in result["results"]}, {a, b})
        self.assertEqual((self.span(cross), self.span(a), self.span(b), self.span(other)), ((28, 34), (32, 34), (33, 35), (30, 32)))
        before = self.snapshot()
        self.assertFalse(insert_gap(self.c, self.p, at=30, length=2, layer_ids=[self.l, 999])["ok"])
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(insert_gap(self.c, self.p, at=30, length=2, layer_ids=[])["applied"])

    def test_each_axis_has_explicit_actual_gap_without_unit_conversion(self):
        coarse = self.layer(axis={"unit": "帧", "precision": 0.1})
        a, b = self.obj(1, 2), self.obj(1, 2, layer=coarse)
        result = insert_gap(self.c, self.p, at=0.25, length=0.24, whole_project=True)
        self.assertTrue(result["ok"], result)
        gaps = {g["layer_id"]: g for g in result["data"]["gaps"]}
        self.assertEqual((gaps[self.l]["begin"], gaps[self.l]["end"]), (0.25, 0.49))
        self.assertEqual((gaps[coarse]["begin"], gaps[coarse]["end"]), (0.3, 0.5))
        self.assertEqual((self.span(a), self.span(b)), ((1.24, 2.24), (1.2, 2.2)))

    def test_invalid_gap_length_and_unrepresentable_legacy_crossing_do_not_write(self):
        id = self.obj(20, 30)
        for length in (0, -1, 0.00001, True, float("nan")):
            before = self.snapshot()
            self.assertFalse(insert_gap(self.c, self.p, at=30, length=length, whole_project=True)["ok"])
            self.assertEqual(self.snapshot(), before)
        self.c.execute('UPDATE objects SET "end"=? WHERE project_id=? AND id=?', (30.00000000001, self.p, id))
        self.c.commit()
        before = self.snapshot()
        result = insert_gap(self.c, self.p, at=30, length=2, split_contents=[{"object_id": id, "first_information": {}, "second_information": {}}], whole_project=True)
        self.assertFalse(result["ok"])
        self.assertEqual(self.snapshot(), before)

    def test_overlap_is_diagnosed_after_shift_and_respects_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "configs"
            shutil.copytree(DEFAULT_ROOT, root)
            (root / "layers/track.toml").write_text('[layer]\ntype="track"\nclass="example:Track"\nextends="base.toml"\n[layer.constraint]\noverlap=false\n', encoding="utf-8")
            layer = self.layer(config_ref="layers/track.toml", type="track")
            self.obj(0, 2, layer=layer)
            moving = self.obj(3, 4, layer=layer)
            result = shift_objects(self.c, self.p, [moving], offset=-2, config_root=root)
            self.assertTrue(result["ok"], result)
            self.assertEqual(self.span(moving), (1, 2))
            self.assertTrue(any(i["rule"] == "overlap" for i in result["checks"]["issues"]))

    def test_manual_split_then_gap_matches_composed_gap(self):
        one, two = self.obj(28, 34), self.obj(28, 34)
        other = self.layer()
        self.call("update", "object", id=two, data={"layer": other})
        split = self.split(one, [{"at": 30, "information": {"text": "B"}}])
        self.assertTrue(split["ok"], split)
        result = insert_gap(self.c, self.p, at=30, length=2, layer_id=self.l)
        self.assertTrue(result["ok"], result)
        combined = insert_gap(self.c, self.p, at=30, length=2, layer_id=other, split_contents=[
            {"object_id": two, "first_information": {"text": "A"}, "second_information": {"text": "B"}}])
        self.assertTrue(combined["ok"], combined)
        first = [self.row(r["id"]) for r in split["data"]["segments"]]
        second = combined["data"]["splits"][0]["segments"]
        self.assertEqual([(r["begin"], r["end"], r["information"]) for r in first],
                         [(r["begin"], r["end"], r["information"]) for r in second])

    def test_cli_split_gap_and_shift_selection(self):
        id = self.obj()
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "data.sqlite3"
            with open_database(db) as c:
                self.c.backup(c)
            c.close()
            payload = Path(folder) / "parts.json"
            payload.write_text(json.dumps({"first_information": {"text": "A"}, "cuts": [{"at": 14, "information": {"text": "B"}}]}), encoding="utf-8")
            commands = [("split", [str(id), "--data-file", str(payload), "--json"]),
                        ("gaps", ["14", "2", "--project", "--json"]),
                        ("positions", ["shift", "--layer-ids", str(self.l), "--from-position", "16", "--offset", "1"])]
            for module, args in commands:
                run = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", f"tool.builtin.usage.editing.{module}", str(db), str(self.p), *args], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertTrue(json.loads(run.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()

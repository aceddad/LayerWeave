"""Shared layout persistence, copy remapping, undo and geometry without an open browser."""
from contextlib import closing
from pathlib import Path
import json
import tempfile
import unittest

from layerweave.support.api import initialize_database, open_database, transaction, read_record, table_specs, change_cursor
from layerweave.tool.builtin.view.layout import arrange, load_layout, layout_path, save_layout, layout_serial
from layerweave.tool.builtin.view.layout_geometry import geometry
from layerweave.tool.builtin.view.layout_store import STYLE, MEMBER
from layerweave.tool.builtin.view.data import project_view
from layerweave.tool.builtin.usage.exchange import export_project, import_project
from layerweave.tool.builtin.usage.undo.service import undo_operation


class SharedLayoutTests(unittest.TestCase):
    def test_frontend_geometry_contract(self):
        fixture = json.loads((Path(__file__).parents[1]/"fixtures/view-layout-geometry.json").read_text(encoding="utf-8"))
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                view = {**fixture["data"], "folds": case["folds"]}
                box = geometry(view, {k: case[k] for k in ("rows", "pps", "styles")})
                self.assertEqual({k: box[k] for k in ("width", "height")}, case["expected"])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = initialize_database(self.root / "project.sqlite3")
        self.c = open_database(self.db)
        self.addCleanup(self.c.close)
        with transaction(self.c) as w:
            self.p = w.create("project", {"name": "layout"})["id"]
            self.a = w.create("layer", {"name": "A", "type": "text", "config_ref": "layers/text.toml",
                "axis": {"unit": "序号", "precision": 1}}, project_id=self.p)["id"]
            self.b = w.create("layer", {"name": "B", "type": "text", "config_ref": "layers/text.toml",
                "axis": {"unit": "序号", "precision": 1}}, project_id=self.p)["id"]
            self.o = w.create("object", {"layer": self.a, "config_ref": "objects/text.toml",
                "begin": 0, "end": 10, "information": {"text": "A long paragraph\n" * 15}}, project_id=self.p)["id"]
            w.create("object", {"layer": self.b, "config_ref": "objects/text.toml",
                "begin": 0, "end": 5, "information": {"text": "B"}}, project_id=self.p)
        self.boards = [
            {"rows": [[self.a]], "x": 10, "y": 20, "pps": 30, "styles": {str(self.a): {"pps": 30, "lane_height": 100}}},
            {"rows": [[self.b]], "x": 900, "y": 300, "pps": 50, "styles": {str(self.b): {"pps": 50, "lane_height": 200}}},
        ]

    def test_show_is_read_only_and_has_geometry(self):
        before = change_cursor(self.c)
        result = arrange(self.db, self.p)
        self.assertEqual(len(result["boards"]), 1)
        box = result["boards"][0]
        self.assertGreater(box["width"], 0)
        self.assertGreater(box["height"], 0)
        self.assertEqual((box["x"], box["y"]), (0, 0))
        self.assertTrue(box["automatic"])
        self.assertNotIn(STYLE, table_specs(self.c))
        self.assertEqual(change_cursor(self.c), before)
        self.assertFalse(layout_path(self.db).exists())

    def test_database_layout_is_shared_and_resize_is_undoable(self):
        save_layout(self.db, self.p, self.boards, self.root/"one")
        before = read_record(self.c, "object", project_id=self.p, id=self.o)
        serial = layout_serial(self.db)
        result = arrange(self.db, self.p, "resize", root=self.a, width=1000, lane_height=180)
        box = next(b for b in result["boards"] if self.a in b["roots"])
        self.assertAlmostEqual(box["width"], 1000)
        self.assertEqual(box["height"], 248)
        self.assertEqual(read_record(self.c, "object", project_id=self.p, id=self.o), before)
        self.assertNotEqual(layout_serial(self.db), serial)
        other = arrange(self.db, self.p, state_root=self.root/"other")
        self.assertEqual(other["boards"], result["boards"])
        self.assertTrue(undo_operation(self.c, result["operation_id"])["ok"])
        restored = arrange(self.db, self.p)["boards"][0]
        self.assertEqual(restored["styles"][str(self.a)]["lane_height"], 100)

    def test_merge_precedence_and_split_restore_member_preferences(self):
        save_layout(self.db, self.p, self.boards)
        merged = arrange(self.db, self.p, "merge", root=self.b, target=self.a, side="above")
        board = merged["boards"][0]
        self.assertEqual(board["roots"], [self.b, self.a])
        self.assertEqual(board["pps"], 50)
        self.assertEqual(board["height"], 376)
        split = arrange(self.db, self.p, "split", root=self.b)
        by_root = {b["roots"][0]: b for b in split["boards"]}
        self.assertEqual(by_root[self.a]["pps"], 30)
        self.assertEqual(by_root[self.b]["pps"], 50)
        joined = arrange(self.db, self.p, "merge", root=self.b, target=self.a, side="right")["boards"][0]
        self.assertEqual(joined["pps"], 30)
        self.assertEqual(joined["height"], 192)  # shared root track uses left row height
        self.assertEqual(joined["styles"][str(self.b)]["lane_height"], 200)

    def test_copy_into_shifted_project_remaps_both_tables(self):
        save_layout(self.db, self.p, self.boards)
        arrange(self.db, self.p, "merge", root=self.b, target=self.a, side="right")
        doc = export_project(self.c, self.p, op="add")
        with transaction(self.c) as w:
            target = w.create("project", {"name": "copy"})["id"]
            w.create("layer", {"name": "seed", "type": "text", "config_ref": "layers/text.toml"}, project_id=target)
        copied = import_project(self.c, doc, project_id=target)
        self.assertTrue(copied["ok"], copied)
        layers = {l["name"]:l["id"] for l in read_record(self.c, "layer", project_id=target)}
        self.assertNotEqual(layers["A"], self.a)
        members = read_record(self.c, MEMBER, project_id=target)
        self.assertEqual({m["id"] for m in members}, {layers["A"], layers["B"]})
        self.assertEqual({m["anchor_id"] for m in members}, {layers["A"]})
        box = next(b for b in arrange(self.db, target)["boards"] if layers["A"] in b["roots"])
        self.assertEqual(box["roots"], [layers["A"], layers["B"]])
        self.assertEqual((box["x"], box["y"], box["pps"]), (10, 20, 30))

    def test_resize_mixed_heights_reaches_target_even_when_one_row_hits_minimum(self):
        save_layout(self.db, self.p, self.boards)
        arrange(self.db, self.p, "merge", root=self.b, target=self.a, side="below")
        box = arrange(self.db, self.p, "resize", root=self.a, height=140)["boards"][0]
        self.assertAlmostEqual(box["height"], 140, places=6)
        self.assertAlmostEqual(box["styles"][str(self.a)]["lane_height"], 24)
        self.assertAlmostEqual(box["styles"][str(self.b)]["lane_height"], 40, places=6)

    def test_partial_copy_keeps_style_when_group_anchor_is_outside_selection(self):
        save_layout(self.db, self.p, self.boards)
        arrange(self.db, self.p, "merge", root=self.b, target=self.a, side="right")
        doc = export_project(self.c, self.p, op="add", layer_ids=[self.b])
        result = import_project(self.c, doc, new_project=True)
        self.assertTrue(result["ok"], result)
        target = result["data"]["project_id"]
        self.assertEqual(len(read_record(self.c, STYLE, project_id=target)), 1)
        self.assertEqual(read_record(self.c, MEMBER, project_id=target), [])
        box = arrange(self.db, target)["boards"][0]
        self.assertEqual(box["pps"], 50)
        self.assertEqual(next(iter(box["styles"].values()))["lane_height"], 200)

    def test_axis_change_detaches_member_without_losing_its_size(self):
        save_layout(self.db, self.p, self.boards)
        arrange(self.db, self.p, "merge", root=self.b, target=self.a, side="right")
        with transaction(self.c) as w:
            w.update("layer", self.b, {"axis": {"unit": "页", "precision": 1}}, project_id=self.p)
        boxes = arrange(self.db, self.p)["boards"]
        self.assertEqual(len(boxes), 2)
        detached = next(b for b in boxes if self.b in b["roots"])
        self.assertEqual(detached["pps"], 50)
        self.assertEqual(detached["styles"][str(self.b)]["lane_height"], 200)
        self.assertEqual(set(next(b for b in boxes if self.a in b["roots"])["styles"]), {str(self.a)})
        resized = arrange(self.db, self.p, "resize", root=self.a, lane_height=80)["boards"]
        self.assertEqual(next(b for b in resized if self.b in b["roots"])["styles"][str(self.b)]["lane_height"], 200)

    def test_legacy_is_only_read_until_explicit_migrate_then_database_wins(self):
        state = self.root/"legacy"
        path = layout_path(self.db, state)
        path.parent.mkdir()
        raw = json.dumps({"projects": {str(self.p): {"boards": self.boards}}}).encode()
        path.write_bytes(raw)
        before = change_cursor(self.c)
        self.assertEqual(arrange(self.db, self.p, state_root=state)["boards"][0]["x"], 10)
        self.assertEqual(change_cursor(self.c), before)
        migrated = arrange(self.db, self.p, "migrate", state_root=state)
        self.assertIn("operation_id", migrated)
        self.assertEqual(path.read_bytes(), raw)
        arrange(self.db, self.p, "move", root=self.a, x=300, y=400)
        self.assertEqual(arrange(self.db, self.p, state_root=state)["boards"][0]["x"], 300)
        reset = arrange(self.db, self.p, "reset", state_root=state)
        self.assertEqual(len(reset["boards"]), 1)
        self.assertEqual(reset["boards"][0]["x"], 0)
        self.assertTrue(undo_operation(self.c, reset["operation_id"])["ok"])
        self.assertEqual(arrange(self.db, self.p, state_root=state)["boards"][0]["x"], 300)

    def test_place_avoids_neighbor_but_move_can_overlap(self):
        save_layout(self.db, self.p, self.boards)
        placed = arrange(self.db, self.p, "place", root=self.b, target=self.a, side="right", gap=48)
        a,b = placed["boards"]
        self.assertEqual(b["x"], a["x"]+a["width"]+48)
        moved = arrange(self.db, self.p, "move", root=self.b, x=a["x"], y=a["y"])
        self.assertEqual(moved["boards"][0]["x"], moved["boards"][1]["x"])
        self.assertEqual(moved["boards"][0]["y"], moved["boards"][1]["y"])

    def test_place_freezes_an_automatic_target_instead_of_moving_it_away(self):
        with transaction(self.c) as w:
            w.update("layer", self.b, {"axis": {"unit": "页", "precision": 1}}, project_id=self.p)
        before = arrange(self.db, self.p)["boards"]
        self.assertTrue(all(b["automatic"] for b in before))
        placed = arrange(self.db, self.p, "place", root=self.b, target=self.a, side="right")["boards"]
        a = next(b for b in placed if self.a in b["roots"])
        b = next(b for b in placed if self.b in b["roots"])
        self.assertEqual((a["x"], a["y"]), (before[0]["x"], before[0]["y"]))
        self.assertEqual((b["x"], b["y"]), (a["x"]+a["width"]+48, a["y"]))
        self.assertFalse(any(b["automatic"] for b in placed))

    def test_invalid_resize_has_no_side_effects(self):
        save_layout(self.db, self.p, self.boards)
        before = change_cursor(self.c)
        for values in [{"width": 100}, {"height": 1}, {"pps": -1}, {"lane_height": 10}, {"width": float("nan")}]:
            with self.assertRaises(ValueError):
                arrange(self.db, self.p, "resize", root=self.a, **values)
        self.assertEqual(change_cursor(self.c), before)

    def test_position_only_payload_preserves_size_and_noop_has_no_operation(self):
        save_layout(self.db, self.p, self.boards)
        plain = [{k: v for k, v in b.items() if k != "styles"} for b in self.boards]
        plain[0]["x"] = 300
        save_layout(self.db, self.p, plain)
        box = arrange(self.db, self.p)["boards"][0]
        self.assertEqual(box["styles"][str(self.a)]["lane_height"], 100)
        before = change_cursor(self.c)
        result = save_layout(self.db, self.p, plain, with_result=True)
        self.assertEqual(result["changed"], 0)
        self.assertIsNone(result["operation_id"])
        self.assertEqual(change_cursor(self.c), before)


if __name__ == "__main__":
    unittest.main()

"""空档查询的区间、点占用、原始精度与只读边界。"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from runtime.api import dispatch, find_gaps, open_database
from runtime.storage.database import SCHEMA_PATH
from tools.usage.common.free_ranges import format_gaps


class FreeRangesTests(unittest.TestCase):
    def setUp(self):
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.p = self.create("project", {})
        self.layer = self.create("layer", {"config_ref": "layers/text.toml"})

    def create(self, kind, data):
        result = dispatch(self.c, {"action": "create", "kind": kind, "data": data,
                                  **({"project_id": self.p} if kind != "project" else {})}, checker=None)
        self.assertTrue(result["ok"], result)
        return result["id"]

    def obj(self, b, e, layer=None):
        return self.create("object", {"config_ref": "objects/text.toml", "layer": self.layer if layer is None else layer,
                                      "begin": b, "end": e, "information": {"text": "正文"}})

    def gaps(self, **kwargs):
        return find_gaps(self.c, self.p, self.layer, **{"begin": 0, "end": 20, **kwargs})["gaps"]

    def test_overlaps_touching_nested_and_clipped_objects_form_union(self):
        for b, e in ((-2, 3), (1, 2), (2, 4), (4, 5), (9, 12), (10, 11), (17, 24)):
            self.obj(b, e)
        self.assertEqual(self.gaps(), [
            {"begin": 5, "end": 9, "length": 4.0, "begin_inclusive": True},
            {"begin": 12, "end": 17, "length": 5.0, "begin_inclusive": True}])
        self.assertEqual(len(self.gaps(min_length=5)), 1)
        self.assertEqual(self.gaps(min_length=6), [])

    def test_empty_layer_boundaries_and_equal_query(self):
        self.assertEqual(self.gaps(begin=-5, end=5)[0]["length"], 10)
        self.obj(-3, 0)
        self.obj(20, 24)
        self.assertEqual(self.gaps(), [{"begin": 0, "end": 20, "length": 20.0, "begin_inclusive": True}])
        self.assertEqual(self.gaps(begin=4, end=4), [])

    def test_points_split_free_ranges_without_inventing_epsilon(self):
        self.obj(0, 0)
        self.obj(5, 5)
        self.obj(5, 5)
        self.obj(20, 20)
        gaps = self.gaps()
        self.assertEqual([(g["begin"], g["end"], g["begin_inclusive"]) for g in gaps], [(0, 5, False), (5, 20, False)])
        self.assertEqual(self.gaps(min_length=15), [])
        self.assertEqual(len(self.gaps(min_length=14)), 1)
        self.assertIn("(5", format_gaps(find_gaps(self.c, self.p, self.layer, begin=0, end=20)))

    def test_point_inside_occupied_interval_is_not_a_gap(self):
        self.obj(0, 10)
        self.obj(5, 5)
        self.obj(10, 10)
        self.assertEqual(self.gaps(), [{"begin": 10, "end": 20, "length": 10.0, "begin_inclusive": False}])
        self.obj(10, 20)
        self.assertEqual(self.gaps(), [])

    def test_direct_layer_only_raw_precision_no_body_or_config_loading_or_writes(self):
        child = self.create("layer", {"config_ref": "layers/text.toml", "father": self.layer})
        self.obj(0, 20, child)
        obj = self.obj(0, 0.1)
        self.c.execute('UPDATE objects SET "end"=?, information=? WHERE project_id=? AND id=?',
                       (0.123456789, "not JSON", self.p, obj))
        self.c.commit()
        count = self.c.total_changes
        with patch("runtime.configuration.loader.Loader.load", side_effect=AssertionError("no configs")):
            result = self.gaps(end=0.3)
        self.assertEqual(result[0]["begin"], 0.123456789)
        self.assertEqual(result[0]["length"], 0.176543211)
        self.assertEqual(self.c.total_changes, count)
        self.assertFalse(self.c.in_transaction)
        self.c.execute("BEGIN")
        self.gaps()
        self.assertTrue(self.c.in_transaction)
        self.c.rollback()

    def test_invalid_input_or_stored_position_does_not_claim_free_space(self):
        for kwargs in ({"begin": 2, "end": 1}, {"min_length": -1}, {"begin": float("nan")}, {"end": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.gaps(**kwargs)
        with self.assertRaisesRegex(ValueError, "不存在"):
            find_gaps(self.c, self.p, 999, begin=0, end=20)
        obj = self.obj(8, 3)
        with self.assertRaisesRegex(ValueError, str(obj)):
            self.gaps()
        self.c.execute('UPDATE objects SET "end"=? WHERE id=? AND project_id=?', ("bad", obj, self.p))
        self.c.commit()
        with self.assertRaisesRegex(ValueError, "有限数值"):
            self.gaps()

    def test_cli_json_and_text(self):
        self.obj(0, 3)
        self.obj(7, 20)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "gaps.sqlite3"
            destination = open_database(path)
            self.c.backup(destination)
            destination.close()
            command = [sys.executable, "-X", "utf8", "-B", "-m", "tools.usage.common.free_ranges", str(path),
                       str(self.p), str(self.layer), "0", "20", "--min-length", "4"]
            result = subprocess.run([*command, "--json"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["gaps"][0]["begin"], 3)
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("1 个空档", result.stdout)


if __name__ == "__main__":
    unittest.main()

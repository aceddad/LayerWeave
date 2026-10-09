"""缺字段警告、读取时提示，以及轴精度下的计算落点。"""

from functools import partial
from pathlib import Path
import shutil
import tempfile
import unittest

from runtime.api import dispatch, open_database, read_record, validate
from runtime.configuration.loader import DEFAULT_ROOT
from runtime.storage.database import SCHEMA_PATH
from runtime.validation.runner import check_changes
from tools.common.objects import append_object, copy_object
from tools.common.positions import align_objects, arrange_objects, set_duration, shift_objects
from tools.text.collect import collect_text


class MissingFieldsPrecisionTests(unittest.TestCase):
    def setUp(self):
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        temp = tempfile.TemporaryDirectory(prefix="layerweave-precision-")
        self.addCleanup(temp.cleanup)
        self.configs = Path(temp.name) / "configs"
        shutil.copytree(DEFAULT_ROOT, self.configs)
        path = self.configs / "layers/text.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("overlap = true", "overlap = false")
                        + "\n[layer.options]\naxis_only_on_root=false\n", encoding="utf-8")
        self.checker = partial(check_changes, config_root=self.configs)
        self.project_id = self.create("project", {})["id"]
        self.layer_id = self.layer(axis={"unit": "秒", "precision": 0.001})

    def create(self, kind, data):
        result = dispatch(self.connection, {"action": "create", "kind": kind, "data": data,
                                           **({"project_id": self.project_id} if kind != "project" else {})}, checker=self.checker)
        self.assertTrue(result["ok"], result)
        return result

    def layer(self, **data):
        return self.create("layer", {"type": "text", "config_ref": "layers/text.toml", **data})["id"]

    def obj(self, *, layer_id=None, **data):
        return self.create("object", {"layer": layer_id or self.layer_id, "config_ref": "objects/text.toml", **data})

    def append(self, *, layer_id=None, duration=0.1, **kwargs):
        return append_object(self.connection, self.project_id, layer_id or self.layer_id,
                             {"config_ref": "objects/text.toml", "information": {"text": "正文"}},
                             duration=duration, checker=self.checker, **kwargs)

    def span(self, id):
        row = read_record(self.connection, "object", project_id=self.project_id, id=id)
        return row["begin"], row["end"]

    def test_typo_is_saved_but_missing_declared_field_warns_and_collect_reports_it(self):
        typo = self.obj(information={"txt": "你好"})
        self.obj(begin=1, end=2, information={"text": "世界"})
        warnings = [item for item in typo["checks"]["issues"] if item["severity"] == "warn"]
        self.assertEqual([item["field"] for item in warnings], ["information.txt"])
        self.assertEqual(warnings[0]["suggestions"], {"txt": "text"})
        self.assertEqual(typo["data"]["information"], {"txt": "你好"})
        result = collect_text(self.connection, self.project_id, self.layer_id, config_root=self.configs)
        self.assertEqual(result["text"], "世界")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["issues"][0]["severity"], "warn")
        self.assertEqual(result["issues"][0]["target"]["id"], typo["id"])

    def test_empty_text_is_present_open_extras_are_allowed_and_virtual_fields_do_not_warn(self):
        result = self.obj(information={"text": "", "txt": "额外字段"})
        self.assertEqual(result["checks"]["issues"], [])
        checks = validate([{"kind": "layer", "project_id": self.project_id, "id": self.layer_id}],
                          partial(read_record, self.connection), config_root=self.configs)
        self.assertFalse(any(item.get("field") in {"bind", "objects"} for item in checks["issues"]))

    def test_inherited_missing_fields_warn_once_without_requiring_values(self):
        (self.configs / "objects/dialogue.toml").write_text(
            '[object]\ntype="dialogue"\nclass="fixture_types:DialogueObject"\nextends="text.toml"\n[object.information]\nspeaker={type="str"}\n', encoding="utf-8")
        result = self.obj(config_ref="objects/dialogue.toml", information={})
        warnings = [item for item in result["checks"]["issues"] if item["severity"] == "warn"]
        self.assertEqual({item["field"] for item in warnings}, {"information.text", "information.speaker"})
        self.assertEqual(len(warnings), 2)
        self.assertTrue(result["applied"])
        renamed = dispatch(self.connection, {"action": "update", "kind": "object", "project_id": self.project_id,
                                           "id": result["id"], "data": {"name": "只改名字"}}, checker=self.checker)
        self.assertEqual(renamed["checks"]["issues"], [])

    def test_optional_model_data_is_silent(self):
        layer = self.layer(type="Layer", config_ref="layers/base.toml")
        result = self.obj(layer_id=layer, config_ref="objects/model.toml", information={"source": "mesh.glb"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["checks"]["issues"], [])

    def test_three_decimal_appends_end_at_point_three_without_false_overlap(self):
        records = [self.append() for _ in range(3)]
        self.assertEqual([item["data"]["end"] for item in records], [0.1, 0.2, 0.3])
        self.assertTrue(all(item["checks"]["issues"] == [] for item in records))
        following = self.obj(begin=0.3, end=0.4, information={"text": "手动指定的下一段"})
        self.assertEqual(following["checks"]["issues"], [])

    def test_frame_sized_precision_and_decimal_rounding(self):
        frame_layer = self.layer(axis={"unit": "秒", "precision": 1/30, "fps": 30})
        records = [self.append(layer_id=frame_layer, duration=1/30) for _ in range(3)]
        self.assertEqual(records[-1]["data"]["end"], 0.1)
        self.assertTrue(all(item["checks"]["issues"] == [] for item in records))
        following = self.obj(layer_id=frame_layer, begin=0.1, end=0.2, information={"text": "下一段"})
        self.assertEqual(following["checks"]["issues"], [])
        coarse = self.layer(axis={"precision": 0.25})
        result = self.append(layer_id=coarse, duration=0.4)
        self.assertEqual(result["data"]["end"], 0.5)

    def test_precision_inherits_from_axis_but_own_axis_is_not_unit_converted(self):
        child = self.layer(father=self.layer_id)
        self.assertEqual(self.append(layer_id=child, duration=0.0006)["data"]["end"], 0.001)
        local = self.layer(father=self.layer_id, axis={"unit": "帧", "precision": 1, "fps": 30})
        grandchild = self.layer(father=local)
        self.assertEqual(self.append(layer_id=grandchild, duration=0.6)["data"]["end"], 1)
        no_precision = self.layer(father=self.layer_id, axis={"unit": "帧"})
        self.assertEqual(self.append(layer_id=no_precision, duration=0.0004)["data"]["end"], 0.0004)

    def test_all_generated_positions_snap_but_duration_keeps_original_start(self):
        obj = self.obj(begin=1.0004, end=2.0004, information={"text": "位置"})["id"]
        shifted = shift_objects(self.connection, self.project_id, [obj], offset=0, checker=self.checker)
        self.assertFalse(shifted["applied"])  # 创建时已经落点，平移零不再产生修改。
        self.assertEqual(self.span(obj), (1.0, 2.0))
        aligned = align_objects(self.connection, self.project_id, [obj], position=0.1004, checker=self.checker)
        self.assertTrue(aligned["ok"])
        self.assertEqual(self.span(obj), (0.1, 1.1))
        aligned = align_objects(self.connection, self.project_id, [obj], position=1.2004, edge="end", checker=self.checker)
        self.assertEqual(self.span(obj), (0.2, 1.2))
        copied = copy_object(self.connection, self.project_id, obj, begin=2.1004, checker=self.checker)
        self.assertEqual(self.span(copied["id"]), (2.1, 3.1))
        raw = self.obj(begin=4.0004, end=5, information={"text": "保持起点"})["id"]
        result = set_duration(self.connection, self.project_id, raw, 0.1, checker=self.checker)
        self.assertTrue(result["ok"])
        self.assertEqual(self.span(raw), (4.0, 4.1))
        destination = self.layer(axis={"precision": 0.01})
        copied = copy_object(self.connection, self.project_id, obj, layer_id=destination, begin=2.006, checker=self.checker)
        self.assertEqual(self.span(copied["id"]), (2.01, 3.01))

    def test_rounding_half_steps_and_precision_changes_between_operations(self):
        self.assertEqual(self.append(duration=0.0005)["data"]["end"], 0.001)
        negative = self.layer(axis={"precision": 0.001})
        point = self.append(layer_id=negative, duration=0, empty_start=-0.0005)
        self.assertEqual(self.span(point["id"]), (-0.001, -0.001))
        obj = self.obj(begin=1.004, end=1.014, information={"text": "新精度"})["id"]
        dispatch(self.connection, {"action": "update", "kind": "layer", "project_id": self.project_id,
                                   "id": self.layer_id, "data": {"axis": {"precision": 0.01}}}, checker=self.checker)
        result = shift_objects(self.connection, self.project_id, [obj], offset=0, checker=self.checker)
        self.assertTrue(result["ok"])
        self.assertEqual(self.span(obj), (1.0, 1.01))

    def test_arrangement_quantizes_endpoints_from_legacy_durations_without_rounding_cursor(self):
        ids = [self.obj(begin=0, end=1/30, information={"text": str(i)})["id"] for i in range(3)]
        # 模拟旧数据库中尚未落点的时长；新写入现在会先落点。
        self.connection.execute('UPDATE objects SET "end"=? WHERE project_id=?', (1/30, self.project_id))
        self.connection.commit()
        result = arrange_objects(self.connection, self.project_id, self.layer_id, object_ids=ids, start=0, checker=self.checker)
        self.assertTrue(result["ok"], result)
        self.assertEqual([self.span(id) for id in ids], [(0, 0.033), (0.033, 0.067), (0.067, 0.1)])
        self.assertEqual(result["checks"]["issues"], [])

    def test_invalid_precision_aborts_without_allocating_or_modifying_data(self):
        bad = self.layer(axis={"precision": 0})
        before = read_record(self.connection, "project", id=self.project_id)["max_id"]
        result = self.append(layer_id=bad)
        self.assertFalse(result["ok"])
        self.assertIn("precision", result["error"]["message"])
        self.assertEqual(read_record(self.connection, "project", id=self.project_id)["max_id"], before)

    def test_direct_writes_and_plain_copy_use_axis_precision(self):
        original = self.obj(begin=0.0004, end=0.30000000000000004, information={"text": "原值"})["id"]
        copied = copy_object(self.connection, self.project_id, original, checker=self.checker)
        self.assertEqual(self.span(copied["id"]), (0.0, 0.3))
        self.assertEqual(self.span(original), self.span(copied["id"]))

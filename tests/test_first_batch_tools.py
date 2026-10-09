"""第一批只读工具：筛选语义、完整引用、文本来源、诊断继续和命令行。"""

import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from runtime.api import dispatch, open_database, read_record
from runtime.configuration.loader import DEFAULT_ROOT
from runtime.storage.database import SCHEMA_PATH
from tools.usage.common.find_objects import find_objects
from tools.usage.common.project_overview import project_overview
from tools.usage.common.relations import query_relations
from tools.usage.text.collect import collect_text


class FirstBatchToolsTests(unittest.TestCase):
    def setUp(self):
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-tools-")
        self.addCleanup(self.temp.cleanup)
        self.configs = Path(self.temp.name) / "configs"
        shutil.copytree(DEFAULT_ROOT, self.configs)
        self.project_id = self.create("project", {"name": "tools"})
        self.layer_id = self.layer(self.project_id)

    def create(self, kind, data, *, project_id=None):
        result = dispatch(self.connection, {"action": "create", "kind": kind, "data": data,
                                           **({"project_id": project_id} if project_id is not None else {})}, checker=None)
        self.assertTrue(result["ok"], result)
        return result["id"]

    def layer(self, project_id):
        return self.create("layer", {"type": "Layer", "config_ref": "layers/base.toml"}, project_id=project_id)

    def obj(self, *, project_id=None, layer_id=None, **data):
        return self.create("object", {"layer": layer_id or self.layer_id, "config_ref": "objects/text.toml", **data},
                           project_id=project_id or self.project_id)

    def binding(self, source, target, tips=""):
        return self.create("bind", {**{f"source_{key}": value for key, value in source.items()},
                                    **{f"target_{key}": value for key, value in target.items()}, "tips": tips})

    def ref(self, id, *, kind="object", project_id=None):
        return {"kind": kind, "project_id": project_id or self.project_id, "id": id}

    def test_find_combines_literal_name_nested_content_and_layer_scope(self):
        wanted = self.obj(name="片段_100%", information={"nested": [42, {"text": "你好 Needle"}]})
        self.obj(name="片段_100%", information={"Needle": "only a key"})
        self.obj(name="其他", information={"text": "你好 Needle"})
        extra_layer = self.layer(self.project_id)
        self.obj(layer_id=extra_layer, name="片段_100%", information={"text": "你好 Needle"})
        result = find_objects(self.connection, self.project_id, layer_id=self.layer_id, name="_100%", content="Needle")
        self.assertEqual([row["id"] for row in result], [wanted])
        self.assertEqual(find_objects(self.connection, self.project_id, content="needle"), [])
        self.assertEqual(find_objects(self.connection, self.project_id, content="42"), [])
        self.assertEqual(find_objects(self.connection, self.project_id, name="' OR 1=1 --"), [])
        self.assertTrue(all(row["project_id"] == self.project_id for row in result))

    def test_find_string_content_is_not_limited_to_one_content_key(self):
        path = self.obj(config_ref="objects/image.toml", information={"source": "assets/needle.png"})
        scalar = self.obj(information="needle")
        self.obj(information={"value": True})
        self.assertEqual({row["id"] for row in find_objects(self.connection, self.project_id, content="needle")}, {path, scalar})
        self.assertEqual(find_objects(self.connection, self.project_id, content="true"), [])

    def test_range_and_point_queries_follow_half_open_and_instant_rules(self):
        positions = {"before": (-1, 1), "span": (1, 3), "after": (3, 5), "left": (1, 1),
                     "right": (3, 3), "reversed": (5, 2), "bad": ("bad", 4)}
        for name, (begin, end) in positions.items():
            self.obj(name=name, begin=begin, end=end)
        cases = [({"begin": 1, "end": 3}, {"span", "left"}),
                 ({"begin": 3, "end": 3}, {"after", "right"}),
                 ({"begin": 1, "end": 1}, {"span", "left"}),
                 ({"begin": 3}, {"after", "right"}),
                 ({"end": 1}, {"before"})]
        for parameters, names in cases:
            with self.subTest(parameters=parameters):
                result = find_objects(self.connection, self.project_id, **parameters)
                self.assertEqual({row["name"] for row in result}, names)
        self.assertEqual(len(find_objects(self.connection, self.project_id)), len(positions))

    def test_invalid_query_bounds_report_request_error(self):
        for bounds in ({"begin": 4, "end": 1}, {"begin": float("nan")}, {"end": float("inf")},
                       {"begin": True}, {"end": "three"}):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                find_objects(self.connection, self.project_id, **bounds)

    def test_find_is_project_scoped_and_orders_by_layer_then_position(self):
        other_project = self.create("project", {})
        other_layer = self.layer(other_project)
        foreign = self.obj(project_id=other_project, layer_id=other_layer, name="foreign")
        local = self.obj(name="local", begin=5, end=6)
        self.assertEqual(foreign, local)
        second_layer = self.layer(self.project_id)
        second = self.obj(layer_id=second_layer, begin=-5, end=-4)
        first = self.obj(begin=1, end=2)
        self.assertEqual([row["id"] for row in find_objects(self.connection, self.project_id)], [first, local, second])
        self.assertEqual(find_objects(self.connection, 999), [])
        self.assertEqual(find_objects(self.connection, self.project_id, layer_id=999), [])

    def test_relations_directions_self_reference_and_cross_project_identity(self):
        anchor = self.obj()
        other_project = self.create("project", {})
        other_layer = self.layer(other_project)
        foreign = self.obj(project_id=other_project, layer_id=other_layer)
        self.assertEqual(anchor, foreign)
        outgoing = self.binding(self.ref(anchor), self.ref(foreign, project_id=other_project), "out")
        incoming = self.binding(self.ref(foreign, project_id=other_project), self.ref(anchor), "in")
        self_bind = self.binding(self.ref(anchor), self.ref(anchor), "self")
        self.binding(self.ref(anchor, kind="layer"), self.ref(999), "wrong kind")
        result = query_relations(self.connection, self.project_id, "object", anchor)
        self.assertEqual([row["id"] for row in result["outgoing"]], [outgoing, self_bind])
        self.assertEqual([row["id"] for row in result["incoming"]], [incoming, self_bind])
        self.assertEqual(result["entity"], self.ref(anchor))
        result = query_relations(self.connection, self.project_id, "object", anchor, direction="incoming")
        self.assertEqual(result["outgoing"], [])
        self.assertEqual([row["id"] for row in result["incoming"]], [incoming, self_bind])
        self.assertEqual(result["direction"], "incoming")

    def test_relations_survive_deleted_endpoint_without_loading_it(self):
        anchor = self.obj()
        binding = self.binding(self.ref(self.layer_id, kind="layer"), self.ref(anchor))
        dispatch(self.connection, {"action": "delete", "kind": "object", "project_id": self.project_id, "id": anchor})
        result = query_relations(self.connection, self.project_id, "object", anchor)
        self.assertEqual([row["id"] for row in result["incoming"]], [binding])
        self.assertEqual(query_relations(self.connection, 999, "object", anchor)["incoming"], [])

    def test_relation_arguments_and_single_query(self):
        anchor = self.obj()
        for _ in range(30):
            self.binding(self.ref(anchor), self.ref(999))
        statements = []
        self.connection.set_trace_callback(statements.append)
        try:
            with patch.object(Path, "open", side_effect=AssertionError("must not load configs")):
                result = query_relations(self.connection, self.project_id, "object", anchor)
        finally:
            self.connection.set_trace_callback(None)
        self.assertEqual(len(result["outgoing"]), 30)
        self.assertEqual(sum(sql.lstrip().upper().startswith("SELECT") for sql in statements), 1)
        for kind, direction in (("project", "both"), ("object", "wrong")):
            with self.assertRaises(ValueError):
                query_relations(self.connection, self.project_id, kind, anchor, direction=direction)

    def test_collect_accepts_text_descendants_preserves_empty_text_and_sources(self):
        (self.configs / "objects/dialogue.toml").write_text(
            '[object]\ntype="dialogue"\nextends="text.toml"\nclass="module_not_imported:Dialogue"\n', encoding="utf-8")
        last = self.obj(name="last", begin=3, end=5, information={"text": "丙"})
        first = self.obj(name="first", begin=0, end=1, information={"text": "甲"})
        empty = self.obj(begin=1, end=1, information={"text": ""})
        derived = self.obj(begin=1, end=3, config_ref="objects/dialogue.toml", information={"text": "乙"})
        self.obj(config_ref="objects/image.toml", information={"text": "图片备注"})
        self.obj(config_ref="objects/base.toml", information={"text": "基础对象不是文字类型"})
        missing = self.obj(information={})
        result = collect_text(self.connection, self.project_id, self.layer_id, separator="|", config_root=self.configs)
        self.assertEqual(result["text"], "甲||乙|丙")
        self.assertEqual([item["id"] for item in result["items"]], [first, empty, derived, last])
        self.assertEqual(result["items"][2]["config_ref"], "objects/dialogue.toml")
        self.assertTrue(all(item["project_id"] == self.project_id for item in result["items"]))
        self.assertEqual(result["skipped_count"], 3)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["issues"]), 1)
        self.assertEqual(result["issues"][0]["severity"], "warn")
        self.assertEqual(result["issues"][0]["target"]["id"], missing)

    def test_collect_reports_each_unreadable_item_and_continues(self):
        self.obj(information={"text": "good"})
        missing = self.obj(config_ref="objects/missing.toml")
        number = self.obj(information={"text": 123})
        invalid = self.obj(information=[])
        result = collect_text(self.connection, self.project_id, self.layer_id)
        self.assertEqual(result["text"], "good")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["skipped_count"], 3)
        self.assertEqual({item["target"]["id"] for item in result["issues"]}, {missing, number, invalid})
        self.assertTrue(all(item["severity"] == "error" for item in result["issues"]))

    def test_collect_range_point_and_missing_layer(self):
        self.obj(begin=1, end=3, information={"text": "before"})
        self.obj(begin=3, end=3, information={"text": "instant"})
        self.obj(begin=3, end=5, information={"text": "after"})
        result = collect_text(self.connection, self.project_id, self.layer_id, begin=3, end=3)
        self.assertEqual(result["text"], "instant\nafter")
        self.assertIsNone(collect_text(self.connection, self.project_id, 999))
        empty_layer = self.layer(self.project_id)
        self.assertEqual(collect_text(self.connection, self.project_id, empty_layer)["items"], [])

    def test_collect_unavailable_baseline_is_not_silently_successful(self):
        self.obj(information={"text": "text"})
        (self.configs / "objects/text.toml").unlink()
        result = collect_text(self.connection, self.project_id, self.layer_id, config_root=self.configs)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["skipped_count"], 1)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["issues"][0]["target"]["kind"], "layer")

    def test_all_tools_are_read_only_and_preserve_callers_transaction(self):
        obj = self.obj(information={"text": "hello"})
        self.binding(self.ref(obj), self.ref(self.layer_id, kind="layer"))
        logs = len(read_record(self.connection, "change"))
        self.connection.execute("UPDATE projects SET name='pending' WHERE id=?", (self.project_id,))
        changes = self.connection.total_changes
        self.assertEqual(project_overview(self.connection, self.project_id)["project"]["name"], "pending")
        with patch.object(Path, "open", side_effect=AssertionError("object search does not load config")):
            self.assertEqual(len(find_objects(self.connection, self.project_id, content="hello")), 1)
        query_relations(self.connection, self.project_id, "object", obj)
        collect_text(self.connection, self.project_id, self.layer_id)
        self.assertTrue(self.connection.in_transaction)
        self.assertEqual(self.connection.total_changes, changes)
        self.assertEqual(len(read_record(self.connection, "change")), logs)
        self.connection.rollback()
        self.assertEqual(read_record(self.connection, "project", id=self.project_id)["name"], "tools")

    def test_three_new_command_line_tools_and_partial_text_feedback(self):
        good = self.obj(name="hello", begin=1, end=3, information={"text": "你好"})
        self.obj(begin=3, end=3, information={"text": 123})
        bind_id = self.binding(self.ref(good), self.ref(self.layer_id, kind="layer"))
        database = Path(self.temp.name) / "cli.sqlite3"
        copied = sqlite3.connect(database)
        try:
            self.connection.backup(copied)
        finally:
            copied.close()

        def run(module, *args):
            return subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", module,
                                   str(database), str(self.project_id), *map(str, args)],
                                  capture_output=True, text=True, encoding="utf-8")

        found = run("tools.usage.common.find_objects", "--name", "hello", "--begin", 1, "--end", 3)
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertEqual(json.loads(found.stdout)[0]["id"], good)
        relations = run("tools.usage.common.relations", "object", good)
        self.assertEqual(relations.returncode, 0, relations.stderr)
        self.assertEqual(json.loads(relations.stdout)["outgoing"][0]["id"], bind_id)
        collected = run("tools.usage.text.collect", self.layer_id, "--json")
        self.assertEqual(collected.returncode, 0, collected.stderr)
        self.assertEqual(json.loads(collected.stdout)["status"], "partial")
        plain = run("tools.usage.text.collect", self.layer_id)
        self.assertEqual(plain.stdout.strip(), "你好")
        self.assertIn("information.text", plain.stderr)
        invalid = run("tools.usage.common.find_objects", "--begin", 3, "--end", 1)
        self.assertEqual(invalid.returncode, 1)

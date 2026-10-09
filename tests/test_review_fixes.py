"""Claude 反馈回归：明确范围、跨界 split/keep、顶层字段撤销。"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runtime.api import command_help, dispatch, insert_gap, open_database, query_objects, read_record, undo_operation
from runtime.storage.database import SCHEMA_PATH
from tools.common.gaps import format_gap


class ReviewFixTests(unittest.TestCase):
    def setUp(self):
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.p = self.call("create", "project", data={})["id"]
        self.root = self.layer()
        self.lyrics = self.layer(father=self.root)
        self.description = self.layer(father=self.root)
        self.background = self.layer(father=self.root, config_ref="layers/image.toml")
        self.a = self.obj(self.lyrics, 8, 12, {"text": "歌词甲句"})
        self.b = self.obj(self.description, 0, 30, {"text": "第一段：犹豫"})
        self.c_image = self.obj(self.background, 5, 15, {"source": "background.png"}, config_ref="objects/image.toml")

    def call(self, action, kind, **args):
        if kind in {"object", "layer"}:
            args.setdefault("project_id", self.p)
        result = dispatch(self.c, {"action": action, "kind": kind, **args}, checker=None)
        self.assertTrue(result["ok"], result)
        return result

    def layer(self, **data):
        return self.call("create", "layer", data={"config_ref": "layers/text.toml", **data})["id"]

    def obj(self, layer, begin, end, info, **data):
        return self.call("create", "object", data={"config_ref": "objects/text.toml", "layer": layer,
                         "begin": begin, "end": end, "information": info, **data})["id"]

    def row(self, id):
        return read_record(self.c, "object", project_id=self.p, id=id)

    def snapshot(self):
        return {table: [tuple(row) for row in self.c.execute(f'SELECT * FROM "{table}" ORDER BY 1,2')]
                for table in ("projects", "layers", "objects", "binds", "changes", "sqlite_sequence")}

    def actions(self):
        return [{"object_id": self.a, "action": "split", "first_information": {"text": "前半"}, "second_information": {"text": "后半"}},
                {"object_id": self.b, "action": "keep"}, {"object_id": self.c_image, "action": "keep"}]

    def undo(self, op):
        result = undo_operation(self.c, op["operation_id"])
        self.assertTrue(result["ok"], result)
        return result

    def test_omitted_or_ambiguous_scope_never_expands_to_project(self):
        for scope in ({}, {"whole_project": True, "layer_id": self.lyrics}, {"whole_project": "yes"}):
            before = self.snapshot()
            result = insert_gap(self.c, self.p, at=10, length=2, **scope)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["code"], "explicit_scope_required")
            self.assertEqual(self.snapshot(), before)

    def test_direct_layer_does_not_select_siblings_or_children(self):
        child = self.layer(father=self.lyrics)
        child_obj = self.obj(child, 0, 30, {"text": "子层内容"})
        untouched = [self.row(id) for id in (self.b, self.c_image, child_obj)]
        result = insert_gap(self.c, self.p, at=10, length=2, layer_id=self.lyrics, crossing_actions=self.actions()[:1])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["scope"], {"mode": "layer", "layer_ids": [self.lyrics]})
        self.assertEqual([self.row(id) for id in (self.b, self.c_image, child_obj)], untouched)
        self.assertEqual(len(result["data"]["splits"]), 1)

    def test_subtree_splits_only_lyrics_and_keeps_complete_background_and_description(self):
        before = [self.row(id) for id in (self.a, self.b, self.c_image)]
        result = insert_gap(self.c, self.p, at=10, length=2, layer_ids=[self.root], crossing_actions=self.actions())
        self.assertTrue(result["ok"], result)
        self.assertEqual([self.row(id) for id in (self.b, self.c_image)], before[1:])
        self.assertEqual({r["id"] for r in result["data"]["kept"]}, {self.b, self.c_image})
        self.assertEqual([(r["begin"],r["end"]) for r in result["data"]["splits"][0]["segments"]], [(8,10),(12,14)])
        self.assertIn("保持原样", format_gap(result))
        self.assertIn("插入时段", format_gap(result))
        u = self.undo(result)
        self.assertEqual([self.row(id) for id in (self.a,self.b,self.c_image)], before)
        self.undo(u)
        self.assertEqual([self.row(id) for id in (self.b,self.c_image)], before[1:])

    def test_explicit_project_missing_actions_reports_all_crossings_without_guessing(self):
        before = self.snapshot()
        result = insert_gap(self.c, self.p, at=10, length=2, whole_project=True)
        self.assertFalse(result["ok"])
        self.assertEqual({r["object_id"] for r in result["error"]["required_crossings"]}, {self.a,self.b,self.c_image})
        self.assertEqual(result["error"]["allowed"], ["split","keep","stretch","move"])
        self.assertEqual(self.snapshot(), before)

    def test_keep_only_does_not_write_or_require_replacement_contents(self):
        before = self.snapshot()
        result = insert_gap(self.c, self.p, at=10, length=2, layer_id=self.background,
                            crossing_actions=[{"object_id":self.c_image,"action":"keep"}])
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["applied"])
        self.assertEqual(self.snapshot(), before)

    def test_unsupported_action_and_missing_action_are_explicit_errors(self):
        for action in ({"object_id":self.b,"action":"auto"}, {"object_id":self.b}):
            before = self.snapshot()
            result = insert_gap(self.c, self.p, at=10, length=2, layer_id=self.description, crossing_actions=[action])
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["allowed"], ["split","keep","stretch","move"])
            self.assertEqual(self.snapshot(), before)

    def test_legacy_split_contents_still_works_with_explicit_scope(self):
        legacy = {k:v for k,v in self.actions()[0].items() if k != "action"}
        result = insert_gap(self.c, self.p, at=10, length=2, layer_id=self.lyrics, split_contents=[legacy])
        self.assertTrue(result["ok"], result)
        before = self.snapshot()
        invalid = insert_gap(self.c, self.p, at=9, length=2, layer_id=self.lyrics, split_contents=[], crossing_actions=[])
        self.assertFalse(invalid["ok"])
        self.assertEqual(self.snapshot(), before)

    def test_stretch_keeps_description_and_background_aligned_with_later_content(self):
        final_line = self.obj(self.lyrics, 28, 30, {"text": "丙句"})
        middle_line = self.obj(self.lyrics, 13, 16, {"text": "乙句"})
        original = {id:self.row(id) for id in (self.b, self.c_image)}
        actions = self.actions()
        actions[1]["action"] = actions[2]["action"] = "stretch"
        result = insert_gap(self.c, self.p, at=10, length=2, layer_ids=[self.root], crossing_actions=actions)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.row(self.b)["end"], 32)
        self.assertEqual(self.row(self.c_image)["end"], 17)
        self.assertEqual((self.row(final_line)["begin"], self.row(final_line)["end"]), (30,32))
        self.assertEqual((self.row(middle_line)["begin"], self.row(middle_line)["end"]), (15,18))
        self.assertEqual([r["id"] for r in query_objects(self.c,self.p,layer_id=self.description,begin=30,end=31)], [self.b])
        self.assertEqual([r["id"] for r in query_objects(self.c,self.p,layer_id=self.background,begin=15,end=16)], [self.c_image])
        for id, before in original.items():
            self.assertEqual({k:v for k,v in self.row(id).items() if k!="end"}, {k:v for k,v in before.items() if k!="end"})
        self.assertEqual({r["id"] for r in result["data"]["stretched"]}, set(original))

    def test_move_adds_length_to_both_edges_without_repositioning_to_gap_end(self):
        bind = self.call("create","bind",data={"source_kind":"object","source_project_id":self.p,"source_id":self.a,
                         "target_kind":"object","target_project_id":self.p,"target_id":self.b})["data"]
        before = self.row(self.a)
        result = insert_gap(self.c,self.p,at=10,length=2,layer_id=self.lyrics,
                            crossing_actions=[{"object_id":self.a,"action":"move"}])
        self.assertTrue(result["ok"],result)
        self.assertEqual((self.row(self.a)["begin"],self.row(self.a)["end"]),(10,14))
        self.assertEqual({k:v for k,v in self.row(self.a).items() if k not in {"begin","end"}},
                         {k:v for k,v in before.items() if k not in {"begin","end"}})
        self.assertEqual(read_record(self.c,"bind"),[bind])
        self.assertEqual(result["data"]["shifted"],[])
        self.assertEqual(result["data"]["moved"][0]["previous_begin"],8)
        self.assertIn("整体后移",format_gap(result))

    def test_stretch_only_writes_end_and_keeps_original_begin_even_off_grid(self):
        self.call("update","layer",id=self.root,data={"axis":{"precision":0.001}})
        self.c.execute('UPDATE objects SET "begin"=?, "end"=? WHERE project_id=? AND id=?',
                       (0.0001234,30.0001,self.p,self.b))
        self.c.commit()
        self.c.execute("CREATE TRIGGER protect_unchanged BEFORE UPDATE OF begin,information ON objects BEGIN SELECT RAISE(ABORT,'only end may change'); END")
        result = insert_gap(self.c,self.p,at=10,length=2,layer_id=self.description,
                            crossing_actions=[{"object_id":self.b,"action":"stretch"}])
        self.assertTrue(result["ok"],result)
        self.assertEqual((self.row(self.b)["begin"],self.row(self.b)["end"]),(0.0001234,32))
        self.assertIn("延长终点",format_gap(result))

    def test_stretch_and_move_use_actual_quantized_insertion_length(self):
        self.call("update","layer",id=self.root,data={"axis":{"unit":"秒","precision":0.1}})
        actions = [{"object_id":self.a,"action":"keep"}, {"object_id":self.b,"action":"stretch"},
                   {"object_id":self.c_image,"action":"move"}]
        result = insert_gap(self.c,self.p,at=10.25,length=0.24,layer_ids=[self.root],crossing_actions=actions)
        self.assertTrue(result["ok"],result)
        self.assertTrue(all(item["length"]==0.2 for item in result["data"]["gaps"]))
        self.assertEqual(self.row(self.b)["end"],30.2)
        self.assertEqual((self.row(self.c_image)["begin"],self.row(self.c_image)["end"]),(5.2,15.2))

    def test_all_four_crossing_actions_share_one_undoable_operation(self):
        moving = self.obj(self.lyrics,9,16,{"text":"移动"})
        later = self.obj(self.lyrics,28,30,{"text":"后续"})
        ids = [self.a,self.b,self.c_image,moving,later]
        original = [self.row(id) for id in ids]
        actions = self.actions()
        actions[1]["action"] = "stretch"
        actions.append({"object_id":moving,"action":"move"})
        result = insert_gap(self.c,self.p,at=10,length=2,layer_ids=[self.root],crossing_actions=actions)
        self.assertTrue(result["ok"],result)
        self.assertEqual([len(result["data"][key]) for key in ("splits","kept","stretched","moved","shifted")], [1,1,1,1,1])
        after = [self.row(id) for id in ids]
        logs = read_record(self.c,"change",filters={"operation_id":result["operation_id"]})
        self.assertEqual(len(logs),5)
        undone = self.undo(result)
        self.assertEqual([self.row(id) for id in ids],original)
        self.undo(undone)
        self.assertEqual([self.row(id) for id in ids],after)

    def test_failed_move_rolls_back_preceding_split_and_stretch(self):
        self.c.execute(f"CREATE TRIGGER block_move BEFORE UPDATE OF begin ON objects WHEN old.id={self.c_image} BEGIN SELECT RAISE(ABORT,'move blocked'); END")
        before = self.snapshot()
        actions = self.actions()
        actions[1]["action"] = "stretch"
        actions[2]["action"] = "move"
        result = insert_gap(self.c,self.p,at=10,length=2,layer_ids=[self.root],crossing_actions=actions)
        self.assertFalse(result["ok"])
        self.assertEqual(self.snapshot(),before)

    def test_stretch_move_cli_and_command_help_explain_the_same_choices(self):
        description = command_help("insert_gap")["items"][0]
        self.assertIn("stretch",description["parameters"]["crossing_actions"]["description"])
        self.assertIn("move",description["parameters"]["crossing_actions"]["description"])
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder)/"test.sqlite3"
            c = open_database(db)
            self.c.backup(c)
            c.close()
            payload = Path(folder)/"actions.json"
            payload.write_text(json.dumps([{"object_id":self.a,"action":"move"}, {"object_id":self.b,"action":"stretch"},
                                           {"object_id":self.c_image,"action":"keep"}]),encoding="utf-8")
            command = [sys.executable,"-X","utf8","-B","-m","tools.common.gaps",str(db),str(self.p),"10","2",
                       "--layer-ids",str(self.root),"--contents-file",str(payload),"--json"]
            run = subprocess.run(command,capture_output=True,text=True,encoding="utf-8")
            self.assertEqual(run.returncode,0,run.stderr)
            data = json.loads(run.stdout)["data"]
            self.assertEqual(data["moved"][0]["id"],self.a)
            self.assertEqual(data["stretched"][0]["end"],32)

    def test_undo_end_preserves_later_information_and_does_not_issue_update_of_it(self):
        end = self.call("update", "object", id=self.a, data={"end": 14})
        self.call("update", "object", id=self.a, data={"information": {"text":"新内容"}})
        self.c.execute("CREATE TRIGGER protect_info BEFORE UPDATE OF information ON objects BEGIN SELECT RAISE(ABORT,'information must stay untouched'); END")
        u = self.undo(end)
        self.assertEqual(self.row(self.a)["end"], 12)
        self.assertEqual(self.row(self.a)["information"], {"text":"新内容"})
        self.call("update", "object", id=self.a, data={"tips":"后来备注"})
        self.undo(u)
        self.assertEqual((self.row(self.a)["end"],self.row(self.a)["tips"]), (14,"后来备注"))
        self.assertEqual(self.row(self.a)["information"], {"text":"新内容"})

    def test_same_top_level_field_conflicts_and_information_is_not_merged_inside(self):
        changed = self.call("update", "object", id=self.a, data={"information":{"text":"改稿","author":"A"}})
        self.call("update", "object", id=self.a, data={"information":{"text":"改稿","author":"B"}})
        before = self.snapshot()
        result = undo_operation(self.c, changed["operation_id"])
        self.assertFalse(result["ok"])
        conflict = result["error"]["conflicts"][0]
        self.assertEqual(conflict["comparison"], "fields")
        self.assertEqual([f["path"] for f in conflict["fields"]], [["information"]])
        self.assertEqual(self.snapshot(), before)

    def test_axis_is_also_one_whole_field(self):
        changed = self.call("update", "layer", id=self.root, data={"axis":{"unit":"秒","precision":0.1}})
        self.call("update", "layer", id=self.root, data={"axis":{"unit":"帧","precision":0.1}})
        result = undo_operation(self.c, changed["operation_id"])
        self.assertFalse(result["ok"])
        self.assertEqual([f["path"] for f in result["error"]["conflicts"][0]["fields"]], [["axis"]])

    def test_create_still_requires_whole_record_match(self):
        created = self.call("create", "object", data={"layer":self.lyrics,"config_ref":"objects/text.toml","information":{"text":"新建"}})
        self.call("update", "object", id=created["id"], data={"tips":"后续修改"})
        before = self.snapshot()
        result = undo_operation(self.c, created["operation_id"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["conflicts"][0]["comparison"], "record")
        self.assertEqual(self.snapshot(), before)

    def test_one_conflicting_field_prevents_the_entire_undo(self):
        changed = dispatch(self.c,[{"action":"update","kind":"object","project_id":self.p,"id":id,"data":{"end":50}} for id in (self.a,self.b)], checker=None)
        self.assertTrue(changed["ok"])
        self.call("update", "object", id=self.a, data={"information":{"text":"可保留"}})
        self.call("update", "object", id=self.b, data={"end":60})
        before = self.snapshot()
        result = undo_operation(self.c, changed["operation_id"])
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["error"]["conflicts"]),1)
        self.assertEqual(self.snapshot(), before)

    def test_cancelled_changes_in_a_batch_do_not_conflict_with_later_values(self):
        changed = dispatch(self.c,[{"action":"update","kind":"object","project_id":self.p,"id":self.a,"data":data}
                         for data in ({"end":14},{"end":12,"name":"changed"})], checker=None)
        self.call("update", "object", id=self.a, data={"end":18})
        self.undo(changed)
        self.assertEqual(self.row(self.a)["end"],18)
        self.assertEqual(self.row(self.a)["name"],"")

    def test_cli_omitted_scope_fails_before_any_write_and_keep_file_is_usable(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder)/"test.sqlite3"
            c = open_database(db)
            self.c.backup(c)
            c.close()
            base = [sys.executable,"-X","utf8","-B","-m","tools.common.gaps",str(db),str(self.p),"10","2"]
            run = subprocess.run([*base,"--json"],capture_output=True,text=True,encoding="utf-8")
            self.assertEqual(run.returncode,2)
            payload = Path(folder)/"keep.json"
            payload.write_text(json.dumps([{"object_id":self.c_image,"action":"keep"}]),encoding="utf-8")
            run = subprocess.run([*base,"--layer-id",str(self.background),"--contents-file",str(payload),"--json"],capture_output=True,text=True,encoding="utf-8")
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(json.loads(run.stdout)["data"]["kept"][0]["id"],self.c_image)


if __name__ == "__main__":
    unittest.main()

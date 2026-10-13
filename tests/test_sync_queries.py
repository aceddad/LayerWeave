"""同步更新保留引用、关联图边界与新命令；使用临时/内存数据库。"""
from contextlib import closing
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from layerweave.support.api import open_database, transaction, run_operation, read_record, register_tables, change_cursor
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.support.commands import command_help
from layerweave.tool.builtin.usage.editing.upsert import upsert_objects, upsert_objects_in_session
from layerweave.tool.builtin.usage.query.walk import walk_relations
from layerweave.tool.builtin.usage.undo.service import undo_operation


class Fixture(unittest.TestCase):
    def setUp(self):
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        with transaction(self.c) as w:
            self.p = w.create("project", {})["id"]
            self.layer = w.create("layer", {"type":"text", "config_ref":"layers/text.toml"}, project_id=self.p)["id"]
            self.other = w.create("layer", {"type":"text", "config_ref":"layers/text.toml"}, project_id=self.p)["id"]

    def obj(self, name="", *, project=None, layer=None, **values):
        with transaction(self.c) as w:
            return w.create("object", {"name":name, "config_ref":"objects/text.toml", "layer":self.layer if layer is None else layer,
                                        "information":{"text":"hello"}, **values}, project_id=self.p if project is None else project)

    def bind(self, source, destination, *, source_kind="object", target_kind="object", target_project=None):
        with transaction(self.c) as w:
            return w.create("bind", {"source_kind":source_kind, "source_project_id":self.p, "source_id":source,
                                     "target_kind":target_kind, "target_project_id":self.p if target_project is None else target_project,
                                     "target_id":destination})

    def sync(self, objects, **kwargs):
        return upsert_objects(self.c, self.p, self.layer, objects, checker=None, **kwargs)


class UpsertTests(Fixture):
    def test_update_preserves_id_bindings_notes_and_undo(self):
        obj = self.obj("开场", tips="keep")
        incoming = self.bind(self.other, obj["id"], source_kind="layer")
        outgoing = self.bind(obj["id"], self.layer, target_kind="layer")
        register_tables(self.c, {"note":{"fields":{"object_id":"INTEGER", "text":"TEXT"},
                                         "references":[{"fields":["project_id","object_id"],"kind":"object"}]}})
        with transaction(self.c) as w:
            note = w.create("note", {"object_id":obj["id"], "text":"评语"}, project_id=self.p)
        result = self.sync([{"name":"开场", "end":3, "information":{"text":"updated"}}])
        self.assertTrue(result["ok"], result)
        row = result["data"]["items"][0]["record"]
        self.assertEqual((row["id"], row["tips"]), (obj["id"], "keep"))
        self.assertEqual(read_record(self.c,"bind"), [incoming, outgoing])
        self.assertEqual(read_record(self.c,"note",project_id=self.p,id=note["id"]), note)
        self.assertTrue(undo_operation(self.c,result["operation_id"])["ok"])
        self.assertEqual(read_record(self.c,"object",project_id=self.p,id=obj["id"]), obj)

    def test_repeat_is_noop_no_extra_ids_or_logs(self):
        payload = [{"name":"A", "config_ref":"objects/text.toml", "information":{"text":"one"}, "end":0.1+0.2}]
        first = self.sync(payload)
        before = list(self.c.iterdump())
        again = self.sync(payload)
        self.assertTrue(first["ok"] and again["ok"])
        self.assertEqual(again["data"]["counts"], {"created":0,"updated":0,"unchanged":1})
        self.assertFalse(again["applied"])
        self.assertEqual(list(self.c.iterdump()), before)
        self.assertEqual(again["data"]["items"][0]["record"]["end"], 0.3)

    def test_stable_nested_key_allows_rename_and_information_is_replaced(self):
        old = self.obj("旧标题", information={"source":{"key":"scene_017"},"text":"old","extra":1})
        result = self.sync([{"name":"新标题", "information":{"source":{"key":"scene_017"},"text":"new"}}],
                           match_by="information.source.key")
        self.assertTrue(result["ok"], result)
        row = result["data"]["items"][0]["record"]
        self.assertEqual((row["id"],row["name"]), (old["id"],"新标题"))
        self.assertNotIn("extra", row["information"])

    def test_only_exact_matches_within_selected_layer_are_updated(self):
        old = self.obj("A longer")
        elsewhere = self.obj("A", layer=self.other)
        missing = self.obj("untouched")
        result = self.sync([{"name":"A", "config_ref":"objects/text.toml"}])
        self.assertEqual(result["data"]["counts"]["created"], 1)
        for row in (old,elsewhere,missing):
            self.assertEqual(read_record(self.c,"object",project_id=self.p,id=row["id"]),row)

    def test_ambiguity_and_duplicate_input_rollback_and_list_candidates(self):
        a, b = self.obj("same"), self.obj("same")
        before = list(self.c.iterdump())
        result = self.sync([{"name":"new", "config_ref":"objects/text.toml"},{"name":"same"}])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["candidate_ids"],[a["id"],b["id"]])
        self.assertEqual(list(self.c.iterdump()),before)
        repeated = self.sync([{"name":"x","config_ref":"objects/text.toml"},{"name":"x"}])
        self.assertEqual(repeated["error"]["code"],"duplicate_match_key")
        self.assertEqual(list(self.c.iterdump()),before)
        self.assertTrue(self.sync([{"name":"different","config_ref":"objects/text.toml"}])["ok"])

    def test_later_storage_failure_rolls_back_creation_and_number(self):
        before = list(self.c.iterdump())
        result = self.sync([{"name":"new","config_ref":"objects/text.toml"},{"name":"bad","config_ref":"objects/text.toml","txt":1}])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["request_index"],1)
        self.assertEqual(list(self.c.iterdump()),before)

    def test_keys_are_typed_and_missing_or_invalid_keys_fail(self):
        self.assertTrue(self.sync([{"name":"int","config_ref":"objects/text.toml","information":{"key":1}},
                                   {"name":"str","config_ref":"objects/text.toml","information":{"key":"1"}}],
                                  match_by="information.key")["ok"])
        for value in (None,True,1.2,{},[],""):
            with self.subTest(value=value):
                result = self.sync([{"information":{"key":value}}],match_by="information.key")
                self.assertEqual(result["error"]["code"],"missing_match_key")
        for path in ("id","information","information.",3):
            self.assertFalse(self.sync([],match_by=path)["ok"])
        self.assertFalse(self.sync([{"name":""}])["ok"])
        self.assertFalse(self.sync([{"name":"x","layer":self.other}])["ok"])
        self.assertTrue(self.sync([])["ok"])

    def test_session_helper_composes_and_checks_once_after_commit(self):
        called = []
        def check(changes, read):
            self.assertFalse(self.c.in_transaction)
            called.append(changes)
            return []
        def work(w):
            row = upsert_objects_in_session(w,self.p,self.layer,[{"name":"x","config_ref":"objects/text.toml"}])["items"][0]["record"]
            return w.update("object",row["id"],{"tips":"composed"},project_id=self.p)
        result = run_operation(self.c,work,checker=check)
        self.assertTrue(result["ok"])
        self.assertEqual(len(called),1)
        self.assertEqual(len(result["operation"]["changes"]),2)

    def test_default_checks_report_but_do_not_reject_content(self):
        result = upsert_objects(self.c,self.p,self.layer,[{"name":"bad content","config_ref":"objects/text.toml","information":{"text":42}}])
        self.assertTrue(result["ok"])
        self.assertTrue(result["checks"]["issues"])


class WalkTests(Fixture):
    def test_cycle_and_diamond_keep_edges_and_shortest_depth(self):
        a,b,c,d = [self.obj(name)["id"] for name in "ABCD"]
        for source,destination in ((a,b),(a,c),(b,d),(c,d),(d,a),(a,a)):
            self.bind(source,destination)
        result = walk_relations(self.c,self.p,"object",a)
        self.assertEqual([(n["id"],n["depth"]) for n in result["nodes"]],[(a,0),(b,1),(c,1),(d,2)])
        self.assertEqual(len(result["edges"]),6)
        self.assertFalse(result["truncated"])
        self.assertTrue(all(n["record"]["information"]["text"] == "hello" for n in result["nodes"]))

    def test_depth_direction_and_no_mutation(self):
        a,b,c = [self.obj()["id"] for _ in range(3)]
        self.bind(a,b)
        self.bind(b,c)
        before = list(self.c.iterdump())
        self.assertEqual(len(walk_relations(self.c,self.p,"object",a,max_depth=0)["nodes"]),1)
        shallow = walk_relations(self.c,self.p,"object",a,max_depth=1)
        self.assertEqual(len(shallow["nodes"]),2)
        self.assertFalse(shallow["truncated"])
        incoming = walk_relations(self.c,self.p,"object",c,direction="incoming")
        self.assertEqual([n["id"] for n in incoming["nodes"]],[c,b,a])
        self.assertEqual(len(walk_relations(self.c,self.p,"object",b,direction="both")["edges"]),2)
        self.assertEqual(list(self.c.iterdump()),before)

    def test_bounded_nodes_edges_and_disconnected_missing_targets(self):
        a,b,c = [self.obj()["id"] for _ in range(3)]
        self.bind(a,b)
        self.bind(a,c)
        self.bind(b,9999)
        self.bind(b,8888,target_kind="other")
        result = walk_relations(self.c,self.p,"object",a,max_nodes=2)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["truncation_reasons"],["max_nodes"])
        self.assertEqual(len(result["nodes"]),2)
        limited = walk_relations(self.c,self.p,"object",a,max_edges=1)
        self.assertEqual((len(limited["edges"]),limited["truncation_reasons"]),(1,["max_edges"]))
        full = walk_relations(self.c,self.p,"object",a)
        self.assertEqual([n["status"] for n in full["nodes"]], ["found","found","found","missing","unsupported_kind"])
        self.assertIsNone(full["nodes"][-1]["record"])
        self.assertFalse(full["truncated"])
        self.assertEqual(walk_relations(self.c,self.p,"object",7777)["nodes"][0]["status"],"missing")

    def test_full_identity_separates_same_number_in_other_project(self):
        a = self.obj()["id"]
        with transaction(self.c) as w:
            other = w.create("project", {})["id"]
            for _ in range(a):
                destination = w.create("layer", {"type":"text","config_ref":"layers/text.toml"},project_id=other)
        self.bind(a,a,target_kind="layer",target_project=other)
        graph = walk_relations(self.c,self.p,"object",a)
        self.assertEqual(len(graph["nodes"]),2)
        self.assertEqual(graph["nodes"][1]["record"],destination)

    def test_invalid_query_limits_fail(self):
        for args in ({"max_nodes":0},{"max_edges":0},{"max_depth":-1},{"max_depth":True},{"direction":"wrong"}):
            with self.assertRaises(ValueError):
                walk_relations(self.c,self.p,"layer",self.layer,**args)


class NewCommandTests(unittest.TestCase):
    def test_aliases_and_real_cli_upsert_then_walk(self):
        self.assertEqual([i["name"] for i in command_help(["overview","upsert","walk"])["items"]],
                         ["project_overview","upsert_objects","walk_relations"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"cli.sqlite3"
            with closing(open_database(path)) as c:
                c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
                with transaction(c) as w:
                    p = w.create("project",{})["id"]
                    layer = w.create("layer",{"type":"text","config_ref":"layers/text.toml"},project_id=p)["id"]
            payload = Path(folder)/"objects.json"
            payload.write_text(json.dumps([{"name":"A","config_ref":"objects/text.toml","information":{"text":"hi"}}]),encoding="utf-8")
            base = [sys.executable,"-X","utf8","-B","-m"]
            def run(module,args):
                result = subprocess.run([*base,module,*map(str,args)],capture_output=True,text=True,encoding="utf-8",timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                return json.loads(result.stdout)
            created = run("layerweave.tool.builtin.usage.editing.upsert",[path,p,layer,"--data-file",payload])
            self.assertTrue(created["ok"])
            again = run("layerweave.tool.builtin.usage.editing.upsert",[path,p,layer,"--data-file",payload])
            self.assertFalse(again["applied"])
            graph = run("layerweave.tool.builtin.usage.query.walk",[path,p,"object",created["data"]["items"][0]["record"]["id"]])
            self.assertEqual(graph["nodes"][0]["record"]["name"],"A")


if __name__ == "__main__":
    unittest.main()

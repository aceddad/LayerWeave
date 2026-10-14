"""交换工具的实际数据往返、跳过与引用转换；全部使用内存或临时库。"""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from layerweave.support.api import (open_database, transaction, read_record, run_operation, register_tables,
                                   table_specs, allocate)
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.tool.builtin.usage.exchange import (
    export_project, import_project, import_project_in_session, prepare_exchange, template_help, save_document, load_document)
from layerweave.tool.builtin.usage.undo.service import undo_operation


class ExchangeTests(unittest.TestCase):
    def database(self, path=":memory:"):
        c = open_database(path)
        self.addCleanup(c.close)
        c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        return c

    def setUp(self):
        self.c = self.database()
        with transaction(self.c) as w:
            self.p = w.create("project", {"name":"原项目", "tips":"说明"})["id"]
            self.a = w.create("layer", {"name":"故事", "type":"text", "config_ref":"layers/text.toml"}, project_id=self.p)["id"]
            self.child = w.create("layer", {"name":"子层", "type":"text", "config_ref":"layers/text.toml", "father":self.a}, project_id=self.p)["id"]
            self.b = w.create("layer", {"name":"独立根", "type":"text", "config_ref":"layers/text.toml"}, project_id=self.p)["id"]
            self.obj = w.create("object", {"name":"开场", "layer":self.child, "config_ref":"objects/text.toml",
                                          "begin":0, "end":2, "information":{"text":"旧正文"}}, project_id=self.p)["id"]
            self.late = w.create("object", {"name":"后段", "layer":self.child, "config_ref":"objects/text.toml",
                                           "begin":5, "end":8, "information":{"text":"后段"}}, project_id=self.p)["id"]
            self.bind = w.create("bind", {"source_kind":"object","source_project_id":self.p,"source_id":self.obj,
                                         "target_kind":"layer","target_project_id":self.p,"target_id":self.b})["id"]

    def document(self, items, **extra):
        return {"format_version":1,"project_id":self.p,"items":items,**extra}

    def apply(self, doc, **kwargs):
        return import_project(self.c,doc,checker=None,**kwargs)

    def nodes(self, document):
        def visit(items):
            for item in items:
                yield item
                yield from visit(item.get("children",[]))
        return [*visit(document.get("items",[])),*document.get("records",[])]

    def find(self, doc, kind, id):
        return next(node for node in self.nodes(doc) if node["kind"] == kind and node["id"] == id)

    def tools(self):
        register_tables(self.c,{
            "note":{"fields":{"object_id":"INTEGER","text":"TEXT"},
                    "references":[{"fields":["project_id","object_id"],"kind":"object"}]},
            "view_state":{"id_source":"provided","fields":{"collapsed":{"type":"INTEGER","default":0}},
                          "references":[{"fields":["project_id","id"],"kind":"layer"}]},
            "global_note":{"scoped":False,"fields":{"owner":"INTEGER","object_id":"INTEGER","text":"TEXT"},
                           "references":[{"fields":["owner","object_id"],"kind":"object"}]},
            "catalog":{"scoped":False,"fields":{"text":"TEXT"}}
        })
        with transaction(self.c) as w:
            self.note = w.create("note",{"object_id":self.obj,"text":"批注"},project_id=self.p)["id"]
            w.create("view_state",{"id":self.child,"collapsed":1},project_id=self.p)
            w.create("global_note",{"owner":self.p,"object_id":self.obj,"text":"相关全局记录"})
            w.create("catalog",{"text":"不属于某个项目"})

    def test_roundtrip_update_is_noop_and_readonly_export(self):
        before = list(self.c.iterdump())
        doc = export_project(self.c,self.p)
        self.assertEqual(list(self.c.iterdump()),before)
        self.assertEqual(len(doc["items"]),2)
        self.assertNotIn("max_id",doc["project"]["data"])
        result = self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertFalse(result["applied"])
        self.assertEqual(result["data"]["counts"]["unchanged"],6)
        self.assertEqual(list(self.c.iterdump()),before)

    def test_edit_export_preserves_ids_bindings_and_undo(self):
        doc = export_project(self.c,self.p)
        self.find(doc,"object",self.obj)["data"]["information"]["text"] = "新版"
        result = self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertEqual(result["data"]["counts"]["updated"],1)
        self.assertEqual(len(read_record(self.c,"bind")),1)
        self.assertTrue(undo_operation(self.c,result["operation_id"],checker=None)["ok"])
        self.assertEqual(read_record(self.c,"object",project_id=self.p,id=self.obj)["information"]["text"],"旧正文")

    def test_whole_export_keeps_bind_with_deleted_source_and_partial_export_does_not_claim_it(self):
        with transaction(self.c) as w:
            orphan = w.create("bind",{"source_kind":"object","source_project_id":self.p,"source_id":9999,
                                      "target_kind":"layer","target_project_id":self.p,"target_id":self.a})
        whole = export_project(self.c,self.p)
        self.assertEqual(whole["counts"]["bind"],2)
        self.assertTrue(any(n["id"]==orphan["id"] for n in whole["records"]))
        self.assertIn({"kind":"object","project_id":self.p,"id":9999},whole["external_references"])
        self.assertFalse(self.apply(whole)["applied"])
        partial = export_project(self.c,self.p,layer_ids=[self.child])
        self.assertEqual(partial["counts"]["bind"],1)

    def test_add_to_existing_project_maps_all_ids_and_bind_endpoints(self):
        doc = export_project(self.c,self.p,op="add")
        result = self.apply(doc,project_id=self.p)
        self.assertTrue(result["ok"],result)
        mappings = {item["source"]["kind"]+":"+str(item["source"]["id"]): item["target"]["id"] for item in result["data"]["id_map"]}
        self.assertNotEqual(mappings[f"object:{self.obj}"],self.obj)
        bound = read_record(self.c,"bind",id=mappings[f"bind:{self.bind}"])
        self.assertEqual(bound["source_id"],mappings[f"object:{self.obj}"])
        self.assertEqual(bound["target_id"],mappings[f"layer:{self.b}"])
        self.assertEqual(read_record(self.c,"object",project_id=self.p,id=mappings[f"object:{self.obj}"])["layer"],mappings[f"layer:{self.child}"])
        self.assertTrue(undo_operation(self.c,result["operation_id"],checker=None)["ok"])

    def test_cross_database_copy_includes_tool_definitions_and_declared_references(self):
        self.tools()
        doc = export_project(self.c,self.p,op="add")
        self.assertEqual(doc["omitted_tool_records"],{"catalog":1})
        other = self.database()
        with transaction(other) as w:
            w.create("project",{"name":"已有项目"})
        result = import_project(other,doc,checker=None)
        self.assertTrue(result["ok"],result)
        target = result["data"]["project_id"]
        self.assertNotEqual(target,self.p)
        maps = {(m["source"]["kind"],m["source"]["id"]):m["target"]["id"] for m in result["data"]["id_map"]}
        note = read_record(other,"note",project_id=target)[0]
        self.assertEqual(note["object_id"],maps[("object",self.obj)])
        state = read_record(other,"view_state",project_id=target)[0]
        self.assertEqual(state["id"],maps[("layer",self.child)])
        global_note = read_record(other,"global_note")[0]
        self.assertEqual((global_note["owner"],global_note["object_id"]),(target,maps[("object",self.obj)]))
        self.assertEqual(read_record(other,"catalog"),[])
        self.assertTrue(undo_operation(other,result["operation_id"],checker=None)["ok"])
        self.assertIn("view_state",table_specs(other))  # 建表与业务撤销分开。
        self.assertEqual(read_record(other,"project",id=target),None)

    def test_all_global_records_can_be_explicitly_exported(self):
        self.tools()
        doc = export_project(self.c,self.p,include_global=True)
        self.assertEqual(doc["omitted_tool_records"],{})
        self.assertEqual(doc["counts"]["catalog"],1)
        result = self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertFalse(result["applied"])

    def test_declared_global_dependencies_are_included_without_all_global_rows(self):
        register_tables(self.c, {
            "lookup":{"scoped":False,"fields":{"text":"TEXT"}},
            "tagged_note":{"fields":{"lookup_id":"INTEGER"},"references":[{"fields":["lookup_id"],"kind":"lookup"}]}
        })
        with transaction(self.c) as w:
            chosen=w.create("lookup",{"text":"used"})["id"]
            w.create("lookup",{"text":"unused"})
            w.create("tagged_note",{"lookup_id":chosen},project_id=self.p)
        doc=export_project(self.c,self.p,op="add")
        self.assertEqual(doc["counts"]["lookup"],1)
        self.assertEqual(doc["omitted_tool_records"]["lookup"],1)
        other=self.database()
        result=import_project(other,doc,checker=None)
        self.assertTrue(result["ok"],result)
        self.assertEqual(result["data"]["status"],"completed")

    def test_parent_mismatch_skips_entire_branch_but_other_root_commits(self):
        doc = self.document([
            {"kind":"layer","id":self.a,"children":[
                {"kind":"layer","id":self.b,"op":"update","data":{"name":"错归属"},"children":[
                    {"kind":"object","op":"add","key":"skipped","data":{"config_ref":"objects/text.toml"}}]}]},
            {"kind":"layer","id":self.b,"op":"update","data":{"name":"正确修改"}}])
        # 同一身份不重复声明；独立分支选择另一个实体。
        doc["items"][1] = {"kind":"object","id":self.late,"op":"update","data":{"tips":"正常"}}
        result = self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertEqual(result["data"]["status"],"partial")
        self.assertEqual(result["data"]["counts"]["skipped"],2)
        self.assertEqual(result["data"]["counts"]["updated"],1)
        self.assertEqual(read_record(self.c,"layer",project_id=self.p,id=self.b)["name"],"独立根")
        self.assertEqual(read_record(self.c,"object",project_id=self.p,id=self.late)["tips"],"正常")

    def test_skipped_new_target_does_not_fall_back_to_old_id_in_bind(self):
        doc = self.document([{"kind":"layer","id":self.a,"children":[
            {"kind":"layer","id":self.b,"children":[
                {"kind":"object","op":"add","key":"new","id":999,"data":{"config_ref":"objects/text.toml"}}]}]}],
            records=[{"kind":"bind","op":"add","refs":{"source":{"key":"new"},"target":{"kind":"layer","project_id":self.p,"id":self.a,"external":True}}}])
        result = self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertFalse(result["applied"])
        self.assertEqual(result["data"]["counts"]["skipped"],3)
        self.assertEqual(len(read_record(self.c,"bind")),1)

    def test_baseline_is_optional_and_checking_compares_original_state(self):
        doc = export_project(self.c,self.p,object_ids=[self.obj],include_baseline=True)
        self.find(doc,"object",self.obj)["data"]["information"]["text"] = "文件"
        with transaction(self.c) as w:
            w.update("object",self.obj,{"information":{"text":"其他人"}},project_id=self.p)
        result = self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertFalse(result["applied"])
        self.assertEqual(result["data"]["issues"][0]["code"],"source_changed")
        overwrite = self.apply(doc,check_baseline=False)
        self.assertTrue(overwrite["applied"],overwrite)
        self.assertEqual(read_record(self.c,"object",project_id=self.p,id=self.obj)["information"]["text"],"文件")

    def test_counter_only_changes_do_not_conflict_project_baseline(self):
        doc = export_project(self.c,self.p,include_baseline=True)
        with transaction(self.c):
            allocate("project_entities",data={"project_id":self.p})
        result = self.apply(doc)
        self.assertEqual(result["data"]["issues"],[])

    def test_update_does_not_implicitly_move_and_information_replaces_whole_field(self):
        doc = self.document([{"kind":"object","op":"update","id":self.obj,"data":{"information":{"new":1}}}])
        result = self.apply(doc)
        self.assertTrue(result["ok"],result)
        row = read_record(self.c,"object",project_id=self.p,id=self.obj)
        self.assertEqual(row["layer"],self.child)
        self.assertEqual(row["information"],{"new":1})

    def test_explicit_move_is_possible_without_false_parent_context(self):
        result = self.apply(self.document([{"kind":"object","id":self.obj,"op":"update","data":{"layer":self.b}}]))
        self.assertTrue(result["ok"],result)
        self.assertEqual(read_record(self.c,"object",project_id=self.p,id=self.obj)["layer"],self.b)

    def test_new_ids_are_ignored_as_storage_ids_and_key_forward_refs_work(self):
        doc = self.document([],records=[
            {"kind":"bind","op":"add","refs":{"source":{"key":"one"},"target":{"key":"two"}}},
            {"kind":"object","op":"add","key":"one","id":9999,"data":{"config_ref":"objects/text.toml"},
             "refs":{"layer":{"kind":"layer","project_id":self.p,"id":self.b,"external":True}}},
            {"kind":"layer","op":"add","key":"two","id":8888,"data":{"config_ref":"layers/text.toml"}}])
        result = self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertEqual(result["data"]["counts"]["created"],3)
        self.assertTrue(all(m["target"]["id"] not in {9999,8888} for m in result["data"]["id_map"]))

    def test_delete_parent_first_and_children_explicitly_and_undo(self):
        doc = export_project(self.c,self.p,layer_ids=[self.a],op="delete")
        result = self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertIsNone(read_record(self.c,"layer",project_id=self.p,id=self.a))
        self.assertIsNotNone(read_record(self.c,"layer",project_id=self.p,id=self.b))
        self.assertTrue(undo_operation(self.c,result["operation_id"],checker=None)["ok"])
        self.assertIsNotNone(read_record(self.c,"object",project_id=self.p,id=self.obj))

    def test_whole_project_delete_includes_tools(self):
        self.tools()
        result = self.apply(export_project(self.c,self.p,op="delete"))
        self.assertTrue(result["ok"],result)
        self.assertIsNone(read_record(self.c,"project",id=self.p))
        self.assertEqual(len(read_record(self.c,"catalog")),1)
        self.assertTrue(undo_operation(self.c,result["operation_id"],checker=None)["ok"])

    def test_deletion_does_not_implicitly_delete_unlisted_children(self):
        before = list(self.c.iterdump())
        result = self.apply(self.document([{"kind":"layer","id":self.a,"op":"delete"}]))
        self.assertFalse(result["ok"])
        self.assertEqual(list(self.c.iterdump()),before)

    def test_late_error_rolls_back_records_numbers_and_logs(self):
        before = list(self.c.iterdump())
        doc = self.document([{"kind":"layer","op":"add","data":{"config_ref":"layers/text.toml"}},
                             {"kind":"object","op":"update","id":self.obj,"data":{"unknown":1}}])
        result = self.apply(doc)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["pointer"],"/items/1")
        self.assertNotIn("data",result)
        self.assertEqual(list(self.c.iterdump()),before)

    def test_commit_failure_keeps_skip_diagnostics_without_leaking_new_id_map(self):
        before = list(self.c.iterdump())
        doc = self.document([{"kind":"layer","id":self.a,"op":"delete","children":[
            {"kind":"object","id":self.obj,"op":"delete"}]}])  # obj 直属 child，不直属 a。
        result = self.apply(doc)
        self.assertFalse(result["ok"])
        self.assertEqual(result["import_issues"][0]["code"],"parent_mismatch")
        self.assertNotIn("data",result)
        self.assertEqual(list(self.c.iterdump()),before)

    def test_project_baseline_conflict_skips_all_nodes(self):
        doc = export_project(self.c,self.p,include_baseline=True)
        with transaction(self.c) as w:
            w.update("project",self.p,{"name":"别处改名"})
        result = self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertFalse(result["applied"])
        self.assertEqual(result["data"]["counts"]["skipped"],6)
        self.assertEqual(result["data"]["project_action"],"skipped")

    def test_nested_new_tool_reference_can_use_key_and_existing_schema_keeps_extra_columns(self):
        register_tables(self.c,{"extra":{"fields":{"object_id":"INTEGER","text":"TEXT","later":"TEXT"},
                                          "references":[{"fields":["project_id","object_id"],"kind":"object"}]}})
        doc = self.document([{"kind":"layer","id":self.child,"children":[
            {"kind":"object","key":"new","op":"add","data":{"config_ref":"objects/text.toml"}}]}],
            records=[{"kind":"extra","op":"add","data":{"text":"note"},"refs":{"object_id":{"key":"new"}}}])
        definition={"table":"tool_extra","scoped":True,"id_source":"auto",
                    "fields":{"object_id":{"type":"INTEGER","nullable":True},"text":{"type":"TEXT","nullable":True}},
                    "references":table_specs(self.c)["extra"]["references"]}
        doc["tables"]={"extra":definition}
        result=self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertIn("later",table_specs(self.c)["extra"]["fields"])
        mapping=next(m for m in result["data"]["id_map"] if m["source"].get("key")=="new")
        self.assertEqual(read_record(self.c,"extra",project_id=self.p)[0]["object_id"],mapping["target"]["id"])

    def test_unresolved_new_cycles_are_reported_without_guessing_ids(self):
        definition={"fields":{"other":"INTEGER"},"references":[{"fields":["project_id","other"],"kind":"cycle"}]}
        doc=self.document([],tables={"cycle":definition},records=[
            {"kind":"cycle","op":"add","key":"a","refs":{"other":{"key":"b"}}},
            {"kind":"cycle","op":"add","key":"b","refs":{"other":{"key":"a"}}}])
        result=self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertFalse(result["applied"])
        self.assertEqual(result["data"]["counts"]["skipped"],2)
        self.assertEqual(result["data"]["issues"][0]["code"],"unresolved_dependency")

    def test_schema_survives_failed_business_stage_and_is_reported(self):
        doc = self.document([{"kind":"object","id":99999,"op":"delete"}],
                            tables={"custom":{"fields":{"text":"TEXT"}}})
        result = self.apply(doc)
        self.assertFalse(result["ok"])
        self.assertEqual(result["schema"]["prepared_kinds"],["custom"])
        self.assertIn("custom",table_specs(self.c))

    def test_handwritten_table_definition_reuses_implicit_project_reference(self):
        definition={"fields":{"object_id":"INTEGER"},"references":[{"fields":["project_id","object_id"],"kind":"object"}]}
        register_tables(self.c,{"handwritten":definition})
        doc=self.document([],tables={"handwritten":definition})
        result=self.apply(doc)
        self.assertTrue(result["ok"],result)
        changed=deepcopy(doc)
        changed["tables"]["handwritten"]["id_source"]="provided"
        rejected=self.apply(changed)
        self.assertFalse(rejected["ok"])
        self.assertEqual(table_specs(self.c)["handwritten"]["id_source"],"auto")

    def test_subtree_add_requires_external_parent_mapping_or_attachment(self):
        doc = export_project(self.c,self.p,layer_ids=[self.child],op="add")
        skipped = self.apply(doc,project_id=self.p)
        self.assertTrue(skipped["ok"],skipped)
        self.assertEqual(skipped["data"]["counts"]["created"],0)
        applied = self.apply(doc,project_id=self.p,parent_layer_id=self.b,external_refs="preserve")
        self.assertTrue(applied["ok"],applied)
        created_layer = next(m["target"]["id"] for m in applied["data"]["id_map"] if m["target"]["kind"]=="layer")
        self.assertEqual(read_record(self.c,"layer",project_id=self.p,id=created_layer)["father"],self.b)

    def test_external_ref_mapping_is_explicit(self):
        doc = export_project(self.c,self.p,object_ids=[self.obj],op="add")
        result = self.apply(doc,project_id=self.p,parent_layer_id=self.b,
                            reference_map=[{"source":{"kind":"layer","project_id":self.p,"id":self.b},
                                            "target":{"kind":"layer","project_id":self.p,"id":self.a}}])
        self.assertTrue(result["ok"],result)
        newbind = next(m["target"]["id"] for m in result["data"]["id_map"] if m["target"]["kind"]=="bind")
        self.assertEqual(read_record(self.c,"bind",id=newbind)["target_id"],self.a)

    def test_range_export_does_not_delete_context_layers_or_unmatched_objects(self):
        self.tools()
        with transaction(self.c) as w:
            layer_bind = w.create("bind",{"source_kind":"layer","source_project_id":self.p,"source_id":self.child,
                                          "target_kind":"layer","target_project_id":self.p,"target_id":self.b})
        doc = export_project(self.c,self.p,begin=0,end=2,op="delete")
        self.assertTrue(all("op" not in n for n in self.nodes(doc) if n["kind"]=="layer"))
        result = self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertIsNone(read_record(self.c,"object",project_id=self.p,id=self.obj))
        self.assertIsNotNone(read_record(self.c,"object",project_id=self.p,id=self.late))
        self.assertEqual(len(read_record(self.c,"layer",project_id=self.p)),3)
        self.assertIsNotNone(read_record(self.c,"bind",id=layer_bind["id"]))
        self.assertIsNotNone(read_record(self.c,"view_state",project_id=self.p,id=self.child))

    def test_delete_owns_project_linked_tools_but_preserves_shared_dependencies(self):
        register_tables(self.c,{
            "owned":{"scoped":False,"fields":{"owner":"INTEGER"},
                     "references":[{"fields":["owner"],"kind":"project"}]},
            "dictionary":{"scoped":False,"fields":{"text":"TEXT"}},
            "use_dictionary":{"fields":{"dictionary_id":"INTEGER"},
                              "references":[{"fields":["dictionary_id"],"kind":"dictionary"}]}
        })
        with transaction(self.c) as w:
            w.create("owned",{"owner":self.p})
            dictionary=w.create("dictionary",{"text":"shared"})
            w.create("use_dictionary",{"dictionary_id":dictionary["id"]},project_id=self.p)
        doc=export_project(self.c,self.p,op="delete")
        self.assertEqual(doc["counts"]["owned"],1)
        dependency=next(n for n in doc["records"] if n["kind"]=="dictionary")
        self.assertNotIn("op",dependency)
        result=self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertEqual(read_record(self.c,"owned"),[])
        self.assertEqual(read_record(self.c,"dictionary"),[dictionary])

    def test_raw_positions_survive_export_and_copy(self):
        with transaction(self.c) as w:
            w.restore("object",self.obj,{**w.read("object",project_id=self.p,id=self.obj),"end":0.123456789},project_id=self.p)
        doc = export_project(self.c,self.p,op="add")
        result = self.apply(doc)
        self.assertTrue(result["ok"],result)
        target=result["data"]["project_id"]
        obj = next(row for row in read_record(self.c,"object",project_id=target) if row["name"]=="开场")
        self.assertEqual(obj["end"],0.123456789)

    def test_provided_id_collision_does_not_overwrite(self):
        register_tables(self.c,{"external":{"scoped":False,"id_source":"provided","fields":{"text":"TEXT"}}})
        with transaction(self.c) as w:
            w.create("external",{"id":100,"text":"old"})
        doc=self.document([],records=[{"kind":"external","id":100,"op":"add","data":{"text":"new"}}])
        result=self.apply(doc)
        self.assertFalse(result["ok"])
        self.assertEqual(read_record(self.c,"external",id=100)["text"],"old")
        doc["records"][0]["data"]["id"]=101
        self.assertTrue(self.apply(doc)["ok"])

    def test_missing_op_provides_context_and_ignores_data(self):
        doc=self.document([{"kind":"layer","id":self.child,"data":{"name":"不执行"},"children":[
            {"kind":"object","id":self.obj,"op":"update","data":{"tips":"修改"}}]}])
        result=self.apply(doc)
        self.assertTrue(result["ok"],result)
        self.assertEqual(read_record(self.c,"layer",project_id=self.p,id=self.child)["name"],"子层")
        self.assertEqual(result["data"]["counts"]["selected"],1)

    def test_missing_id_is_error_and_duplicate_id_is_not_guessed(self):
        for items in ([{"kind":"object","id":99999,"op":"update"}],
                      [{"kind":"object","id":self.obj},{"kind":"object","id":self.obj,"op":"delete"}]):
            before=list(self.c.iterdump())
            result=self.apply(self.document(items))
            self.assertFalse(result["ok"])
            self.assertEqual(list(self.c.iterdump()),before)

    def test_in_session_composes_and_default_checker_runs_after_commit(self):
        checked=[]
        doc=self.document([{"kind":"object","id":self.obj,"op":"update","data":{"information":{"text":42}}}])
        def checker(changes,read):
            self.assertFalse(self.c.in_transaction)
            checked.append(changes)
            return []
        result=run_operation(self.c,lambda w: import_project_in_session(w,doc),checker=checker)
        self.assertTrue(result["ok"],result)
        self.assertEqual(len(checked),1)
        doc["items"][0]["data"]["information"]["text"]=43
        checked_result=import_project(self.c,doc)
        self.assertTrue(checked_result["ok"])
        self.assertTrue(checked_result["checks"]["issues"])

    def test_templates_discover_and_all_execute_and_undo(self):
        catalog=template_help()
        self.assertEqual({item["name"] for item in catalog["items"]},{"subtitles","storyboard","hand-drawn-video"})
        self.assertTrue(all("document" not in item for item in catalog["items"]))
        for item in catalog["items"]:
            with self.subTest(template=item["name"]):
                doc=template_help(item["name"])["items"][0]["document"]
                result=import_project(self.c,doc,new_project=True)
                self.assertTrue(result["ok"],result)
                self.assertEqual(result["data"]["status"],"completed")
                self.assertEqual(result["checks"]["issues"],[])
                self.assertTrue(undo_operation(self.c,result["operation_id"],checker=None)["ok"])

    def test_file_roundtrip_custom_template_and_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            doc=template_help("subtitles")["items"][0]["document"]
            doc["name"]="外部模板"
            path=save_document(doc,root/"templates"/"custom.json")
            self.assertEqual(load_document(path),doc)
            self.assertEqual(template_help("custom",template_root=root/"templates")["items"][0]["title"],"外部模板")
            db=root/"test.sqlite3"
            with closing(open_database(db)) as c:
                c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            base=[sys.executable,"-X","utf8","-B","-m","layerweave.tool.builtin.usage.exchange.cli"]
            def call(args):
                result=subprocess.run([*base,*map(str,args)],capture_output=True,text=True,encoding="utf-8",timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                return result.stdout
            result=json.loads(call(["apply",db,"--template","custom","--template-root",root/"templates","--new-project","--json"]))
            self.assertTrue(result["ok"],result)
            summary=json.loads(call(["export",db,result["data"]["project_id"],"--output",root/"export.json","--include-baseline"]))
            self.assertIn("path",summary)
            self.assertNotIn("items",summary)
            output=call(["apply",db,"--data-file",root/"export.json","--result-file",root/"result.json"])
            self.assertIn("未变化",output)
            self.assertFalse(json.loads((root/"result.json").read_text(encoding="utf-8"))["applied"])


if __name__ == "__main__":
    unittest.main()

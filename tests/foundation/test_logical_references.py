"""逻辑引用只携带语义；硬外键、撤销和复制策略各自保持边界。"""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from layerweave.support.api import open_database, register_tables, table_specs, transaction, run_operation, read_record
from layerweave.support.feedback import InputError
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.support.storage.references import dependent_records, missing_references
from layerweave.tool.builtin.usage.exchange import export_project, import_project, import_project_in_session, prepare_exchange
from layerweave.tool.builtin.usage.undo.service import undo_operation


FOLD = {"id_source":"provided", "fields":{"fold":{"type":"TEXT","default":""}},
        "logical_references":[{"fields":["project_id","id"],"kind":"layer"}]}
READ = {"id_source":"provided", "fields":{"reads":{"type":"TEXT","default":"{}"}},
        "logical_references":[{"fields":["project_id","id"],"kind":"object"}],
        "exchange":{"on_copy":"skip"}}


class LogicalReferenceTests(unittest.TestCase):
    def database(self, path=":memory:"):
        c = open_database(path)
        self.addCleanup(c.close)
        c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        return c

    def setUp(self):
        self.c = self.database()
        with transaction(self.c) as w:
            self.p = w.create("project",{"name":"source"})["id"]
            self.root = w.create("layer",{"type":"text","config_ref":"layers/text.toml","name":"root"},project_id=self.p)["id"]
            self.story = w.create("layer",{"type":"text","config_ref":"layers/text.toml","name":"story","father":self.root},project_id=self.p)["id"]
            self.note = w.create("object",{"layer":self.story,"config_ref":"objects/text.toml","information":{"text":"note"}},project_id=self.p)["id"]

    def states(self):
        register_tables(self.c,{"view_layer":FOLD,"view_note":READ})
        with transaction(self.c) as w:
            w.create("view_layer",{"id":self.story,"fold":"user"},project_id=self.p)
            w.create("view_note",{"id":self.note,"reads":json.dumps({"Claude":self.note})},project_id=self.p)

    def apply(self, connection, doc, **kwargs):
        return import_project(connection,doc,checker=None,**kwargs)

    def test_metadata_defaults_and_legacy_catalog_read_do_not_write(self):
        register_tables(self.c,{"legacy":{"fields":{"text":"TEXT"}}})
        self.c.execute("UPDATE _layerweave_tables SET definition=json_remove(definition,'$.logical_references','$.exchange')")
        self.c.commit()
        before=list(self.c.iterdump())
        spec=table_specs(self.c)["legacy"]
        self.assertEqual(spec["logical_references"],[])
        self.assertEqual(spec["exchange"],{"on_copy":"include"})
        self.assertEqual(list(self.c.iterdump()),before)
        register_tables(self.c,{"legacy":{"fields":{"text":"TEXT"}}})
        self.assertEqual(table_specs(self.c)["legacy"]["exchange"],{"on_copy":"include"})

    def test_adding_metadata_does_not_rebuild_table_or_rewrite_data_or_history(self):
        old={"id_source":"provided","fields":deepcopy(FOLD["fields"])}
        register_tables(self.c,{"view_layer":old})
        with transaction(self.c) as w:
            row=w.create("view_layer",{"id":self.story,"fold":"user"},project_id=self.p)
        schema=tuple(self.c.execute("SELECT sql,rootpage FROM sqlite_master WHERE name='tool_view_layer'").fetchone())
        history=read_record(self.c,"change")
        register_tables(self.c,{"view_layer":FOLD})
        self.assertEqual(tuple(self.c.execute("SELECT sql,rootpage FROM sqlite_master WHERE name='tool_view_layer'").fetchone()),schema)
        self.assertEqual(read_record(self.c,"view_layer",project_id=self.p,id=self.story),row)
        self.assertEqual(read_record(self.c,"change"),history)
        self.assertEqual({r["table"] for r in self.c.execute("PRAGMA foreign_key_list(tool_view_layer)")},{"projects"})

    def test_omitting_metadata_keeps_it_and_explicit_registration_can_clear_it(self):
        self.states()
        old={"id_source":"provided","fields":deepcopy(READ["fields"])}
        register_tables(self.c,{"view_note":old})
        self.assertEqual(table_specs(self.c)["view_note"]["logical_references"],READ["logical_references"])
        self.assertEqual(table_specs(self.c)["view_note"]["exchange"],{"on_copy":"skip"})
        register_tables(self.c,{"view_note":{**old,"logical_references":[],"exchange":{"on_copy":"include"}}})
        self.assertEqual(table_specs(self.c)["view_note"]["logical_references"],[])
        self.assertEqual(table_specs(self.c)["view_note"]["exchange"],{"on_copy":"include"})

    def test_metadata_survives_reopen_without_loading_any_view_code(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"metadata.sqlite3"
            with closing(open_database(path)) as c:
                c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
                register_tables(c,{"view_note":READ})
            with closing(open_database(path)) as c:
                self.assertEqual(table_specs(c)["view_note"]["logical_references"],READ["logical_references"])
                self.assertEqual(table_specs(c)["view_note"]["exchange"],READ["exchange"])

    def test_soft_target_absence_and_deletion_do_not_block_but_project_ownership_still_exists(self):
        register_tables(self.c,{"view_layer":FOLD})
        with transaction(self.c) as w:
            w.create("view_layer",{"id":999,"fold":"orphan"},project_id=self.p)
            w.create("view_layer",{"id":self.story,"fold":"user"},project_id=self.p)
            w.delete("object",self.note,project_id=self.p)
            w.delete("layer",self.story,project_id=self.p)
        orphan=read_record(self.c,"view_layer",project_id=self.p,id=self.story)
        self.assertIsNotNone(orphan)
        self.assertEqual(missing_references(self.c,"view_layer",orphan),[])
        self.assertEqual(dependent_records(self.c,("layer",self.p,self.story)),[])
        result=run_operation(self.c,lambda w: w.create("view_layer",{"id":1},project_id=9999))
        self.assertFalse(result["ok"])

    def test_old_hard_reference_still_blocks_deletion_and_cannot_be_silently_weakened(self):
        register_tables(self.c,{"hard":{"id_source":"provided","fields":{},
                                       "references":[{"fields":["project_id","id"],"kind":"layer"}]}})
        with transaction(self.c) as w:
            w.create("hard",{"id":self.story},project_id=self.p)
            w.delete("object",self.note,project_id=self.p)
        before=list(self.c.iterdump())
        self.assertFalse(run_operation(self.c,lambda w:w.delete("layer",self.story,project_id=self.p))["ok"])
        self.assertEqual(list(self.c.iterdump()),before)
        with self.assertRaises(InputError):
            register_tables(self.c,{"hard":{"id_source":"provided","fields":{},
                                           "logical_references":[{"fields":["project_id","id"],"kind":"layer"}]}})

    def test_soft_references_do_not_block_undo_or_redo_of_target_creation(self):
        register_tables(self.c,{"view_layer":FOLD})
        made=run_operation(self.c,lambda w:w.create("layer",{"type":"text","config_ref":"layers/text.toml"},project_id=self.p))
        id=made["data"]["id"]
        with transaction(self.c) as w:
            w.create("view_layer",{"id":id,"fold":"user"},project_id=self.p)
        undone=undo_operation(self.c,made["operation_id"],checker=None)
        self.assertTrue(undone["ok"],undone)
        self.assertIsNotNone(read_record(self.c,"view_layer",project_id=self.p,id=id))
        self.assertTrue(undo_operation(self.c,undone["operation_id"],checker=None)["ok"])
        self.assertIsNotNone(read_record(self.c,"layer",project_id=self.p,id=id))

    def test_invalid_metadata_rejects_atomically(self):
        cases=[
            {"logical_references":None},
            {"logical_references":[{"fields":["project_id","missing"],"kind":"layer"}]},
            {"logical_references":[{"fields":["id"],"kind":"layer"}]},
            {"logical_references":[{"fields":["project_id","id"],"kind":"unknown"}]},
            {"logical_references":[{"fields":["project_id","id"],"kind":"object"},{"fields":["project_id","id"],"kind":"layer"}]},
            {"exchange":{"on_copy":"reset"}},
            {"exchange":{"other":1}},
            {"exchange":None},
        ]
        for extra in cases:
            before=list(self.c.iterdump())
            with self.subTest(extra=extra), self.assertRaises(InputError):
                register_tables(self.c,{"candidate":{"id_source":"provided","fields":{},**extra}})
            self.assertEqual(list(self.c.iterdump()),before)

    def test_conflicting_hard_and_logical_targets_reject_but_identical_reference_deduplicates(self):
        hard={"id_source":"provided","fields":{},"references":[{"fields":["project_id","id"],"kind":"layer"}]}
        with self.assertRaises(InputError):
            register_tables(self.c,{"conflict":{**hard,"logical_references":[{"fields":["project_id","id"],"kind":"object"}]}})
        register_tables(self.c,{"same":{**hard,"logical_references":deepcopy(hard["references"])}})
        with transaction(self.c) as w:
            w.create("same",{"id":self.story},project_id=self.p)
        doc=export_project(self.c,self.p,op="add")
        result=self.apply(self.c,doc)
        self.assertTrue(result["ok"],result)
        self.assertEqual(result["data"]["status"],"completed")

    def test_view_layer_and_note_copy_shifted_ids_without_view_name_special_cases(self):
        self.states()
        target=self.database()
        with transaction(target) as w:
            q=w.create("project",{})["id"]
            w.create("layer",{"type":"text","config_ref":"layers/text.toml","name":"existing"},project_id=q)
        doc=export_project(self.c,self.p,op="add")
        result=self.apply(target,doc,project_id=q)
        self.assertTrue(result["ok"],result)
        mapping={(m["source"]["kind"],m["source"]["id"]):m["target"]["id"] for m in result["data"]["id_map"]}
        new_story=mapping[("layer",self.story)]
        self.assertNotEqual(new_story,self.story)
        self.assertEqual(read_record(target,"view_layer",project_id=q)[0]["id"],new_story)
        self.assertEqual(read_record(target,"view_note",project_id=q),[])
        self.assertEqual(result["data"]["counts"]["skipped"],1)
        self.assertEqual(result["data"]["issues"][0]["code"],"copy_policy")
        self.assertTrue(undo_operation(target,result["operation_id"],checker=None)["ok"])
        self.assertEqual(read_record(target,"view_layer",project_id=q),[])

    def test_same_database_copy_and_update_are_separate(self):
        self.states()
        doc=export_project(self.c,self.p)
        note=next(n for n in doc["records"] if n["kind"]=="view_note")
        note["data"]["reads"]='{"someone":123}'
        updated=self.apply(self.c,doc)
        self.assertTrue(updated["ok"],updated)
        self.assertEqual(updated["data"]["counts"]["skipped"],0)
        self.assertEqual(read_record(self.c,"view_note",project_id=self.p,id=self.note)["reads"],'{"someone":123}')
        doc["project"]["op"]="add"
        def add_nodes(values):
            for node in values:
                node["op"]="add"
                add_nodes(node.get("children",[]))
        add_nodes(doc["items"]); add_nodes(doc["records"])
        copied=self.apply(self.c,doc,project_id=self.p)
        self.assertTrue(copied["ok"],copied)
        self.assertEqual(copied["data"]["counts"]["skipped"],1)
        self.assertEqual(len(read_record(self.c,"view_layer",project_id=self.p)),2)
        self.assertEqual(len(read_record(self.c,"view_note",project_id=self.p)),1)

    def test_copy_skip_does_not_block_crud_or_fresh_exchange_add(self):
        self.states()
        with transaction(self.c) as w:
            w.create("view_note",{"id":999,"reads":"{}"},project_id=self.p)
            w.update("view_note",999,{"reads":'{"a":2}'},project_id=self.p)
        doc={"format_version":1,"project_id":self.p,"items":[
            {"kind":"object","op":"add","key":"new_note","data":{"config_ref":"objects/text.toml","information":{"text":"new"}},
             "refs":{"layer":{"kind":"layer","project_id":self.p,"id":self.story,"external":True}}}],
             "records":[{"kind":"view_note","op":"add","data":{"reads":"{}"},"refs":{"id":{"key":"new_note"}}}]}
        created=self.apply(self.c,doc)
        self.assertTrue(created["ok"],created)
        self.assertEqual(created["data"]["counts"]["created"],2)
        self.assertEqual(created["data"]["counts"]["skipped"],0)
        self.assertEqual(read_record(self.c,"view_note",project_id=self.p,id=999)["reads"],'{"a":2}')

    def test_fresh_provided_identity_is_written_in_data_id(self):
        register_tables(self.c,{"cache":{"id_source":"provided","fields":{"text":"TEXT"},"exchange":{"on_copy":"skip"}}})
        doc={"format_version":1,"project_id":self.p,"records":[
            {"kind":"cache","op":"add","data":{"id":73,"text":"new"}}]}
        result=self.apply(self.c,doc)
        self.assertTrue(result["ok"],result)
        self.assertEqual(result["data"]["counts"]["created"],1)
        doc["records"][0]={"kind":"cache","op":"add","id":73,"data":{"text":"copy"}}
        skipped=self.apply(self.c,doc)
        self.assertTrue(skipped["ok"])
        self.assertFalse(skipped["applied"])
        self.assertEqual(read_record(self.c,"cache",project_id=self.p,id=73)["text"],"new")

    def test_orphan_logical_identity_does_not_attach_to_same_number_in_destination(self):
        register_tables(self.c,{"view_layer":FOLD})
        with transaction(self.c) as w:
            w.create("view_layer",{"id":999,"fold":"orphan"},project_id=self.p)
        target=self.database()
        with transaction(target) as w:
            q=w.create("project",{})["id"]
            w.restore("layer",999,{"project_id":q,"id":999,"name":"unrelated","type":"text","config_ref":"layers/text.toml",
                                   "father":None,"axis":None,"tips":""},project_id=q)
        result=self.apply(target,export_project(self.c,self.p,op="add"),project_id=q)
        self.assertTrue(result["ok"],result)
        self.assertEqual(result["data"]["counts"]["skipped"],1)
        self.assertEqual(result["data"]["issues"][0]["code"],"external_reference")
        self.assertEqual(read_record(target,"view_layer",project_id=q),[])

    def test_partial_exports_collect_logical_children_and_forward_tool_dependencies(self):
        self.states()
        register_tables(self.c,{"labels":{"scoped":False,"fields":{"text":"TEXT"}},
                                "annotation":{"fields":{"object_id":"INTEGER","label_id":"INTEGER"},
                                               "logical_references":[{"fields":["project_id","object_id"],"kind":"object"},
                                                                     {"fields":["label_id"],"kind":"labels"}]}})
        with transaction(self.c) as w:
            label=w.create("labels",{"text":"label"})
            w.create("annotation",{"object_id":self.note,"label_id":label["id"]},project_id=self.p)
        selected=export_project(self.c,self.p,object_ids=[self.note])
        self.assertEqual(selected["counts"]["view_note"],1)
        self.assertEqual(selected["counts"]["annotation"],1)
        self.assertEqual(selected["counts"]["labels"],1)
        self.assertEqual(selected["counts"]["view_layer"],0)
        tree=export_project(self.c,self.p,layer_ids=[self.story])
        self.assertEqual(tree["counts"]["view_layer"],1)
        # 普通业务列和全局独立表的编号也按声明转换，不局限于复用主键的状态表。
        target=self.database()
        register_tables(target,{"labels":{"scoped":False,"fields":{"text":"TEXT"}}})
        with transaction(target) as w:
            q=w.create("project",{})["id"]
            layer=w.create("layer",{"type":"text","config_ref":"layers/text.toml"},project_id=q)["id"]
            w.create("labels",{"text":"existing"})
        result=self.apply(target,export_project(self.c,self.p,object_ids=[self.note],op="add"),project_id=q,
                          reference_map=[{"source":{"kind":"layer","project_id":self.p,"id":self.story},
                                          "target":{"kind":"layer","project_id":q,"id":layer}}])
        self.assertTrue(result["ok"],result)
        copied=read_record(target,"annotation",project_id=q)[0]
        self.assertNotEqual(copied["object_id"],self.note)
        self.assertNotEqual(copied["label_id"],label["id"])
        self.assertEqual(read_record(target,"object",project_id=q,id=copied["object_id"])["layer"],layer)
        self.assertEqual(read_record(target,"labels",id=copied["label_id"])["text"],"label")

    def test_deleted_targets_and_existing_orphan_states_survive_full_export_without_being_rebound(self):
        self.states()
        deleted=self.apply(self.c,export_project(self.c,self.p,op="delete"))
        self.assertTrue(deleted["ok"],deleted)  # copy 策略不影响显式删除。
        self.assertEqual(deleted["data"]["counts"]["skipped"],0)
        self.assertTrue(undo_operation(self.c,deleted["operation_id"],checker=None)["ok"])
        self.assertEqual(len(read_record(self.c,"view_note",project_id=self.p)),1)

    def test_old_source_file_cannot_erase_destination_metadata(self):
        self.states()
        doc=export_project(self.c,self.p,op="add")
        for definition in doc["tables"].values():
            definition["logical_references"]=[]
            definition["exchange"]={"on_copy":"include"}
        target=self.database()
        register_tables(target,{"view_layer":FOLD,"view_note":READ})
        result=self.apply(target,doc,new_project=True)
        self.assertTrue(result["ok"],result)
        self.assertEqual(result["data"]["counts"]["skipped"],1)
        self.assertEqual(table_specs(target)["view_layer"]["logical_references"],FOLD["logical_references"])
        self.assertEqual(table_specs(target)["view_note"]["exchange"],{"on_copy":"skip"})
        for definition in doc["tables"].values():
            definition.pop("logical_references")
            definition.pop("exchange")
        prepare_exchange(target,doc)
        self.assertEqual(table_specs(target)["view_note"]["exchange"],{"on_copy":"skip"})

    def test_import_enriches_old_destination_and_rejects_conflicting_mapping(self):
        self.states()
        target=self.database()
        register_tables(target,{"view_layer":{"id_source":"provided","fields":deepcopy(FOLD["fields"])}})
        doc=export_project(self.c,self.p,op="add")
        result=self.apply(target,doc,new_project=True)
        self.assertTrue(result["ok"],result)
        self.assertEqual(table_specs(target)["view_layer"]["logical_references"],FOLD["logical_references"])
        doc["tables"]["view_layer"]["logical_references"]=[{"fields":["project_id","id"],"kind":"object"}]
        before=list(target.iterdump())
        rejected=self.apply(target,doc,new_project=True)
        self.assertFalse(rejected["ok"])
        self.assertEqual(list(target.iterdump()),before)

    def test_skip_propagates_to_dependent_records_and_in_session_respects_policy(self):
        self.states()
        register_tables(self.c,{"dependent":{"fields":{"state_id":"INTEGER"},
                                             "logical_references":[{"fields":["project_id","state_id"],"kind":"view_note"}]}})
        with transaction(self.c) as w:
            w.create("dependent",{"state_id":self.note},project_id=self.p)
        doc=export_project(self.c,self.p,op="add")
        result=run_operation(self.c,lambda w:import_project_in_session(w,doc,project_id=self.p))
        self.assertTrue(result["ok"],result)
        self.assertEqual(result["data"]["counts"]["skipped"],2)
        self.assertEqual({issue["code"] for issue in result["data"]["issues"]},{"copy_policy","dependency_skipped"})
        self.assertEqual(len(read_record(self.c,"dependent",project_id=self.p)),1)

    def test_plain_unannotated_provided_ids_keep_old_semantics(self):
        register_tables(self.c,{"external":{"id_source":"provided","fields":{"text":"TEXT"}}})
        with transaction(self.c) as w:
            w.create("external",{"id":78,"text":"external id"},project_id=self.p)
        target=self.database()
        result=self.apply(target,export_project(self.c,self.p,op="add"),new_project=True)
        self.assertTrue(result["ok"],result)
        self.assertEqual(read_record(target,"external",project_id=result["data"]["project_id"])[0]["id"],78)


if __name__ == "__main__":
    unittest.main()

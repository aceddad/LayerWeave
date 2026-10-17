"""局部结构依赖与精简文档的往返；不丢工具数据和逻辑引用。"""
from copy import deepcopy
import unittest
import test_exchange as base
from layerweave.support.api import register_tables, transaction, read_record
from layerweave.tool.builtin.usage.exchange import export_project, import_project, prepare_exchange


class CompactExchangeTests(unittest.TestCase):
    setUp=base.ExchangeTests.setUp
    database=base.ExchangeTests.database
    tools=base.ExchangeTests.tools
    nodes=base.ExchangeTests.nodes
    find=base.ExchangeTests.find

    def test_partial_definitions_include_transitive_empty_and_cyclic_dependencies(self):
        register_tables(self.c,{
            'attached':{'fields':{'object_id':'INTEGER','lookup_id':{'type':'INTEGER','nullable':True}},
                'references':[{'fields':['project_id','object_id'],'kind':'object'}],
                'logical_references':[{'fields':['project_id','lookup_id'],'kind':'lookup'}]},
            'lookup':{'fields':{'other_id':{'type':'INTEGER','nullable':True}},
                'references':[{'fields':['project_id','other_id'],'kind':'attached'}]},
            'unrelated':{'fields':{'text':'TEXT'}}})
        with transaction(self.c) as w:
            w.create('attached',{'object_id':self.obj,'lookup_id':None},project_id=self.p)
        doc=export_project(self.c,self.p,object_ids=[self.obj])
        self.assertEqual(set(doc['tables']),{'attached','lookup'})
        self.assertEqual({r['kind'] for r in doc['records']},{'bind','attached'})
        target=self.database()
        prepared=prepare_exchange(target,doc)
        self.assertEqual(set(prepared['prepared_kinds']),{'attached','lookup'})
        full=export_project(self.c,self.p)
        self.assertIn('unrelated',full['tables'])
        empty=export_project(self.c,self.p,object_ids=[self.late])
        self.assertEqual(empty['tables'],{})

    def test_compact_keeps_tools_bindings_baseline_and_rejects_missing_kind(self):
        self.tools()
        doc=export_project(self.c,self.p,layer_ids=[self.child],compact=True,include_baseline=True)
        self.assertNotIn('tables',doc)
        self.assertNotIn('source_numbering',doc)
        self.assertTrue(doc['scope']['compact'])
        self.assertTrue(any(n['kind']=='note' for n in doc['records']))
        self.assertTrue(any(n['kind']=='bind' for n in doc['records']))
        self.find(doc,'object',self.obj)['data']['information']={'text':'修改正文'}
        self.find(doc,'note',self.note)['data']['text']='修改工具记录'
        result=import_project(self.c,doc,checker=None,external_refs='preserve')
        self.assertTrue(result['ok'],result)
        self.assertEqual(read_record(self.c,'note',project_id=self.p,id=self.note)['text'],'修改工具记录')
        self.assertEqual(read_record(self.c,'object',project_id=self.p,id=self.obj)['information']['text'],'修改正文')
        # 同一份旧基线不能覆盖刚写入的新内容。
        again=import_project(self.c,doc,checker=None)
        self.assertTrue(again['ok'],again)
        self.assertTrue(any(i['code']=='source_changed' for i in again['data']['issues']),again)
        target=self.database()
        copied=import_project(target,doc,new_project=True,checker=None)
        self.assertFalse(copied['ok'],copied)
        self.assertTrue(copied['error']['pointer'].endswith('/kind'),copied)
        self.assertEqual(read_record(target,'project'),[])

    def test_compact_copy_to_prepared_target_remaps_tool_references(self):
        self.tools()
        full=export_project(self.c,self.p,op='add')
        doc=export_project(self.c,self.p,op='add',compact=True)
        target=self.database()
        prepare_exchange(target,full)
        result=import_project(target,doc,new_project=True,checker=None)
        self.assertTrue(result['ok'],result)
        new=result['data']['project_id']
        objects=read_record(target,'object',project_id=new)
        notes=read_record(target,'note',project_id=new)
        self.assertEqual(len(notes),1)
        self.assertIn(notes[0]['object_id'],{o['id'] for o in objects})
        self.assertEqual(len(read_record(target,'bind')),1)


if __name__=='__main__':
    unittest.main()

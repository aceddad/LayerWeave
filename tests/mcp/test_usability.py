"""首次发现、署名、扩展说明和错误阶段；使用真实 MCP SDK 与临时数据库。"""
import asyncio
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from pathlib import Path
from tests._support.mcpfixture import MCPFixture, HAS_MCP
from layerweave.support.api import read_record, register_tables, transaction


@unittest.skipUnless(HAS_MCP, '安装 layerweave[mcp] 运行协议验收')
class MCPTrialTests(MCPFixture, unittest.TestCase):

    def test_first_use_discovers_overview_and_updates_from_help(self):
        overview = self.runtime.help()
        group = next(g for g in overview['groups'] if g['group'] == 'query')
        self.assertEqual(group['common'][0]['id'], 'layerweave.project_overview')
        for word, target in [('概览','project_overview'), ('总览','project_overview'),
                             ('更新','dispatch'), ('修改','dispatch')]:
            self.assertIn('layerweave.'+target, {i['id'] for i in self.runtime.help(search=word)['items']})
        detail = self.runtime.help(names=['dispatch'])['items'][0]
        self.assertEqual(len(detail['examples']), 4)
        for example in detail['examples']:
            args = deepcopy(example['arguments']['arguments'])
            requests = args['request'] if isinstance(args['request'], list) else [args['request']]
            for request in requests:
                if request['kind'] == 'object':
                    request.update(project_id=self.project, id=self.obj)
            outcome = self.runtime.invoke(example['tool'].removeprefix('layerweave_'), 'dispatch', args)
            self.assertFalse(outcome.is_error, outcome.data)
        self.assertEqual(read_record(self.c,'object',project_id=self.project,id=self.obj)['tips'], '待检查')
        missing = self.runtime.invoke('edit','dispatch', {'request':{
            'action':'update','kind':'object','id':self.obj,'data':{'tips':'不应写入'}}})
        self.assertTrue(missing.is_error)
        self.assertEqual(missing.data['error']['missing'],['project_id'])
        self.assertEqual(missing.data['error']['field'],'request')
        self.assertNotIn('note',missing.data)
        self.assertEqual(read_record(self.c,'object',project_id=self.project,id=self.obj)['tips'], '待检查')
        typo = self.runtime.invoke('edit','dispatch',{'request':[{
            'action':'update','kind':'object','project_id':self.project,'id':self.obj,'date':{}}]})
        self.assertTrue(typo.is_error)
        self.assertEqual(typo.data['error']['field'],'request.0')

    def test_dispatch_custom_kinds_and_cross_project_requests(self):
        register_tables(self.c, {'trial_record':{'fields':{'text':'TEXT'}}})
        new = self.call('edit','dispatch',request={'action':'create','kind':'project','data':{'name':'另一个'}})['result']['id']
        result = self.call('edit','dispatch',request=[
            {'action':'create','kind':'trial_record','project_id':self.project,'data':{'text':'一'}},
            {'action':'create','kind':'trial_record','project_id':new,'data':{'text':'二'}}])['result']
        self.assertEqual([r['project_id'] for r in result['results']], [self.project,new])
        self.assertEqual([r['data']['text'] for r in result['results']], ['一','二'])

    def test_all_help_examples_conform_and_reply_uses_its_own_description(self):
        for binding in self.runtime.catalog.bindings.values():
            with self.subTest(command=binding.id):
                detail = self.runtime.help(names=[binding.id])
                self.assertFalse(detail['issues'], detail)
                for sample in detail['items'][0]['examples']:
                    args = sample['arguments']
                    if sample['tool'] in ('layerweave_query','layerweave_edit','layerweave_admin'):
                        args = args['arguments']
                    self.runtime._arguments(binding, args)
        reply = self.runtime.help(names=['view_reply'])['items'][0]
        self.assertIn('author',reply['input_schema']['required'])
        self.assertNotIn('remove', json.dumps(reply['input_schema'],ensure_ascii=False))
        self.assertTrue(all(e['arguments'].get('author') == 'Claude' or
                            e['arguments'].get('arguments',{}).get('author') == 'Claude' for e in reply['examples']))

    def test_real_sdk_author_validation_waiting_and_undo(self):
        from mcp import Client
        from layerweave.tool.builtin.shared.mcp import create_server
        top = self.call('edit','view_note',action='add',text='请核对',author='用户')['result']['note']
        before = len(read_record(self.c,'change'))
        async def check():
            async with Client(create_server(self.runtime)) as client:
                for author in (None, '', '  ', '\n\t'):
                    for command in ('view_reply','view_note'):
                        args = {'note_id':top,'text':'拒绝此回复','author':author}
                        if command == 'view_note': args['action'] = 'reply'
                        result = await client.call_tool('layerweave_edit',{'command':command,'arguments':args})
                        self.assertTrue(result.is_error, result)
                        self.assertNotIn('note',result.structured_content)
                    direct = await client.call_tool('layerweave_view_reply',{'note_id':top,'text':'拒绝','author':author})
                    self.assertTrue(direct.is_error)
                omitted = await client.call_tool('layerweave_view_reply',{'note_id':top,'text':'缺署名'})
                self.assertTrue(omitted.is_error)
                add = await client.call_tool('layerweave_edit',{'command':'view_note','arguments':{'action':'add','text':'缺署名'}})
                self.assertTrue(add.is_error)
                self.assertEqual(len(read_record(self.c,'change')),before)
                result = await client.call_tool('layerweave_view_reply',{'note_id':top,'text':'已核对','author':'Claude'})
                self.assertFalse(result.is_error,result.structured_content)
                self.assertEqual(self.call('query','view_inbox',waiting='Claude')['result']['notes'], [])
                self.assertTrue(self.call('query','view_inbox',waiting='用户')['result']['notes'])
                undo = result.structured_content['undo']
                undone = await client.call_tool(undo['tool'],undo['arguments'])
                self.assertFalse(undone.is_error)
                self.assertTrue(self.call('query','view_inbox',waiting='Claude')['result']['notes'])
        asyncio.run(check())

    def test_external_recommendations_keywords_annotations_and_disable(self):
        source = self.root/'discovery.py'
        entries = [{'name':name,'summary':name,'keywords':['外部查询'],'help_order':order,
                    'entrypoint':'unimported:run','read_only':True,'input_schema':{'type':'object'},
                    'mcp':{'route':'query','group':'query','exposure':'direct','open_world':False}}
                   for name,order in [('z',2),('a',1)]]
        entries.append({'name':'plain','summary':'普通项','entrypoint':'unimported:run','read_only':True,
                        'input_schema':{'type':'object'},'mcp':{'route':'query','group':'query','exposure':'direct'}})
        source.write_text('raise RuntimeError("不可导入")\nCOMMANDS = '+repr(entries),encoding='utf-8')
        runtime = self.runtime_with(include_builtin=False,sources=[{'namespace':'outside','path':str(source)}])
        self.assertEqual([i['id'] for i in runtime.help()['groups'][0]['common']], ['outside.a','outside.z','outside.plain'])
        self.assertEqual(len(runtime.help(search='外部查询')['items']),2)
        self.assertTrue(runtime.invoke('query','外部查询',{}).is_error)
        from mcp import Client
        from layerweave.tool.builtin.shared.mcp import create_server
        async def check():
            async with Client(create_server(runtime)) as client:
                listed = {t.name:t.annotations.model_dump(by_alias=True) for t in (await client.list_tools()).tools}
                self.assertFalse(listed['outside_a']['openWorldHint'])
                self.assertTrue(listed['outside_plain']['openWorldHint'])
                self.assertTrue(listed['layerweave_help']['openWorldHint'])
                self.assertTrue(listed['layerweave_query']['openWorldHint'])
        asyncio.run(check())
        disabled = self.runtime_with(include_builtin=False,sources=[{'namespace':'outside','path':str(source)}],disabled=['outside.a'])
        self.assertNotIn('outside.a',[i['id'] for i in disabled.help()['groups'][0]['common']])

    def test_error_notes_distinguish_read_prepare_execution_and_committed(self):
        missing = self.runtime.invoke('edit','view_reply',{'note_id':1,'text':'缺作者'})
        self.assertNotIn('note',missing.data)
        wrong_route = self.runtime.invoke('edit','project_overview',{})
        self.assertNotIn('note',wrong_route.data)
        no_database = self.runtime.invoke('edit','dispatch',{'database':'absent.sqlite3',
            'request':{'action':'create','kind':'project','data':{}}})
        self.assertNotIn('note',no_database.data)
        def broken(*args, **kwargs): raise RuntimeError('未知阶段异常')
        with patch.object(self.runtime,'_function',return_value=broken):
            self.assertNotIn('note',self.runtime.invoke('query','project_overview',{}).data)
            uncertain = self.runtime.invoke('edit','dispatch',{'request':{'action':'create','kind':'project','data':{}}})
            self.assertIn('先核对',uncertain.data['note'])
        with patch.object(self.runtime.pages,'first',side_effect=RuntimeError('返回整理失败')):
            committed = self.runtime.invoke('edit','dispatch',{'request':{
                'action':'update','kind':'object','project_id':self.project,'id':self.obj,'data':{'tips':'已提交'}}})
        self.assertEqual(committed.data['operation']['status'],'committed')
        self.assertIn('已经提交',committed.data['note'])
        self.assertEqual(read_record(self.c,'object',project_id=self.project,id=self.obj)['tips'],'已提交')

    def test_compact_json_and_file_export_keep_same_data(self):
        plain = self.call('query','export_project',object_ids=[self.obj])['result']
        compact = self.call('query','export_project',object_ids=[self.obj],compact=True)['result']
        for key in ('items','records','external_references','counts'):
            self.assertEqual(compact[key],plain[key])
        self.assertNotIn('tables',compact)
        self.assertNotIn('source_numbering',compact)
        path = self.call('admin','export_project_file',object_ids=[self.obj],compact=True,output='compact.json')['result']['path']
        self.assertEqual(json.loads(Path(path).read_text(encoding='utf-8')), compact)
        compact['items'][0]['data']['tips']='直接修改'
        result = self.call('edit','import_project',document=compact)['result']
        self.assertEqual(result['operation']['status'],'committed')


if __name__ == '__main__':
    unittest.main()

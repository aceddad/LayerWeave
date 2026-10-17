"""真实 JSON 读写、统一暴露、可选扩展与 SDK 调用；仅使用临时项目。"""
import ast
import asyncio
import base64
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tests._support.mcpfixture import MCPFixture, HAS_MCP
import zipfile
from unittest.mock import patch

from layerweave.support.api import initialize_database, open_database, read_record
from layerweave.support.commands import discover_commands, command_help
from layerweave.tool.builtin.usage.records.dispatch import dispatch


@unittest.skipUnless(HAS_MCP,'安装 layerweave[mcp] 运行可选协议验收')
class MCPTests(MCPFixture, unittest.TestCase):


    def test_schemas_valid_aliases_and_optional_cli(self):
        from jsonschema import Draft202012Validator
        self.assertFalse(self.runtime.catalog.issues)
        for binding in self.runtime.catalog.bindings.values():
            Draft202012Validator.check_schema(binding.schema)
        self.assertEqual(self.runtime.catalog.resolve('export').id,'layerweave.export_project')
        self.assertEqual(self.runtime.catalog.resolve('view_screenshot').id,'layerweave.view_screenshot')
        source=self.root/'declarations.py'
        source.write_text("raise AssertionError('discovery must not import')\nCOMMANDS = "+repr([{
            'name':'sample','summary':'无 CLI','read_only':True,'input_schema':{'type':'object'},
            'entrypoint':'never_import:sample','mcp':{'route':'query'}}]),encoding='utf-8')
        commands,issues=discover_commands(include_builtin=False,installed=False,sources=[{'namespace':'alice','path':str(source)}])
        self.assertFalse(issues)
        self.assertEqual(commands[0]['id'],'alice.sample')
        self.assertNotIn('cli',commands[0])
        good={k:v for k,v in commands[0].items() if k not in {'parameters','source','source_root','namespace','id','import_root'}}
        bad={**deepcopy(good),'name':'bad','mcp':{'route':[]}}
        source.write_text('COMMANDS = '+repr([bad,good]),encoding='utf-8')
        runtime=self.runtime_with(include_builtin=False,sources=[{'namespace':'alice','path':str(source)}])
        self.assertIn('alice.sample',runtime.catalog.bindings)
        self.assertTrue(any(i['code']=='mcp_route' for i in runtime.catalog.issues))

    def test_json_export_import_without_files_and_default_scope(self):
        before=set(self.root.iterdir())
        exported=self.call('query','export_project',layer_ids=[self.layer])['result']
        exported['items'][0]['children'][0]['data']['information']={'text':'直接 JSON'}
        result=self.call('edit','import_project',document=exported)
        self.assertEqual(result['result']['operation']['status'],'committed')
        self.assertEqual(result['context']['project_id'],self.project)
        self.assertEqual(read_record(self.c,'object',id=self.obj,project_id=self.project)['information']['text'],'直接 JSON')
        self.assertEqual(before,set(self.root.iterdir()))
        self.assertIn('undo',result)
        undo=result['undo']['arguments']
        undone=self.runtime.invoke('edit',undo['command'],undo['arguments'])
        self.assertFalse(undone.is_error,undone.data)
        self.assertNotEqual(undone.data['result']['operation_id'],result['result']['operation_id'])
        self.assertEqual(read_record(self.c,'object',id=self.obj,project_id=self.project)['information']['text'],'原文')

    def test_new_project_does_not_receive_startup_default(self):
        result=self.call('edit','import_project',document={'format_version':1,'name':'新建','items':[]},new_project=True)
        self.assertNotEqual(result['result']['data']['project_id'],self.project)
        self.assertEqual(result['context']['project_id'],result['result']['data']['project_id'])

    def test_changed_database_requires_its_own_project(self):
        other=initialize_database(self.root/'other.sqlite3')
        result=self.runtime.invoke('query','project_overview',{'database':str(other)})
        self.assertTrue(result.is_error)
        self.assertIn('project_id',result.data['error']['missing'])

    def test_logical_root_and_archive_subdirectory_are_not_filesystem_paths(self):
        self.call('query','view_at',root=self.layer,at=11)
        self.call('query','view_layout',action='show',root=self.layer)
        archive=self.root/'skills.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for name in ('demo','other'):
                z.writestr('bundle/'+name+'/SKILL.md','---\nname: '+name+'\ndescription: sample\n---\nbody')
        result=self.call('admin','install_skill',archive=str(archive),source_dir='bundle/demo',layer='text',skills_root=str(self.root/'skills'))
        self.assertTrue((self.root/'skills/layers/text/demo/SKILL.md').is_file(),result)
        binding=self.runtime.catalog.resolve('view_plugin')
        values=self.runtime._arguments(binding,{'action':'add','target':'plugins/demo'})
        self.assertEqual(values['target'],str((self.root/'plugins/demo').resolve()))
        values=self.runtime._arguments(binding,{'action':'info','target':'alice.demo','catalog':'catalog/index.json'})
        self.assertEqual(values['target'],'alice.demo')
        self.assertEqual(values['catalog'],str((self.root/'catalog/index.json').resolve()))

    def test_help_documentation_only_and_action_examples(self):
        help_result=self.runtime.help(names=['layerweave.mcp_server','view_frame','view_walk','export_project_file'])
        self.assertFalse(help_result['issues'])
        self.assertEqual(help_result['items'][0]['availability'],'documentation_only')
        frame=help_result['items'][1]['examples'][0]['arguments']['arguments']
        self.assertIn('at',frame)
        self.assertTrue(frame['output'].endswith('.jpg'))
        walk=help_result['items'][2]['examples'][0]['arguments']['arguments']
        self.assertTrue(walk['start'].startswith('object:'))
        self.assertIn('path',help_result['items'][3]['returns'])

    def test_query_rejects_writes_and_batch_is_one_transaction(self):
        empty=self.call('query','dispatch',request=[])
        self.assertEqual(empty['result']['operation']['status'],'read')
        request=[{'action':'update','kind':'object','project_id':self.project,'id':self.obj,'data':{'name':'first'}},
                 {'action':'update','kind':'object','project_id':self.project,'id':self.obj,'data':{'tips':'second'}}]
        rejected=self.runtime.invoke('query','dispatch',{'request':request})
        self.assertTrue(rejected.is_error)
        self.assertEqual(read_record(self.c,'object',id=self.obj,project_id=self.project)['name'],'')
        result=self.call('edit','dispatch',request=request)['result']
        rows=read_record(self.c,'change',filters={'operation_id':result['operation_id']})
        self.assertEqual(len(rows),2)
        self.assertEqual({r['operation_id'] for r in rows},{result['operation_id']})

    def test_check_errors_do_not_turn_commit_into_failure(self):
        result=self.call('edit','dispatch',request={'action':'create','kind':'object','project_id':self.project,
            'data':{'layer':self.layer,'config_ref':'objects/not_found.toml','information':{'text':'保留'}}})
        self.assertEqual(result['result']['operation']['status'],'committed')
        self.assertTrue(result['result']['checks']['issues'])
        self.assertEqual(result['result']['data']['config_ref'],'objects/not_found.toml')

    def test_import_partial_is_single_committed_operation(self):
        document={'format_version':1,'project_id':self.project,'items':[
            {'kind':'object','id':self.obj,'op':'update','parent_id':999,'data':{'name':'跳过'}},
            {'kind':'layer','id':self.layer,'children':[
                {'kind':'object','op':'add','data':{'config_ref':'objects/text.toml','information':{'text':'成功'}}}]}]}
        result=self.call('edit','import_project',document=document)['result']
        self.assertEqual(result['operation']['status'],'committed')
        self.assertEqual(result['data']['status'],'partial')
        self.assertEqual(result['data']['counts']['skipped'],1)
        self.assertEqual(result['data']['counts']['created'],1)

    def test_disable_wins_over_direct_and_name_conflict_keeps_route(self):
        runtime=self.runtime_with(exposure={'layerweave.project_overview':'direct'},disabled=['layerweave.project_overview'])
        self.assertNotIn('layerweave_project_overview',runtime.catalog.direct)
        self.assertTrue(runtime.invoke('query','project_overview',{}).is_error)
        source=self.root/'names.py'
        items=[{'name':name,'summary':name,'read_only':True,'entrypoint':'external:test',
                'input_schema':{'type':'object'},'mcp':{'route':'query','exposure':'direct','name':'same_tool'}} for name in ('a','b')]
        source.write_text('COMMANDS = '+repr(items),encoding='utf-8')
        runtime=self.runtime_with(include_builtin=False,sources=[{'namespace':'example','path':str(source)}])
        self.assertNotIn('same_tool',runtime.catalog.direct)
        self.assertEqual(runtime.catalog.resolve('example.a').id,'example.a')
        self.assertTrue(any(i['code']=='direct_conflict' for i in runtime.catalog.issues))

    def test_skill_direct_returns_same_material_and_never_executes(self):
        root=self.root/'skills'; skill=root/'demo'; skill.mkdir(parents=True)
        (skill/'SKILL.md').write_text('---\nname: demo\ndescription: 示例\n---\n正文',encoding='utf-8')
        (skill/'evil.py').write_text("raise AssertionError('do not run')",encoding='utf-8')
        first=self.runtime_with(skills_roots=[str(root)])
        identity=first.catalog.skills[0]['id']
        second=self.runtime_with(skills_roots=[str(root)],exposure={identity:'direct'})
        binding=second.catalog.bindings[identity]
        self.assertIsNotNone(binding.direct_name)
        direct=second.invoke('query',identity,{})
        self.assertFalse(direct.is_error,direct.data)
        self.assertFalse(direct.data['result']['executed'])
        help_result=second.help(topic='skills',names=[identity])
        self.assertEqual(help_result['items'][0]['content'],direct.data['result']['content'])

    def test_file_exchange_is_optional_and_never_implicitly_overwrites(self):
        result=self.call('admin','export_project_file',layer_ids=[self.layer],output='exports/part.json')
        path=Path(result['result']['path'])
        self.assertTrue(path.is_absolute())
        original=path.read_bytes()
        second=self.runtime.invoke('admin','export_project_file',{'output':str(path)})
        self.assertTrue(second.is_error)
        self.assertEqual(path.read_bytes(),original)
        document=json.loads(original)
        document['items'][0]['children'][0]['data']['name']='文件修改'
        path.write_text(json.dumps(document),encoding='utf-8')
        result=self.call('edit','import_project_file',document_file=str(path))
        self.assertEqual(result['result']['operation']['status'],'committed')

    def test_pagination_does_not_reexecute_and_detects_changed_database(self):
        request=[{'action':'create','kind':'object','project_id':self.project,'data':{
            'layer':self.layer,'config_ref':'objects/text.toml','name':str(i),'information':{'text':str(i)}}} for i in range(5)]
        self.call('edit','dispatch',request=request)
        result=self.runtime.invoke('query','find_objects',{},limit=2)
        self.assertFalse(result.is_error,result.data)
        cursor=result.data['more']['cursor']
        self.assertIsNotNone(cursor)
        self.call('edit','dispatch',request={'action':'update','kind':'object','project_id':self.project,'id':self.obj,'data':{'name':'变化'}})
        follow=self.runtime.continue_result(cursor)
        self.assertTrue(follow.is_error)
        self.assertEqual(follow.data['error']['code'],'cursor_stale')

    def test_long_single_item_can_advance_and_write_status_survives_chunks(self):
        from layerweave.tool.builtin.shared.mcp.results import ResultPages
        pages=ResultPages(1)
        value={'context':{},'result':{'operation_id':'abc','operation':{'status':'committed','changes':[]},
                                     'items':[{'text':'长文字'*2000},{'text':'最后'}]}}
        page=pages.first(value,limit=1,max_chars=1200)
        self.assertEqual(page['operation_id'],'abc')
        count=0
        while page.get('more',{}).get('cursor'):
            page=pages.page(page['more']['cursor']); count+=1
            self.assertLess(count,100)
        self.assertGreater(count,1)

    def test_real_sdk_direct_and_routed_share_behavior(self):
        from mcp import Client
        from layerweave.tool.builtin.shared.mcp import create_server
        runtime=self.runtime_with(exposure={'layerweave.project_overview':'direct'})
        async def check():
            async with Client(create_server(runtime)) as client:
                listed=await client.list_tools()
                self.assertIn('layerweave_project_overview',{t.name for t in listed.tools})
                direct=await client.call_tool('layerweave_project_overview',{})
                routed=await client.call_tool('layerweave_query',{'command':'layerweave.project_overview','arguments':{}})
                self.assertFalse(direct.is_error,direct.structured_content)
                self.assertEqual(direct.structured_content,routed.structured_content)
                error=await client.call_tool('layerweave_query',{'command':'layerweave.project_overview','arguments':{'projet_id':1}})
                self.assertTrue(error.is_error)
                envelope_error=await client.call_tool('layerweave_query',{'command':'layerweave.project_overview','full':'false'})
                self.assertTrue(envelope_error.is_error)
                self.assertEqual(envelope_error.structured_content['error']['field'],'full')
                from mcp.shared.exceptions import MCPError
                with self.assertRaises(MCPError) as unknown:
                    await client.call_tool('not_a_registered_tool',{})
                self.assertEqual(unknown.exception.code,-32602)
        asyncio.run(check())

    def test_real_stdio_server_from_another_working_directory(self):
        from mcp import Client, StdioServerParameters
        config=self.root/'mcp.json'
        config.write_text(json.dumps(self.options),encoding='utf-8')
        async def check():
            transport=StdioServerParameters(command=sys.executable,
                args=['-X','utf8','-B','-m','layerweave.tool.builtin.shared.mcp','--config',str(config)],
                cwd=self.root,env={**os.environ,'PYTHONPATH':''})
            async with Client(transport) as client:
                listed=await client.list_tools()
                self.assertIn('layerweave_query',{t.name for t in listed.tools})
                result=await client.call_tool('layerweave_query',{'command':'project_overview','arguments':{}})
                self.assertFalse(result.is_error,result.structured_content)
                self.assertEqual(result.structured_content['result']['project']['id'],self.project)
        asyncio.run(check())

    def test_external_directory_can_execute_without_cli(self):
        module='layerweave_test_external'
        source=self.root/(module+'.py')
        declaration={'name':'echo','summary':'独立扩展','entrypoint':module+':echo','read_only':True,
            'input_schema':{'type':'object','properties':{'text':{'type':'string'}},'required':['text'],'additionalProperties':False},
            'mcp':{'route':'query','exposure':'direct'}}
        source.write_text("from pathlib import Path\nPath(__file__).with_suffix('.loaded').touch()\ndef echo(text):\n    return {'text':text}\nCOMMANDS = "+repr([declaration]),encoding='utf-8')
        self.addCleanup(lambda:sys.modules.pop(module,None))
        self.addCleanup(lambda:sys.path.remove(str(self.root)) if str(self.root) in sys.path else None)
        runtime=self.runtime_with(include_builtin=False,sources=[{'namespace':'alice','path':str(source),'import_root':str(self.root)}])
        self.assertFalse(source.with_suffix('.loaded').exists())
        self.assertIn('alice_echo',runtime.catalog.direct)
        result=runtime.invoke('query','alice.echo',{'text':'hello'})
        self.assertFalse(result.is_error,result.data)
        self.assertEqual(result.data['result'],{'text':'hello'})
        self.assertTrue(source.with_suffix('.loaded').exists())

    def test_only_mcp_package_can_discover_without_other_tool_packages(self):
        from layerweave.tool.builtin.shared.mcp import create_runtime
        runtime=create_runtime({'include_builtin':False,'installed':False,'skills_roots':[]})
        self.assertEqual(runtime.help()['groups'],[])
        self.assertTrue(runtime.invoke('query','project_overview',{}).is_error)

    def test_look_and_save_use_the_same_rendering_and_preserve_existing_file(self):
        from layerweave.tool.builtin.view.mcp import look, save_screenshot
        image=b'\x89PNG\r\n\x1a\nexample'
        def render(database,project_id,output,**options):
            Path(output).write_bytes(image)
            return {'output':str(output),'page':'temporary','size':[10,10]}
        with patch('layerweave.tool.builtin.view.screenshot.capture',side_effect=render):
            result=look(self.db,self.project)
            self.assertEqual(result['_image'],image)
            self.assertNotIn('output',result)
            destination=self.root/'shot.png'
            saved=save_screenshot(self.db,self.project,destination)
            self.assertEqual(saved['output'],str(destination.resolve()))
            with self.assertRaises(FileExistsError):
                save_screenshot(self.db,self.project,destination)
            self.assertEqual(destination.read_bytes(),image)

    def test_real_browser_image_is_returned_over_mcp_without_project_writes(self):
        from layerweave.tool.builtin.view.screenshot import find_browser
        if find_browser() is None:
            self.skipTest('本机没有浏览器')
        from mcp import Client
        from layerweave.tool.builtin.shared.mcp import create_server
        before=len(read_record(self.c,'change'))
        async def check():
            async with Client(create_server(self.runtime)) as client:
                result=await client.call_tool('layerweave_view_screenshot',{
                    'width':640,'height':480,'state_root':str(self.root/'view-state'),
                    'wait_ms':15000,'timeout_ms':45000},read_timeout_seconds=60)
                self.assertFalse(result.is_error,result.structured_content)
                images=[c for c in result.content if c.type=='image']
                self.assertEqual(len(images),1)
                image=base64.b64decode(images[0].data)
                self.assertTrue(image.startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertGreater(len(image),1000)
                self.assertFalse(result.structured_content['result']['saved'])
                self.assertNotIn('output',result.structured_content['result'])
        asyncio.run(check())
        self.assertEqual(len(read_record(self.c,'change')),before)

    def test_view_bindings_use_same_registry_and_reading_never_marks_read(self):
        listing=self.call('query','view_inbox')['result']
        self.assertEqual(listing['notes'],[])
        added=self.call('edit','view_note',action='add',text='检查这里',author='用户')['result']
        note_id=added['note']
        before=len(read_record(self.c,'change'))
        self.call('query','view_inbox')
        self.assertEqual(len(read_record(self.c,'change')),before)
        reply=self.call('edit','view_reply',note_id=note_id,text='已看过',author='AI')
        self.assertIn('operation_id',reply['result'])
        self.assertIn('undo',reply)


if __name__=='__main__':
    unittest.main()

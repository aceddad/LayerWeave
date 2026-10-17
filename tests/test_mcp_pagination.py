"""查询数量、回复页和业务游标分开；保留单个业务项的完整内容。"""
import asyncio
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import test_mcp as base
from layerweave.support.feedback import InputError
from layerweave.tool.builtin.shared.mcp.results import ResultPages, encoded
from layerweave.tool.builtin.usage.records.dispatch import dispatch


class ResultPagingTests(unittest.TestCase):
    def test_unique_outer_list_wins_over_long_nested_list(self):
        items=[{'id':i,'changes':list(range(100))} for i in range(8)]
        value={'context':{},'result':{'items':items,'count':8}}
        before=deepcopy(value)
        pages=ResultPages()
        page=pages.first(value,limit=3,max_chars=100000)
        self.assertEqual(page['more']['path'],['items'])
        self.assertEqual(page['result']['items'],items[:3])
        collected=page['result']['items'][:]
        while page['more']['cursor']:
            page=pages.page(page['more']['cursor'])
            collected.extend(page['result']['items'])
        self.assertEqual(collected,items)
        self.assertEqual(value,before)

    def test_root_list_and_nested_dictionary_wrapper(self):
        for result, path in [([1,2,3,4],[]),({'data':{'items':[1,2,3,4]}},['data','items'])]:
            with self.subTest(path=path):
                page=ResultPages().first({'result':result},limit=2,max_chars=10000)
                self.assertEqual(page['more']['path'],path)
                self.assertEqual(page['more']['remaining'],2)

    def test_parallel_lists_are_not_guessed_and_can_be_declared(self):
        value={'result':{'items':[{'id':i} for i in range(8)],'warnings':['a','b']}}
        unchanged=ResultPages().first(value,limit=2,max_chars=10000)
        self.assertTrue(unchanged['result_complete'])
        self.assertEqual(unchanged['result'],value['result'])
        page=ResultPages().first(value,limit=2,max_chars=10000,pagination={'items':['items']})
        self.assertEqual(page['more']['path'],['items'])
        self.assertEqual(len(page['result']['items']),2)
        self.assertEqual(page['result']['warnings'],['a','b'])

    def test_ambiguous_large_result_uses_explicit_whole_json_fragments(self):
        value={'result':{'a':list(range(400)), 'b':list(range(450))}}
        pages=ResultPages()
        page=pages.first(value,limit=2,max_chars=1200)
        text=''
        while True:
            self.assertEqual(page['fragment']['path'],[])
            self.assertEqual(page['fragment']['offset'],len(text))
            text+=page['fragment']['text']
            cursor=page['more']['cursor']
            if not cursor: break
            page=pages.page(cursor)
        self.assertEqual(json.loads(text),value)

    def test_business_cursor_is_released_only_after_all_items(self):
        original={'result':{'data':{'items':list(range(8)), 'next':99}}}
        pages=ResultPages()
        page=pages.first(original,limit=3,max_chars=10000,
                         pagination={'items':['data','items'],'next_cursor':['data','next']})
        while page['more']['has_more']:
            self.assertIsNone(page['result']['data']['next'])
            self.assertTrue(page['more']['business_cursor_pending'])
            self.assertEqual(page['more']['business_cursor_path'],['data','next'])
            page=pages.page(page['more']['cursor'])
        self.assertEqual(page['result']['data']['next'],99)
        self.assertFalse(page['more']['business_cursor_pending'])
        self.assertEqual(original['result']['data']['next'],99)

    def test_huge_single_item_fragments_preserve_whole_operation_and_next(self):
        operation={'operation_id':'large-op','changes':[{'text':'内容'*80,'id':i} for i in range(30)]}
        value={'result':{'items':[operation],'next_cursor':17}}
        pages=ResultPages()
        page=pages.first(value,limit=3,max_chars=1500,
                         pagination={'items':['items'],'next_cursor':['next_cursor']})
        content=''
        while 'fragment' in page:
            self.assertEqual(page['fragment']['path'],['items',0])
            self.assertEqual(page['fragment']['offset'],len(content))
            self.assertTrue(page['more']['business_cursor_pending'])
            content+=page['fragment']['text']
            page=pages.page(page['more']['cursor'])
        self.assertEqual(json.loads(content),operation)
        self.assertEqual(page['result']['items'],[])
        self.assertEqual(page['result']['next_cursor'],17)
        self.assertFalse(page['more']['has_more'])

    def test_indivisible_document_ignores_item_limit_but_respects_size(self):
        document={'result':{'format_version':1,'items':[{'id':i} for i in range(40)]}}
        pages=ResultPages()
        self.assertTrue(pages.first(document,limit=1,max_chars=10000,document=True)['result_complete'])
        with self.assertRaises(InputError) as caught:
            pages.first(document,limit=1,max_chars=256,document=True)
        self.assertEqual(caught.exception.details['code'],'result_too_large')
        self.assertTrue(pages.first(document,limit=1,max_chars=256,document=True,full=True)['result_complete'])

    def test_missing_declared_path_preserves_error_result(self):
        value={'result':{'ok':False,'error':{'message':'业务失败'}}}
        page=ResultPages().first(value,limit=1,max_chars=10000,pagination={'items':['items']})
        self.assertEqual(page['result'],value['result'])
        self.assertTrue(page['result_complete'])

    def test_whole_fragments_defer_business_cursor_until_reconstruction(self):
        value={'result':{'items':[1,2], 'description':'长说明'*1000, 'next_cursor':77}}
        pages=ResultPages()
        page=pages.first(value,limit=1,max_chars=1200,
                         pagination={'items':['items'],'next_cursor':['next_cursor']})
        content=''
        while True:
            self.assertEqual(page['fragment']['path'],[])
            self.assertEqual(page['more']['business_cursor_pending'],page['more']['has_more'])
            content+=page['fragment']['text']
            if not page['more']['has_more']: break
            page=pages.page(page['more']['cursor'])
        self.assertEqual(json.loads(content),value)


@unittest.skipUnless(base.HAS_MCP,'安装 layerweave[mcp] 运行协议验收')
class MCPPagingTests(unittest.TestCase):
    setUp=base.MCPTests.setUp
    call=base.MCPTests.call
    runtime_with=base.MCPTests.runtime_with

    def history_rows(self):
        for i in range(22):
            dispatch(self.c,{'action':'update','kind':'object','project_id':self.project,
                'id':self.obj,'data':{'tips':f'第 {i} 次'}},checker=None)
        latest=dispatch(self.c,[{'action':'update','kind':'object','project_id':self.project,
            'id':self.obj,'data':{'tips':f'批次 {i}'}} for i in range(27)],checker=None)
        return latest['operation_id']

    def test_history_outer_limit_pages_operations_and_never_reexecutes(self):
        latest=self.history_rows()
        from layerweave.tool.builtin.usage.history import service
        with patch.object(service,'read_history',wraps=service.read_history) as reader:
            outcome=self.runtime.invoke('query','read_history',{'project_id':self.project},limit=3,max_chars=1000000)
            self.assertFalse(outcome.is_error,outcome.data)
            page=outcome.data
            self.assertEqual(len(page['result']['items']),3)
            self.assertEqual(page['more']['path'],['items'])
            self.assertEqual(page['result']['items'][0]['operation_id'],latest)
            self.assertEqual(len(page['result']['items'][0]['changes']),27)
            ids=[]
            while True:
                ids.extend(i['operation_id'] for i in page['result']['items'])
                if not page['more']['has_more']: break
                self.assertIsNone(page['result']['next_cursor'])
                outcome=self.runtime.continue_result(page['more']['cursor'])
                self.assertFalse(outcome.is_error,outcome.data)
                page=outcome.data
            self.assertEqual(len(ids),20)
            self.assertEqual(len(set(ids)),20)
            self.assertEqual(reader.call_count,1)
            older=self.call('query','read_history',project_id=self.project,limit=3,before=page['result']['next_cursor'])['result']
            self.assertEqual(len(older['items']),3)
            self.assertFalse(set(ids)&{i['operation_id'] for i in older['items']})
            self.assertEqual(reader.call_count,2)

    def test_command_limit_is_independent_and_declared_in_help(self):
        self.history_rows()
        three=self.call('query','read_history',project_id=self.project,limit=3)['result']
        self.assertEqual(len(three['items']),3)
        outer=self.runtime.invoke('query','read_history',{'project_id':self.project,'limit':3},limit=2,max_chars=1000000)
        self.assertEqual(len(outer.data['result']['items']),2)
        last=self.runtime.continue_result(outer.data['more']['cursor'])
        self.assertEqual(len(last.data['result']['items']),1)
        self.assertEqual(last.data['result']['next_cursor'],three['next_cursor'])
        detail=self.runtime.help(names=['read_history'])['items'][0]
        self.assertEqual(detail['pagination'],{'items':['items'],'next_cursor':['next_cursor']})
        self.assertIn('arguments.limit',detail['input_schema']['properties']['limit']['description'])

    def test_external_parallel_results_declare_pagination_without_cli(self):
        import sys
        module='paging_extension'
        source=self.root/(module+'.py')
        declaration={'name':'read','summary':'分页扩展','read_only':True,'entrypoint':module+':read',
            'input_schema':{'type':'object'},'mcp':{'route':'query','pagination':{'items':['data','rows'],'next_cursor':['next']}}}
        source.write_text('def read():\n    return {"data":{"rows":[1,2,3,4]},"issues":[],"next":"token"}\nCOMMANDS = '+repr([declaration]),encoding='utf-8')
        self.addCleanup(lambda:sys.modules.pop(module,None))
        self.addCleanup(lambda:sys.path.remove(str(self.root)) if str(self.root) in sys.path else None)
        runtime=self.runtime_with(include_builtin=False,sources=[{'namespace':'custom','path':str(source),'import_root':str(self.root)}])
        page=runtime.invoke('query','custom.read',{},limit=2).data
        self.assertEqual(page['result']['data']['rows'],[1,2])
        self.assertIsNone(page['result']['next'])
        last=runtime.continue_result(page['more']['cursor']).data
        self.assertEqual(last['result']['data']['rows'],[3,4])
        self.assertEqual(last['result']['next'],'token')

    def test_project_details_pages_layers_without_cutting_their_objects(self):
        self.call('edit','dispatch',request={'action':'create','kind':'layer','project_id':self.project,
            'data':{'config_ref':'layers/text.toml','name':'另一个层'}})
        dispatch(self.c,[{'action':'create','kind':'object','project_id':self.project,
            'data':{'layer':self.layer,'config_ref':'objects/text.toml','begin':i,'end':i+1,
                    'information':{'text':str(i)}}} for i in range(4)],checker=None)
        page=self.runtime.invoke('query','project_details',{},limit=1,max_chars=100000).data
        self.assertEqual(page['more']['path'],['layers'])
        self.assertEqual(len(page['result']['layers']),1)
        self.assertEqual(len(page['result']['layers'][0]['objects']),5)
        last=self.runtime.continue_result(page['more']['cursor']).data
        self.assertEqual(len(last['result']['layers']),1)
        self.assertFalse(last['more']['has_more'])

    def test_sdk_limit_description_annotations_and_exchange_recommendations(self):
        from mcp import Client
        from layerweave.tool.builtin.shared.mcp import create_server
        async def check():
            async with Client(create_server(self.runtime)) as client:
                tools={t.name:t for t in (await client.list_tools()).tools}
                self.assertIn('arguments.limit',tools['layerweave_query'].input_schema['properties']['limit']['description'])
                for name in ('layerweave_view_inbox','layerweave_view_reply'):
                    self.assertFalse(tools[name].annotations.model_dump(by_alias=True)['openWorldHint'])
                self.assertTrue(tools['layerweave_view_screenshot'].annotations.model_dump(by_alias=True)['openWorldHint'])
                result=await client.call_tool('layerweave_help',{'limit':2})
                self.assertEqual(result.structured_content['more']['path'],['groups'])
                self.assertEqual(len(result.structured_content['result']['groups']),2)
        asyncio.run(check())
        group=next(g for g in self.runtime.help()['groups'] if g['group']=='exchange')
        self.assertEqual([i['id'] for i in group['common'][:2]],['layerweave.export_project','layerweave.import_project'])


if __name__=='__main__':
    unittest.main()

"""客户端说明保持简单，服务端仍验证完整规则；使用真实 SDK 调用。"""
import asyncio
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import patch

from tests._support.mcpfixture import MCPFixture, HAS_MCP


@unittest.skipUnless(HAS_MCP, '安装 layerweave[mcp] 运行协议验收')
class SchemaCompatibilityTests(MCPFixture, unittest.TestCase):
    def test_default_and_direct_tool_advertisements_have_compatible_roots(self):
        from mcp import Client
        from layerweave.tool.builtin.shared.mcp import create_server
        forbidden={'oneOf','anyOf','allOf','not','if','then','else'}
        async def check():
            for runtime in (self.runtime, self.runtime_with(exposure={key:'direct' for key in self.runtime.catalog.bindings})):
                server=create_server(runtime)
                async with Client(server) as client:
                    tools=(await client.list_tools()).tools
                    self.assertIn('layerweave_query', {t.name for t in tools})
                    for tool in tools:
                        self.assertEqual(tool.input_schema['type'], 'object')
                        self.assertFalse(forbidden & tool.input_schema.keys(), tool.name)
                    self.assertIn('oneOf',server.get_tool_input_schema('layerweave_query'))
                    if runtime is self.runtime:
                        self.assertEqual(len(tools),7)
        asyncio.run(check())

    def test_query_modes_fail_before_execution_and_cursor_remains_usable(self):
        from mcp import Client
        from layerweave.tool.builtin.shared.mcp import create_server
        async def check():
            async with Client(create_server(self.runtime)) as client:
                overview=await client.call_tool('layerweave_query',{'command':'project_overview','arguments':{}})
                self.assertFalse(overview.is_error,overview.structured_content)
                self.assertEqual(overview.structured_content['result']['project']['id'],self.project)
                page=await client.call_tool('layerweave_query',{'command':'read_history','arguments':{},'limit':1})
                cursor=page.structured_content['more']['cursor']
                self.assertTrue(cursor)
                with patch.object(self.runtime,'invoke',side_effect=AssertionError('invalid request executed')), \
                     patch.object(self.runtime,'continue_result',side_effect=AssertionError('invalid cursor request executed')):
                    cases=[({},'请提供'),({'command':'project_overview','cursor':cursor},'不能同时'),
                           ({'command':''},'command 不能为空'),({'cursor':''},'cursor 不能为空'),
                           ({'command':' \t'},'command 不能为空'),({'cursor':'\n'},'cursor 不能为空')]
                    for arguments,message in cases:
                        result=await client.call_tool('layerweave_query',arguments)
                        self.assertTrue(result.is_error,result)
                        error=result.structured_content['error']
                        self.assertEqual(error['code'],'request_schema')
                        self.assertIn(message,error['message'])
                continued=await client.call_tool('layerweave_query',{'cursor':cursor})
                self.assertFalse(continued.is_error,continued.structured_content)
                self.assertNotEqual(page.structured_content['result']['items'],continued.structured_content['result']['items'])
                found=await client.call_tool('layerweave_help',{'search':'init database'})
                self.assertEqual(found.structured_content['result']['items'][0]['id'],'layerweave.initialize_database')
        asyncio.run(check())

    def test_direct_tool_keeps_nested_schema_and_enforces_hidden_root_conditions(self):
        from mcp import Client
        from layerweave.tool.builtin.shared.mcp import create_server
        module='lw_schema_projection_fixture'
        source=self.root/(module+'.py')
        schema={'type':'object','properties':{'mode':{'enum':['small','large']},'size':{'type':'integer'},
                'payload':{'oneOf':[{'type':'integer'},{'type':'string'}]}},
                'required':['mode','size','payload'],'additionalProperties':False,
                'allOf':[{'if':{'properties':{'mode':{'const':'small'}}},'then':{'properties':{'size':{'maximum':3}}}}]}
        declaration={'name':'echo','summary':'组合规则示例','entrypoint':module+':echo','read_only':True,
                     'input_schema':schema,'mcp':{'route':'query','exposure':'direct'},
                     'examples':[{'arguments':{'mode':'large','size':4,'payload':'x'}}]}
        source.write_text('def echo(mode,size,payload):\n    return {"size":size,"payload":payload}\nCOMMANDS = '+repr([declaration]),encoding='utf-8')
        self.addCleanup(lambda:sys.modules.pop(module,None))
        self.addCleanup(lambda:sys.path.remove(str(self.root)) if str(self.root) in sys.path else None)
        runtime=self.runtime_with(include_builtin=False,sources=[{'namespace':'compat','path':str(source),'import_root':str(self.root)}])
        before=deepcopy(runtime.catalog.bindings['compat.echo'].schema)
        async def check():
            async with Client(create_server(runtime)) as client:
                tool=next(t for t in (await client.list_tools()).tools if t.name=='compat_echo')
                self.assertNotIn('allOf',tool.input_schema)
                self.assertEqual(tool.input_schema['properties']['payload'],schema['properties']['payload'])
                for args in ({'mode':'small','size':4,'payload':'x'}, {'mode':'large','size':4,'payload':[]}):
                    rejected=await client.call_tool('compat_echo',args)
                    self.assertTrue(rejected.is_error,rejected.structured_content)
                accepted=await client.call_tool('compat_echo',{'mode':'large','size':4,'payload':'x'})
                self.assertFalse(accepted.is_error,accepted.structured_content)
                self.assertEqual(accepted.structured_content['result'],{'size':4,'payload':'x'})
                details=runtime.help(names=['compat.echo'])
                self.assertFalse(details['issues'],details)
                self.assertIn('allOf',details['items'][0]['input_schema'])
        asyncio.run(check())
        self.assertEqual(runtime.catalog.bindings['compat.echo'].schema,before)


if __name__=='__main__': unittest.main()

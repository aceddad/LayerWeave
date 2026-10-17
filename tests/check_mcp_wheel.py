"""普通 wheel + 已安装 SDK 的 stdio 验收；子进程禁用 site，不读取源码安装路径。"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from mcp import Client, StdioServerParameters
import mcp


def check(wheel):
    with tempfile.TemporaryDirectory(prefix='layerweave-mcp-wheel-') as folder:
        root=Path(folder); target=root/'installed'; work=root/'work'; work.mkdir()
        installed=subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-deps',
                                  '--target',str(target),str(wheel)],capture_output=True,text=True,encoding='utf-8',timeout=60)
        assert installed.returncode==0,installed.stdout+installed.stderr
        config=work/'mcp.json'
        config.write_text(json.dumps({'workspace':str(work),'installed':False,'skills_roots':[],
                                      'exposure':{'layerweave.project_overview':'direct'}}),encoding='utf-8')
        dependencies=Path(mcp.__file__).resolve().parents[1]
        bootstrap=f'''
import sys,runpy,os
from pathlib import Path
sys.path.insert(0,{str(target)!r})
sys.path.append({str(dependencies)!r})
for relative in ('win32','win32/lib','Pythonwin'):
    dependency=Path({str(dependencies)!r})/relative
    if dependency.is_dir(): sys.path.append(str(dependency))
if os.name=='nt':
    dll_directory=os.add_dll_directory(str(Path({str(dependencies)!r})/'pywin32_system32'))
import layerweave
assert Path(layerweave.__file__).resolve().is_relative_to(Path({str(target)!r}))
sys.argv=['layerweave-mcp','--config',{str(config)!r}]
runpy.run_module('layerweave.tool.builtin.shared.mcp',run_name='__main__')
'''
        async def exercise(mode):
            transport=StdioServerParameters(command=sys.executable,args=['-X','utf8','-B','-S','-c',bootstrap],
                cwd=work,env={**os.environ,'PYTHONPATH':''})
            async with Client(transport,mode=mode) as client:
                listing=await client.list_tools()
                assert 'layerweave_project_overview' in {t.name for t in listing.tools}
                reply=next(t for t in listing.tools if t.name=='layerweave_view_reply')
                assert 'author' in reply.input_schema['required']
                assert reply.annotations.model_dump(by_alias=True)['openWorldHint'] is False
                found=await client.call_tool('layerweave_help',{'search':'修改'})
                assert any(i['id']=='layerweave.dispatch' for i in found.structured_content['result']['items'])
                created=await client.call_tool('layerweave_admin',{'command':'layerweave.initialize_database','arguments':{'path':mode+'.db'}})
                assert not created.is_error,created.structured_content
                project=await client.call_tool('layerweave_edit',{'command':'layerweave.dispatch','arguments':{
                    'database':mode+'.db','request':{'action':'create','kind':'project','data':{'name':'wheel MCP'}}}})
                assert not project.is_error,project.structured_content
                project_id=project.structured_content['result']['id']
                result=await client.call_tool('layerweave_project_overview',{'database':mode+'.db','project_id':project_id})
                assert not result.is_error,result.structured_content
                assert result.structured_content['result']['project']['name']=='wheel MCP'
                compact=await client.call_tool('layerweave_query',{'command':'export_project','arguments':{
                    'database':mode+'.db','project_id':project_id,'compact':True}})
                assert not compact.is_error,compact.structured_content
                document=compact.structured_content['result']
                assert document['scope']['compact'] and 'tables' not in document and 'source_numbering' not in document
                for i in range(4):
                    added=await client.call_tool('layerweave_edit',{'command':'dispatch','arguments':{
                        'database':mode+'.db','request':{'action':'create','kind':'project','data':{'name':str(i)}}}})
                    assert not added.is_error,added.structured_content
                first=await client.call_tool('layerweave_query',{'command':'read_history','arguments':{
                    'database':mode+'.db','limit':3},'limit':2})
                assert not first.is_error,first.structured_content
                page=first.structured_content
                assert page['more']['path']==['items'] and len(page['result']['items'])==2
                assert page['more']['business_cursor_pending'] and page['result']['next_cursor'] is None
                last=await client.call_tool('layerweave_query',{'cursor':page['more']['cursor']})
                assert not last.is_error,last.structured_content
                page=last.structured_content
                assert len(page['result']['items'])==1 and not page['more']['has_more']
                assert page['result']['next_cursor'] is not None and not page['more']['business_cursor_pending']
                print('ordinary wheel stdio '+mode+': tools, JSON, compact, help, author, annotations and both pagination cursors passed')
        asyncio.run(exercise('auto'))
        asyncio.run(exercise('legacy'))


if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('Usage: python tests/check_mcp_wheel.py PATH_TO_WHEEL')
    check(Path(sys.argv[1]).resolve())

"""MCP 临时项目夹具；不借用任何测试类的生命周期。"""
import importlib.util
from pathlib import Path
import tempfile
from layerweave.support.api import initialize_database, open_database
from layerweave.tool.builtin.usage.records.dispatch import dispatch

HAS_MCP = importlib.util.find_spec('mcp') is not None and importlib.util.find_spec('jsonschema') is not None


class MCPFixture:
    def setUp(self):
        from layerweave.tool.builtin.shared.mcp import create_runtime
        self.temp=tempfile.TemporaryDirectory(prefix='layerweave-mcp-test-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db=initialize_database(self.root/'project.sqlite3')
        c=open_database(self.db)
        self.addCleanup(c.close)
        self.c=c
        self.project=dispatch(c,{'action':'create','kind':'project','data':{'name':'原项目'}},checker=None)['id']
        self.layer=dispatch(c,{'action':'create','kind':'layer','project_id':self.project,'data':{'config_ref':'layers/text.toml'}},checker=None)['id']
        self.obj=dispatch(c,{'action':'create','kind':'object','project_id':self.project,'data':{
            'config_ref':'objects/text.toml','layer':self.layer,'begin':10,'end':20,'information':{'text':'原文'}}},checker=None)['id']
        self.options={'workspace':str(self.root),'database':str(self.db),'project_id':self.project,'installed':False,'skills_roots':[]}
        self.runtime=create_runtime(self.options)
    def runtime_with(self,**changes):
        from layerweave.tool.builtin.shared.mcp import create_runtime
        return create_runtime({**self.options,**changes})
    def call(self,route,name,**arguments):
        result=self.runtime.invoke(route,name,arguments)
        self.assertFalse(result.is_error,result.data)
        return result.data

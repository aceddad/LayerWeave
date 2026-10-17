"""外部声明的真正普通安装与 PEP 660 可编辑安装；发现时不运行业务模块。"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT=Path(__file__).resolve().parents[1]
READY=all(importlib.util.find_spec(name) is not None for name in ('pip','wheel','jsonschema','mcp'))


@unittest.skipUnless(READY,'安装 MCP 开发依赖运行包安装验收')
class ExternalPackageInstallTests(unittest.TestCase):
    def test_wheel_and_actual_editable_install(self):
        with tempfile.TemporaryDirectory(prefix='layerweave-plugin-install-') as folder:
            root=Path(folder)
            project=root/'extension'; code=project/'implementation'; code.mkdir(parents=True)
            (project/'pyproject.toml').write_text('''[build-system]
requires = ["setuptools>=64", "wheel"]
build-backend = "setuptools.build_meta"
[project]
name = "layerweave-mcp-test-extension"
version = "0.1.0"
[project.entry-points."layerweave.tools"]
probe = "layerweave_probe:COMMANDS"
[tool.setuptools]
packages = ["layerweave_probe"]
[tool.setuptools.package-dir]
layerweave_probe = "implementation"
''',encoding='utf-8')
            declaration={'name':'echo','summary':'无 CLI 的扩展','entrypoint':'layerweave_probe:echo','read_only':True,
                'input_schema':{'type':'object','properties':{'text':{'type':'string'}},'required':['text'],'additionalProperties':False},
                'mcp':{'route':'query','exposure':'direct'}}
            (code/'__init__.py').write_text("import os\nfrom pathlib import Path\nPath(os.environ['MCP_PROBE_MARKER']).touch()\ndef echo(text):\n    return {'text':text}\nCOMMANDS = "+repr([declaration]),encoding='utf-8')
            for editable in (False,True):
                with self.subTest(editable=editable):
                    target=root/('editable' if editable else 'installed')
                    command=[sys.executable,'-m','pip','install','--disable-pip-version-check','--no-deps','--no-build-isolation','--target',str(target)]
                    if editable:
                        command.append('--editable')
                    command.append(str(project))
                    install=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=90)
                    self.assertEqual(install.returncode,0,install.stdout+install.stderr)
                    marker=root/('editable.loaded' if editable else 'installed.loaded')
                    script=f'''
import json, site, sys
from pathlib import Path
site.addsitedir({str(target)!r})
from layerweave.tool.builtin.shared.mcp import create_runtime
marker=Path({str(marker)!r})
runtime=create_runtime({{'include_builtin':False,'skills_roots':[]}})
assert not marker.exists(), 'discovery imported the extension'
if 'probe.echo' not in runtime.catalog.bindings:
    assert {editable!r}, runtime.catalog.issues
    assert any(i['code']=='command_source' for i in runtime.catalog.issues), runtime.catalog.issues
    runtime=create_runtime({{'include_builtin':False,'installed':False,'skills_roots':[],
        'sources':[{{'namespace':'probe','path':{str(code/'__init__.py')!r}}}]}})
    assert not marker.exists()
result=runtime.invoke('query','probe.echo',{{'text':'installed'}})
assert not result.is_error, result.data
assert result.data['result']=={{'text':'installed'}}, result.data
assert marker.exists()
assert 'probe_echo' in runtime.catalog.direct
print('editable=' + str({editable!r}) + ': discovery and invocation passed')
'''
                    run=subprocess.run([sys.executable,'-X','utf8','-B','-c',script],cwd=root,
                        env={**os.environ,'MCP_PROBE_MARKER':str(marker),'PYTHONPATH':''},
                        capture_output=True,text=True,encoding='utf-8',timeout=45)
                    self.assertEqual(run.returncode,0,run.stdout+run.stderr)


if __name__=='__main__':
    unittest.main()

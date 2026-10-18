"""从公开命令示例启动进程，按 AI 的 UTF-8 管道读取中文 stdout/stderr。"""
from contextlib import closing
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from layerweave.support.api import initialize_database, open_database, transaction
from layerweave.support.commands import command_help, discover_commands
from tests._support.paths import ROOT


class CLIEncodingTests(unittest.TestCase):
    def environment(self, utf8='0'):
        env=dict(os.environ)
        env.pop('PYTHONIOENCODING',None)
        env.update(PYTHONUTF8=utf8, PYTHONDONTWRITEBYTECODE='1')
        return env

    def command(self, name):
        value=command_help(name)['items'][0]
        args=shlex.split(value['cli'])
        args[0]=sys.executable
        return args

    def run_pipe(self, args, *, env=None):
        # 不用 text=True 的本机默认解码；像外部调用工具一样明确按 UTF-8 读取。
        result=subprocess.run(args,env=env or self.environment(),capture_output=True,timeout=40)
        return result.returncode,result.stdout.decode('utf-8'),result.stderr.decode('utf-8')

    def test_builtin_cli_declarations_and_examples_enable_utf8(self):
        commands,issues=discover_commands(installed=False)
        self.assertFalse(issues)
        for command in commands:
            for value in [command.get('cli'), *(e.get('cli') for e in command.get('examples',[]))]:
                if not value: continue
                with self.subTest(command=command['id'],example=value):
                    tokens=shlex.split(value)
                    if Path(tokens[0]).name not in ('python','python3','python.exe'):
                        continue  # 非 Python 的扩展入口不受解释器启动选项约束。
                    self.assertEqual(tokens[1:3],['-X','utf8'])

    def test_maintained_cli_docs_and_mcp_launcher_examples_enable_utf8(self):
        docs=[*ROOT.glob('README*.md'), *(ROOT/'docs').rglob('*.md'), *(ROOT/'examples').rglob('*.md'),
              *(ROOT/'tests').rglob('*.md'), *(ROOT/'src/layerweave/tool/builtin').rglob('*.md'),
              ROOT/'src/layerweave/tool/README.md']
        bare=re.compile(r'\bpython(?:3|\.exe)?\s+(?:-m\b|-c\b|-B\b|[\w./\\-]+\.py\b)')
        for path in docs:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIsNone(bare.search(path.read_text(encoding='utf-8')))
        guide=(ROOT/'src/layerweave/tool/builtin/shared/mcp/README.md').read_text(encoding='utf-8')
        examples=[json.loads(body) for body in re.findall(r'```json\s*\n(.*?)\n```',guide,re.S)]
        config=next(e for e in examples if 'mcpServers' in e)
        self.assertEqual(config['mcpServers']['layerweave']['args'][:3],['-X','utf8','-m'])

    def test_overview_help_and_list_roundtrip_through_utf8_pipes(self):
        with tempfile.TemporaryDirectory(prefix='layerweave-cli-encoding-') as folder:
            database=initialize_database(Path(folder)/'project.sqlite3')
            with closing(open_database(database)) as c, transaction(c) as write:
                project=write.create('project',{'name':'中文项目 🎬'})['id']
                write.create('layer',{'type':'text','name':'文字层','config_ref':'layers/text.toml'},project_id=project)
            code,text,error=self.run_pipe([*self.command('project_overview'),str(database),str(project)])
            self.assertEqual(code,0,error)
            self.assertIn('中文项目 🎬',text)
            self.assertIn('文字层',text)
        code,text,error=self.run_pipe([*self.command('command_help'),'--json'])
        self.assertEqual(code,0,error)
        self.assertTrue(any('概览' in item['summary'] for item in json.loads(text)['items']))
        code,text,error=self.run_pipe([*self.command('mcp_server'),'--list'])
        self.assertEqual(code,0,error)
        self.assertTrue(any('概览' in item['summary'] for item in json.loads(text)['items']))
        code,text,error=self.run_pipe([*self.command('command_help'),'--help'])
        self.assertEqual(code,0,error)
        self.assertIn('示例',text)

    def test_error_output_uses_utf8_from_the_documented_launch(self):
        with tempfile.TemporaryDirectory(prefix='layerweave-cli-error-') as folder:
            code,text,error=self.run_pipe([*self.command('project_overview'),str(Path(folder)/'missing.db'),'1'])
            self.assertNotEqual(code,0)
            self.assertIn('数据库不存在',error)

    def test_pythonutf8_environment_alternative(self):
        command=[sys.executable,'-m','layerweave.tool.builtin.shared.mcp','--list']
        code,text,error=self.run_pipe(command,env=self.environment('1'))
        self.assertEqual(code,0,error)
        self.assertTrue(any('概览' in item['summary'] for item in json.loads(text)['items']))


if __name__=='__main__':
    unittest.main()

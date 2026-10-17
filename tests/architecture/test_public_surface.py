"""公共出口和测试依赖约定，防止发布整理后再次混入隐式接口。"""
import ast
from pathlib import Path
import unittest

from tests._support.paths import ROOT


class PublicSurfaceTests(unittest.TestCase):
    def test_support_star_import_exposes_only_documented_facade(self):
        from layerweave.support import api
        namespace={}
        exec('from layerweave.support.api import *',namespace)
        self.assertEqual(set(namespace)-{'__builtins__'},set(api.__all__))
        for name in ('transaction','run_operation','read_snapshot','register_tables','allocate','read_changes'):
            self.assertTrue(callable(namespace[name]))
        self.assertFalse(any(name.startswith('_') for name in api.__all__))

    def test_tools_do_not_register_secret_access_as_model_command(self):
        from layerweave.support.commands import discover_commands
        commands,issues=discover_commands(installed=False)
        self.assertFalse(issues)
        self.assertTrue(commands)
        self.assertFalse(any(c.get('entrypoint','').endswith(':get_key') for c in commands))

    def test_test_modules_do_not_import_other_test_cases(self):
        for path in (ROOT/'tests').rglob('*.py'):
            tree=ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                modules=([node.module or ''] if isinstance(node,ast.ImportFrom) else
                         [a.name for a in node.names] if isinstance(node,ast.Import) else [])
                for module in modules:
                    self.assertFalse(any(p.startswith('test_') for p in module.split('.')), (path,module))

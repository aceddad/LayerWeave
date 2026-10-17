"""宿主的常见模块名不能遮蔽 LayerWeave；独立进程避免导入缓存掩盖问题。"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tests._support.namespace import COMMON_NAMES, SMOKE, make_host_modules


from tests._support.paths import ROOT

# check_wheel.py 在不加载测试环境中 layerweave 的独立进程中复用这些行为断言。


class NamespaceTests(unittest.TestCase):
    def test_host_files_and_packages_do_not_break_layerweave(self):
        for packages in (False, True):
            with self.subTest(packages=packages), tempfile.TemporaryDirectory(prefix="layerweave-shadow-") as folder:
                make_host_modules(Path(folder), packages=packages)
                env = dict(os.environ)
                env.pop("PYTHONPATH", None)
                result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", SMOKE], cwd=folder,
                                        env=env, capture_output=True, text=True, encoding="utf-8", timeout=45)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_distribution_declares_only_layerweave(self):
        from importlib.metadata import distribution
        names = distribution("layerweave").read_text("top_level.txt").splitlines()
        self.assertEqual(names, ["layerweave"])

    def test_source_install_does_not_expose_old_empty_namespace_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            code = '''
from importlib.util import find_spec
from pathlib import Path
from layerweave.support.paths import PACKAGE_ROOT
for name in ("core", "models", "support", "tool", "examples"):
    spec = find_spec(name)
    if spec is not None:
        paths = [*(spec.submodule_search_locations or []), *([spec.origin] if spec.origin else [])]
        assert not any(Path(p).resolve().is_relative_to(PACKAGE_ROOT.parent) for p in paths), (name,paths)
'''
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", code], cwd=folder,
                                    env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

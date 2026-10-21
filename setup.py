from setuptools import setup
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_support import BuildPy, prepare_package_readme

prepare_package_readme()
setup(cmdclass={"build_py": BuildPy})

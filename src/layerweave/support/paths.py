"""随包资源位置；源码开发和普通 wheel 安装使用同一份目录结构。"""
from importlib.resources import files
from pathlib import Path

PACKAGE_ROOT = Path(files("layerweave"))
CONFIG_ROOT = PACKAGE_ROOT / "configs"
BUILTIN_ROOT = PACKAGE_ROOT / "tool" / "builtin"
SKILLS_ROOT = PACKAGE_ROOT / "tool" / "skills"

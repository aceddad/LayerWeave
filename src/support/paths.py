"""源码安装中的稳定资源位置，与调用方当前目录无关。"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "configs"
BUILTIN_ROOT = PROJECT_ROOT / "tool" / "builtin"
SKILLS_ROOT = PROJECT_ROOT / "tool" / "skills"

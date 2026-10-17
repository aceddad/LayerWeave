"""命令来源：内置、开发目录与已安装包；定位声明不导入业务模块。"""
from importlib import metadata
from pathlib import Path
import sys

from .paths import BUILTIN_ROOT


def _module_file(entry):
    module = entry.value.split(":", 1)[0]
    parts = module.split(".")
    if not all(part.isidentifier() for part in parts):
        raise ValueError("entry point 需要模块名或模块名:COMMANDS")
    suffixes = (Path(*parts).with_suffix(".py"), Path(*parts) / "__init__.py")
    dist = getattr(entry, "dist", None)
    for record in (() if dist is None else dist.files or ()):
        for suffix in suffixes:
            if Path(str(record)).as_posix() == suffix.as_posix():
                path = Path(dist.locate_file(record)).resolve()
                if path.is_file():
                    return path, path.parents[len(suffix.parts) - 1]
    for root in sys.path:
        if not root:
            continue
        for suffix in suffixes:
            path = Path(root) / suffix
            if path.is_file():
                return path.resolve(), Path(root).resolve()
    raise ValueError("无法静态定位声明模块；可编辑安装请用 sources 指定开发目录，不会导入模块兜底")


def command_sources(*, sources=(), include_builtin=True, installed=True):
    """返回来源及逐项问题；sources 的相对路径由调用方先按配置目录解析。"""
    result, issues = [], []
    if include_builtin and BUILTIN_ROOT.is_dir():
        result.append({"namespace": "layerweave", "path": BUILTIN_ROOT.resolve(), "import_root": None})
    if installed:
        for entry in sorted(metadata.entry_points(group="layerweave.tools"), key=lambda e: (e.name, e.value)):
            try:
                path, root = _module_file(entry)
                result.append({"namespace": entry.name, "path": path, "import_root": root})
            except (OSError, ValueError, TypeError) as error:
                issues.append({"code": "command_source", "source": entry.value, "message": str(error)})
    for source in sources:
        try:
            if not isinstance(source, dict) or not isinstance(source.get("namespace"), str):
                raise ValueError("sources 每项需要 namespace 与 path")
            path = Path(source["path"]).resolve()
            if not path.exists():
                raise ValueError(f"命令来源不存在：{path}")
            root = source.get("import_root")
            result.append({"namespace": source["namespace"], "path": path,
                           "import_root": Path(root).resolve() if root else None})
        except (OSError, ValueError, KeyError, TypeError) as error:
            issues.append({"code": "command_source", "source": str(source), "message": str(error)})
    unique = {}
    for source in result:
        unique.setdefault((source["namespace"], str(source["path"])), source)
    return list(unique.values()), issues

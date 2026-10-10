"""发现完整工具包公开的可选能力；不导入未使用的工具。"""
import ast
from importlib import import_module

from .paths import BUILTIN_ROOT
from .channel import _NOT_CONFIGURED

DEFAULT_CHECKER = object()


def provider(role, *, root=BUILTIN_ROOT):
    """包的 __init__.py 可声明字面量 PROVIDERS；同一角色只能有一个提供者。"""
    found = []
    for path in sorted(root.rglob("__init__.py")):
        source = path.read_text(encoding="utf-8-sig")
        if "PROVIDERS" not in source:
            continue
        for node in ast.parse(source, filename=str(path)).body:
            if isinstance(node, ast.Assign) and any(isinstance(n, ast.Name) and n.id == "PROVIDERS" for n in node.targets):
                route = ast.literal_eval(node.value).get(role)
                if route is not None:
                    found.append(route)
    if len(found) > 1:
        raise ValueError(f"能力 {role} 存在多个提供者：{found}")
    return found[0] if found else None


def optional_checker(checker=DEFAULT_CHECKER, *, config_root=None):
    """工具显式请求默认检测；发现/导入留到提交后，缺席则明确未检查。"""
    if checker is not DEFAULT_CHECKER:
        return checker
    def check(changes, read_record):
        route = provider("checker")
        if route is None:
            return _NOT_CONFIGURED
        module, name = route.split(":", 1)
        execute = getattr(import_module(module), name)
        return execute(changes, read_record, **({"config_root": config_root} if config_root is not None else {}))
    return check

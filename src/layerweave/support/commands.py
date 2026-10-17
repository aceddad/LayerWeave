"""只读命令目录：静态发现模块的 COMMANDS 说明，不导入或执行被发现的工具。"""

import ast
from copy import deepcopy
from difflib import get_close_matches
from functools import lru_cache
import json
from pathlib import Path

from layerweave.support.feedback import InputError
from layerweave.support.command_schema import command_schema, parameters_from_schema


from layerweave.support.paths import BUILTIN_ROOT
DEFAULT_SOURCE_ROOT = BUILTIN_ROOT
CONTEXT = {
    "database": {"type": "string", "required": True, "description": "CLI 的数据库路径；Python 入口由调用方提供 connection"},
    "project_id": {"type": "integer", "required": True, "description": "明确的项目编号"},
}


def help_examples(commands):
    """CLI 与查询接口共用模块内的同一份示例，JSON 文件内容可直接解析。"""
    lines = ["示例（可编辑安装后运行；示例路径和编号替换为实际值）："]
    for command in commands:
        for example in command.get("examples", []):
            if example.get("cli"):
                lines.append("  " + example["cli"])
            for name, value in example.get("files", {}).items():
                lines.append("  " + name + " 内容：\n  " + json.dumps(value, ensure_ascii=False, allow_nan=False))
        lines.extend("  " + note for note in command.get("notes", []))
    return "\n".join(lines)


def _description(command, source):
    """仅保证说明可读取和展示；不据此执行或检查业务参数。"""
    if not isinstance(command, dict) or not all(isinstance(command.get(key), str) for key in ("name", "summary")):
        raise ValueError("命令说明需要字符串 name/summary")
    for key in ("entrypoint", "cli"):
        if key in command and not isinstance(command[key], str):
            raise ValueError(f"{key} 应为字符串；没有该接口时可以省略")
    if type(command.get("read_only")) is not bool:
        raise ValueError("read_only 应为布尔值")
    if "session_entrypoint" in command and not isinstance(command["session_entrypoint"], str):
        raise ValueError("session_entrypoint 应为字符串")
    for key in ("context", "aliases", "notes"):
        values = command.get(key, [])
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise ValueError(f"{key} 应为字符串列表")
    declared = command.get("parameters", {})
    if not isinstance(declared, dict) or not all(isinstance(name, str) and isinstance(spec, dict) for name, spec in declared.items()):
        raise ValueError("parameters 应为参数名到说明对象的映射")
    schema = command_schema(command)
    parameters = parameters_from_schema(schema)
    if not isinstance(command.get("returns", ""), str):
        raise ValueError("returns 应为字符串")
    examples = command.get("examples", [])
    if not isinstance(examples, list) or not all(isinstance(item, dict)
                                               and ("cli" not in item or isinstance(item["cli"], str))
                                               and isinstance(item.get("files", {}), dict) for item in examples):
        raise ValueError("examples 应为入口示例对象列表，cli/files 可选")
    json.dumps(command, allow_nan=False)
    return {**command, "input_schema": schema, "parameters": parameters, "source": source}


@lru_cache(maxsize=256)
def _declarations(path, modified, size):
    source = Path(path).read_text(encoding="utf-8-sig")
    if "COMMANDS" not in source:
        return []
    tree = ast.parse(source, filename=path)
    return [ast.literal_eval(node.value) for node in tree.body
            if isinstance(node, ast.Assign) and any(isinstance(name, ast.Name) and name.id == "COMMANDS" for name in node.targets)]


def _discover(root):
    commands, issues = [], []
    for path in ([root] if root.is_file() else sorted(root.rglob("*.py"))):
        label = path.name if root.is_file() else path.relative_to(root).as_posix()
        try:
            stat = path.stat()
            for values in _declarations(str(path), stat.st_mtime_ns, stat.st_size):
                if not isinstance(values, list):
                    raise ValueError("COMMANDS 应为字面量列表")
                for command in values:
                    try:
                        commands.append(_description(deepcopy(command), label))
                    except (ValueError, TypeError, KeyError) as error:
                        issues.append({"code": "command_metadata", "source": label, "message": str(error)})
        except (OSError, UnicodeError, ValueError, SyntaxError, TypeError, KeyError) as error:
            issues.append({"code": "command_metadata", "source": label, "message": str(error)})
    return commands, issues


def discover_commands(*, sources=(), include_builtin=True, installed=True):
    """合并多个来源，保留身份与导入根；不导入所发现的工具。"""
    from .command_sources import command_sources
    roots, issues = command_sources(sources=sources, include_builtin=include_builtin, installed=installed)
    commands = []
    for root in roots:
        found, problems = _discover(root["path"])
        issues.extend({**item, "namespace": root["namespace"]} for item in problems)
        for command in found:
            name, namespace = command["name"], root["namespace"]
            identity = name if name.startswith(namespace + ".") else namespace + "." + name
            commands.append({**command, "id": identity, "namespace": namespace,
                             "source_root": str(root["path"]),
                             "import_root": str(root["import_root"]) if root["import_root"] else None})
    return commands, issues


def command_help(names=None, *, source_root=DEFAULT_SOURCE_ROOT):
    """不指定名称列总览；名称或别名列表展开详情。无数据库、无命令执行。"""
    root = Path(source_root).resolve()
    if root == DEFAULT_SOURCE_ROOT.resolve() and not root.exists():
        commands, issues = [], []
    elif not root.is_dir():
        raise InputError(f"命令源目录不存在：{root}", field="source_root")
    else:
        commands, issues = _discover(root)
    index = {}
    for command in commands:
        for name in dict.fromkeys([command["name"], *([command["entrypoint"]] if command.get("entrypoint") else []), *command.get("aliases", [])]):
            index.setdefault(name, []).append(command)
    items, seen = [], set()
    requested = sorted({c["name"] for c in commands}) if names is None else [names] if isinstance(names, str) else list(names)
    for name in requested:
        matches = index.get(name, []) if isinstance(name, str) else []
        if len(matches) != 1:
            issues.append({"code": "command_name", "name": name,
                           "message": "命令名称有歧义" if matches else "未找到命令",
                           "candidates": [c["source"] for c in matches] if matches else get_close_matches(str(name), list(index), n=5)})
            continue
        command = matches[0]
        identity = (command["source"], command["name"], command.get("entrypoint"))
        if identity in seen:
            continue
        seen.add(identity)
        items.append({key: command[key] for key in ("name", "summary", "read_only", "cli") if key in command} if names is None else deepcopy(command))
    return {"view": "overview" if names is None else "details", "status": "partial" if issues else "completed", "items": items, "issues": issues}

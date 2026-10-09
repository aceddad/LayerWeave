"""只读命令目录：静态发现模块的 COMMANDS 说明，不导入或执行被发现的工具。"""

import ast
from copy import deepcopy
from difflib import get_close_matches
import json
from pathlib import Path

from support.feedback import InputError


from support.paths import BUILTIN_ROOT
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
            lines.append("  " + example["cli"])
            for name, value in example.get("files", {}).items():
                lines.append("  " + name + " 内容：\n  " + json.dumps(value, ensure_ascii=False, allow_nan=False))
        lines.extend("  " + note for note in command.get("notes", []))
    return "\n".join(lines)


def _description(command, source):
    """仅保证说明可读取和展示；不据此执行或检查业务参数。"""
    if not isinstance(command, dict) or not all(isinstance(command.get(key), str) for key in ("name", "summary", "entrypoint", "cli")):
        raise ValueError("命令说明需要字符串 name/summary/entrypoint/cli")
    if type(command.get("read_only")) is not bool:
        raise ValueError("read_only 应为布尔值")
    for key in ("context", "aliases", "notes"):
        values = command.get(key, [])
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise ValueError(f"{key} 应为字符串列表")
    parameters = {name: deepcopy(CONTEXT[name]) for name in command.get("context", [])}
    declared = command.get("parameters", {})
    if not isinstance(declared, dict) or not all(isinstance(name, str) and isinstance(spec, dict) for name, spec in declared.items()):
        raise ValueError("parameters 应为参数名到说明对象的映射")
    parameters.update(declared)
    if not isinstance(command.get("returns", ""), str):
        raise ValueError("returns 应为字符串")
    examples = command.get("examples", [])
    if not isinstance(examples, list) or not all(isinstance(item, dict) and isinstance(item.get("cli"), str)
                                               and isinstance(item.get("files", {}), dict) for item in examples):
        raise ValueError("examples 应为含 cli 与可选 files 的说明列表")
    json.dumps(command, allow_nan=False)
    return {**command, "parameters": parameters, "source": source}


def _discover(root):
    commands, issues = [], []
    for path in sorted(root.rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8-sig")
            if "COMMANDS" not in source:
                continue
            tree = ast.parse(source, filename=str(path))
            for node in tree.body:
                if not isinstance(node, ast.Assign) or not any(isinstance(name, ast.Name) and name.id == "COMMANDS" for name in node.targets):
                    continue
                values = ast.literal_eval(node.value)
                if not isinstance(values, list):
                    raise ValueError("COMMANDS 应为字面量列表")
                for command in values:
                    try:
                        commands.append(_description(command, path.relative_to(root).as_posix()))
                    except (ValueError, TypeError, KeyError) as error:
                        issues.append({"code": "command_metadata", "source": path.relative_to(root).as_posix(), "message": str(error)})
        except (OSError, UnicodeError, ValueError, SyntaxError, TypeError, KeyError) as error:
            issues.append({"code": "command_metadata", "source": path.relative_to(root).as_posix(), "message": str(error)})
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
        for name in dict.fromkeys([command["name"], command["entrypoint"], *command.get("aliases", [])]):
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
        identity = (command["source"], command["name"], command["entrypoint"])
        if identity in seen:
            continue
        seen.add(identity)
        items.append({key: command[key] for key in ("name", "summary", "read_only", "cli")} if names is None else deepcopy(command))
    return {"view": "overview" if names is None else "details", "status": "partial" if issues else "completed", "items": items, "issues": issues}

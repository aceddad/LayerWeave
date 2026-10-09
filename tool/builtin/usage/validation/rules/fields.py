"""共用字段检查只描述问题；缺字段、类型和疑似拼写分别设置汇报等级。"""

from difflib import get_close_matches


TYPES = {"str": str, "int": int, "float": (int, float), "dict": dict,
         "list": list, "bool": bool, "None": type(None)}


def problem(message, *, field=None, skipped=False, **extra):
    result = {"message": message, **extra}
    if field is not None:
        result["field"] = field
    if skipped:
        result["skipped"] = True
    return result


def matches(value, declaration):
    names = [name.strip() for name in declaration.split("|")]
    if any(name not in TYPES for name in names):
        raise ValueError(f"尚未实现的类型声明：{declaration}")
    return any(isinstance(value, TYPES[name]) and not (name in {"int", "float"} and isinstance(value, bool))
               for name in names)


def interval(record):
    begin, end = record["begin"], record["end"]
    return matches(begin, "float") and matches(end, "float") and begin <= end


def check(record, config, read_record):
    issues = []
    changed = config.get("_changed_fields")

    def field(value, spec, name):
        try:
            if not matches(value, spec["type"]):
                issues.append(problem(f"应为 {spec['type']}，实际为 {type(value).__name__}", field=name, code="field_type"))
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            issues.append(problem(f"无法检查字段类型：{error}", field=name, code="field_check_unavailable", skipped=True))

    for name, spec in config.get("fields", {}).items():
        if changed is None or name in changed:
            if name in record:
                field(record[name], spec, name)
            elif name not in {"objects", "bind"} and not spec.get("optional", False):
                # objects/bind 是反查装载的组合字段，不是数据库记录缺失。
                issues.append(problem("未提供配置声明的字段，请检查是否漏填或字段名写错", field=name, code="missing_field"))
    information = record.get("information")
    if isinstance(information, dict) and (changed is None or "information" in changed):
        declarations = config.get("information", {})
        missing = sorted(declarations.keys() - information.keys())
        hints = {}
        if config.get("open", True):
            for key in sorted(information.keys() - declarations.keys()):
                candidate = {"src": "source", "txt": "text"}.get(key)
                close = [candidate] if candidate in missing else get_close_matches(key, missing, n=1, cutoff=0.8)
                if close:
                    hints.setdefault(close[0], key)
        for name, spec in config.get("information", {}).items():
            if name in information:
                field(information[name], spec, f"information.{name}")
            elif name in hints:
                key = hints[name]
                issues.append(problem(f"未提供 {name}；未声明字段 {key} 可能是它的笔误", code="field_typo",
                                      field=f"information.{key}", suggestions={key: name}))
            elif not spec.get("optional", False):
                issues.append(problem("未提供配置声明的字段，请检查是否漏填或字段名写错",
                                      field=f"information.{name}", code="missing_field"))
        if config.get("open", True) is False:
            for name in information.keys() - config.get("information", {}).keys():
                issues.append(problem("此配置不接受未声明的内容字段", field=f"information.{name}", code="unknown_field"))
    return issues

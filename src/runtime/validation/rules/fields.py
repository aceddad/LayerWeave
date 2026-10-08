"""共用类型判断；只检查声明过且提供了的内容，不补默认值。"""


TYPES = {"str": str, "int": int, "float": (int, float), "dict": dict,
         "list": list, "bool": bool, "None": type(None)}


def problem(message, *, field=None, severity="error", skipped=False, **extra):
    result = {"severity": severity, "message": message, **extra}
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
                issues.append(problem(f"应为 {spec['type']}，实际为 {type(value).__name__}", field=name))
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            issues.append(problem(f"无法检查字段类型：{error}", field=name, skipped=True))

    for name, spec in config.get("fields", {}).items():
        if name in record and (changed is None or name in changed):
            field(record[name], spec, name)
    information = record.get("information")
    if isinstance(information, dict) and (changed is None or "information" in changed):
        for name, spec in config.get("information", {}).items():
            if name in information:
                field(information[name], spec, f"information.{name}")
        if config.get("open", True) is False:
            for name in information.keys() - config.get("information", {}).keys():
                issues.append(problem("此配置不接受未声明的内容字段", field=f"information.{name}"))
    return issues

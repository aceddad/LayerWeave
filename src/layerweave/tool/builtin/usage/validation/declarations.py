"""配置声明的疑似拼写提示；不改名、不禁止自定义段，也不执行视图功能。"""

from difflib import get_close_matches


SECTIONS = {"fields", "information", "methods", "rules", "constraint", "display",
            "defaults", "options", "example"}


def spelling_hints(loader, config, kind):
    issues = []

    def inspect(values, known, prefix, ref):
        for name in values:
            if name in known:
                continue
            matches = get_close_matches(name, sorted(known), n=1, cutoff=0.8)
            if matches:
                field = f"{prefix}.{name}"
                suggestion = f"{prefix}.{matches[0]}"
                issues.append({"code": "config_typo", "field": field, "source_ref": ref,
                               "suggestions": {field: suggestion},
                               "message": f"{ref} 的 {field} 疑似拼写错误，是不是 {suggestion}？声明保留原样，请确认。"})

    # 读实际声明，避免继承后的默认值掩盖笔误，并准确指出应修改的文件。
    for ref in config["_lineage"]:
        raw = loader.declared(ref, kind)
        inspect({name: value for name, value in raw.items() if isinstance(value, dict)}, SECTIONS, kind, ref)
        inspect(raw.get("display", {}), {"visibility"}, f"{kind}.display", ref)
        defaults = raw.get("defaults", {})
        inspect(defaults, {"rules", "constraint", "display"}, f"{kind}.defaults", ref)
        inspect(defaults.get("display", {}), {"visibility"}, f"{kind}.defaults.display", ref)
    return issues

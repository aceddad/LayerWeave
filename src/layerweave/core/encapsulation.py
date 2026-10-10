"""封装约定的纯数据合并语义；没有文件读取和检测器依赖。"""
from copy import deepcopy
from .values import same_value

class DefinitionError(ValueError):
    pass


def _fixed(parent, child, location):
    """固定约定只能增加或重复，不能覆盖已有值。"""
    result = deepcopy(parent)
    for key, value in child.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _fixed(result[key], value, f"{location}.{key}")
        elif key in result and not same_value(result[key], value):
            raise DefinitionError(f"{location}.{key} 改写父约定：{result[key]!r} → {value!r}")
        else:
            result[key] = deepcopy(value)
    return result


def merge_definition(parent, raw):
    result = deepcopy(parent) if parent else {}
    # 类型等声明固定；optional 可收紧，default/note 是可更新的说明。
    for section in ("fields", "information"):
        declarations = result.setdefault(section, {})
        for field, spec in raw.get(section, {}).items():
            if "optional" in spec and type(spec["optional"]) is not bool:
                raise DefinitionError(f"{section}.{field}.optional 应为 true 或 false")
            old = declarations.get(field, {})
            if field in declarations and spec.get("optional") is True and not old.get("optional", False):
                raise DefinitionError(f"{section}.{field}.optional 放宽父约定：false → true")
            fixed_old = {k: v for k, v in old.items() if k not in {"note", "default", "optional"}}
            fixed_new = {k: v for k, v in spec.items() if k not in {"note", "default", "optional"}}
            declarations[field] = {**old, **spec, **_fixed(fixed_old, fixed_new, f"{section}.{field}")}
    contracts = deepcopy(parent.get("_contracts", {})) if parent else {}
    defaults = deepcopy(result.get("defaults", {}))
    for section, values in raw.get("defaults", {}).items():
        defaults.setdefault(section, {}).update(values)
    result["defaults"] = defaults
    for section in ("rules", "constraint", "display"):
        contracts[section] = _fixed(contracts.get(section, {}), raw.get(section, {}), section)
        result[section] = {**defaults.get(section, {}), **contracts[section]}
    if "open" in raw:
        if type(raw["open"]) is not bool:
            raise DefinitionError("object.open 应为 true 或 false")
        if parent and parent.get("open", True) is False and raw["open"] is True:
            raise DefinitionError("object.open 放宽父约定：false → true")
    result["_contracts"] = contracts
    # options 是明确允许派生调整的选项，当前只有 axis_only_on_root。
    result["options"] = {**result.get("options", {}), **raw.get("options", {})}
    for key, value in raw.items():
        if key not in {"fields", "information", "defaults", "rules", "constraint", "display", "options"}:
            result[key] = deepcopy(value)
    return result

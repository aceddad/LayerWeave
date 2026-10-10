"""help 的展示数据：字段来源、简明用法与保存示例，不执行示例。"""

from copy import deepcopy
import json
from pprint import pformat

from layerweave.support.configuration.loader import DEFAULT_ROOT
from layerweave.support.records import writable_fields


def field_origins(loader, config, kind):
    """只给有效字段属性标注最后声明处；默认 optional 不写回配置。"""
    origins = {section: {} for section in ("fields", "information")}
    for ref in config["_lineage"]:
        raw = loader.declared(ref, kind)
        for section, fields in origins.items():
            for name, spec in raw.get(section, {}).items():
                fields.setdefault(name, {}).update({key: ref for key in spec})
    for fields in origins.values():
        for spec in fields.values():
            spec.setdefault("optional", "default: false")
    return origins


def usage(config):
    """使用者需要有效内容约定，包括继承来的字段，而非只看子类差异。"""
    return {key: deepcopy(config[key]) for key in
            ("information", "open", "rules", "constraint", "options", "display")
            if config.get(key) not in (None, {})}


def reporting_exceptions(config, policy):
    """使用 help 只列与全局设置不同的等级；全局缺省仍由 Policy 决定。"""
    ref, differences = config["_ref"], []
    for section in ("fields", "information"):
        for name in config.get(section, {}):
            field = name if section == "fields" else f"information.{name}"
            for code in ("missing_field", "field_type"):
                level = policy.level(code, config_ref=ref, field=field)
                if level != policy.level(code, field=field):
                    differences.append({"code": code, "field": field, "level": level})
    codes = {"field_typo", *(name for section in ("rules", "constraint", "options")
                            for name in config.get(section, {}))}
    for code in sorted(codes):
        local = policy.describe(code, config_ref=ref)
        global_ = {"default": policy.level(code), "fields": {}}
        if local != global_:
            differences.append({"code": code, **local})
    return differences


def save_example(config, kind, config_root):
    """把构造参数适配为新增保存调用；已有实体引用使用明确的上下文变量。"""
    example = config.get("example")
    if not isinstance(example, dict):
        return {"status": "unavailable", "reason": "封装未提供 example 参数字典"}
    payload = deepcopy(example)
    for key in ("id", "project_id", "type"):
        payload.pop(key, None)
    allowed = {*writable_fields(kind), "bind"}
    if kind == "layer":
        allowed.add("objects")
    unknown = payload.keys() - allowed
    if unknown:
        return {"status": "unavailable", "reason": "示例含保存接口不支持的字段：" + ", ".join(sorted(unknown))}
    payload["config_ref"] = config["_ref"]
    context = {"connection": "已初始化的数据库连接", "project_id": "实际存在的项目编号"}
    # 引用不能从作者的示意编号猜测；列表中的对象/关联可能另有引用，由调用方提供。
    variables = {}
    if kind == "object":
        variables["layer"] = "layer_id"
        context["layer_id"] = "项目中实际存在且接受此对象类的层编号"
    if payload.get("father") is not None:
        variables["father"] = "father_id"
        context["father_id"] = "同一项目中实际存在的父层编号"
    for field in ("bind", "objects"):
        if payload.get(field):
            variables[field] = field
            context[field] = ("发出关联字典列表，目标引用使用实际编号" if field == "bind" else
                              "待保存对象列表；字典提供各自的 config_ref，新建不填 id")
    try:
        json.dumps({key: value for key, value in payload.items() if key not in variables}, allow_nan=False)
    except (ValueError, TypeError) as error:
        return {"status": "unavailable", "reason": f"示例不能表示为保存用的 JSON 数据：{error}"}
    parts = [f"    {key!r}: {variables.get(key, pformat(value, width=88, sort_dicts=False))},"
             for key, value in payload.items()]
    for key, variable in variables.items():
        if key not in payload:
            parts.append(f"    {key!r}: {variable},")
    extra = "" if config_root == DEFAULT_ROOT.resolve() else f", config_root={str(config_root)!r}"
    function = f"save_{kind}"
    code = f"from layerweave.support.api import {function}\n\nresult = {function}(connection, project_id, {{\n" + "\n".join(parts) + f"\n}}{extra})"
    return {"status": "available", "function": function, "required_context": context, "code": code}


def io_help(kinds):
    """公共保存接口只展示一次；列名复用实际存储入口。"""
    return {
        "inputs": {kind: [key for key in writable_fields(kind) if key != "type"] +
                   (["objects", "bind"] if kind == "layer" else ["bind"]) for kind in sorted(kinds)},
        "output": "ok/applied：操作结果；data：成功后的完整记录和编号；error：操作失败原因；operation/operation_id：提交状态和操作编号；checks：逐条诊断。",
        "notes": ["新建字典提供 config_ref，不填 id；对象还需真实 layer 编号。type 由配置确定。",
                  "optional=true 允许字段缺省；填入后仍检查类型。未声明 optional 时按 false 检查缺失。",
                  "缺失等约定问题在写入后报告；等级未配置时为 warn。error 诊断不撤销已提交数据。",
                  "example 是封装作者提供的内容示例；default 不会自动补写 information。"],
    }

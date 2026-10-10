"""配置 help：总览、层支持、对象类支持、层与对象类联查；不查询项目数据。"""

import argparse
import json
from layerweave.support.commands import help_examples

from layerweave.tool.builtin.shared.help.catalog import read_support
from layerweave.support.api import format_issue


VIEWS = {"overview": "支持总览", "layers": "层支持详情", "objects": "对象类支持详情", "combined": "层＋对象类支持详情"}
SECTIONS = {"fields": "基础字段", "information": "内容字段", "methods": "方法说明", "rules": "检查约定",
            "constraint": "有效约束", "options": "可调选项", "display": "显示能力",
            "defaults": "可调整默认约定（实际取值见对应项）", "example": "Python 构造参数示例（编号为作者示意值）", "tools": "工具声明"}


def config_help(view="overview", targets=None, *, config_root=None, audience="usage", include_source=None):
    """后三种 view 支持一个或多个配置路径、type、完整 class 路径或唯一类名。"""
    return read_support(view, targets, audience=audience, include_source=include_source,
                        **({"config_root": config_root} if config_root is not None else {}))


def _dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _identity(summary):
    return f"{summary.get('name', summary.get('type', ''))} [{summary.get('type', '')}] · {summary.get('class', '')}"


def _grade(setting):
    return setting["default"] + "".join(f"；{field}={level}" for field, level in setting["fields"].items())


def _format_tools(value):
    """只展示技能引用，不解析路由、检查文件或限制声明内容。"""
    lines = ["  外置技能（供 AI 按路由读取）："]
    if value == []:
        return [*lines, "    （未声明）"]
    if not isinstance(value, list):
        return [*lines, "    " + _dump(value)]
    for tool in value:
        if not isinstance(tool, dict):
            lines.append("    - " + _dump(tool))
            continue
        lines.append(f"    - route: {tool.get('route', '（未填写）')}")
        lines.append(f"      tier: {tool.get('tier', '（未填写）')}")
        lines.append(f"      when: {tool.get('when', '（未填写）')}")
        extra = {key: val for key, val in tool.items() if key not in {"route", "tier", "when"}}
        if extra:
            lines.append("      " + _dump(extra))
    return lines


def _format_usage(item):
    lines = []
    use = item["usage"]
    if "information" in use:
        lines.append("  内容输入：")
        for name, spec in use["information"].items():
            presence = "可选填入" if spec.get("optional", False) else "缺省会产生诊断"
            note = " · " + str(spec["note"]) if spec.get("note") else ""
            lines.append(f"    - information.{name}: {spec.get('type', '未声明类型')} · {presence}{note}")
            extra = {key: value for key, value in spec.items() if key not in {"type", "optional", "note"}}
            if extra:
                lines.append("      " + _dump(extra))
    if "open" in use:
        lines.append("  附加内容：" + ("允许未声明的键" if use["open"] else "仅接受已声明的键"))
    for section in ("rules", "constraint", "options", "display"):
        if use.get(section):
            lines.append(f"  {SECTIONS[section]}：" + "，".join(f"{key}={_dump(value)}" for key, value in use[section].items()))
    for exception in item.get("reporting_exceptions", []):
        detail = f"{exception['field']}={exception['level']}" if "field" in exception else _grade(exception)
        lines.append(f"  特殊汇报 {exception['code']}：{detail}")
    return lines


def _format_entry(item):
    kind = "层" if item["kind"] == "layer" else "对象类"
    ref = item.get("config_ref", item["target"])
    definition = item.get("definition", item.get("summary", {}))
    lines = [f"{kind}：{_identity(definition) if definition else item['target']}", f"  配置：{ref}"]
    if item["status"] == "unavailable":
        lines.append("  状态：配置不可用")
    else:
        for name, label in (("requires", "依赖的工具包"), ("when", "用途"), ("note", "说明"), ("not_for", "适用边界")):
            if definition.get(name):
                lines.append(f"  {label}：{definition[name]}")
        if "tools" in definition:
            lines.extend(_format_tools(definition["tools"]))
        if item.get("lineage"):
            lines.append("  继承：" + " → ".join(item["lineage"]))
        if "accepted_objects" in item:
            lines.append("  支持的对象类：")
            for obj in item["accepted_objects"]:
                owner = f" · 由 {obj['requires']} 登记" if obj.get("requires") else ""
                lines.append(f"    - {_identity(obj)} · {obj['config_ref']}{owner}")
            if not item["accepted_objects"]:
                lines.append("    （没有可列出的对象类）")
            if not item["accepted_objects_complete"]:
                lines.append("    列表不完整：部分对象配置不可用")
        if "definition" in item:
            reporting = item["reporting"]
            if "open" in definition:
                lines.append("  允许附加内容 open：" + _dump(definition["open"]))
            if definition.get("information"):
                lines.append("  疑似笔误汇报（按实际问题字段应用覆盖）：" + _dump(reporting["field_typo"]))
            for section, value in definition.items():
                if section in {"type", "name", "class", "when", "note", "not_for", "extends", "objects", "open", "tools"}:
                    continue
                lines.append(f"  {SECTIONS.get(section, section)}：")
                if section in SECTIONS and value == {}:
                    lines.append("    （无声明）")
                    continue
                if section in {"fields", "information"} and isinstance(value, dict):
                    for name, spec in value.items():
                        text = f"    - {name}: {spec.get('type', '未声明类型')}"
                        text += " · optional=" + _dump(spec.get("optional", False))
                        if "optional" not in spec:
                            text += "（默认）"
                        elif spec["optional"]:
                            text += "（允许缺省，填入仍检查）"
                        if "default" in spec:
                            text += " · 声明默认=" + _dump(spec["default"])
                        if spec.get("note"):
                            text += " · " + str(spec["note"])
                        lines.append(text)
                        extras = {key: val for key, val in spec.items() if key not in {"type", "default", "note", "optional"}}
                        if extras:
                            lines.append("      附加声明：" + _dump(extras))
                        labels = {"missing_field": "缺少字段", "field_type": "类型错误", "field_typo": "疑似笔误"}
                        grades = reporting.get(section, {}).get(name, {})
                        lines.append("      问题汇报：" + "，".join(f"{labels.get(code, code)}={level}" for code, level in grades.items()))
                        origins = item["field_origins"][section][name]
                        lines.append("      声明来源：" + "，".join(f"{key} ← {origin}" for key, origin in origins.items()))
                elif section in {"rules", "constraint", "display", "options"} and isinstance(value, dict):
                    fixed = item["fixed_contracts"].get(section, {})
                    for name, val in value.items():
                        label = "固定约定" if name in fixed else "可调选项" if section == "options" else "默认约定"
                        grade = reporting.get(section, {}).get(name)
                        suffix = " · 同名问题汇报=" + _grade(grade) if grade is not None else ""
                        lines.append(f"    - {name} = {_dump(val)} · {label}{suffix}")
                else:
                    lines.append("    " + _dump(value))
        elif "usage" in item:
            lines.extend(_format_usage(item))
        if "save_example" in item:
            example = item["save_example"]
            if example["status"] == "available":
                lines.append("  保存调用示例（使用实际项目上下文）：")
                lines.append("    所需变量：" + "；".join(f"{key}：{value}" for key, value in example["required_context"].items()))
                lines.extend(["```python", example["code"], "```"])
            else:
                lines.append("  保存示例不可用：" + example["reason"])
    if "source" in item:
        lines.extend(["  当前 TOML 原文：", *["    " + line for line in item["source"].splitlines()]])
    return lines


def format_help(result):
    """同一结构化结果生成文字；新封装/字段/额外节无需增加显示分支。"""
    audience = "开发" if result.get("audience") == "developer" else "使用"
    lines = [f"LayerWeave {audience} help · " + VIEWS.get(result["view"], result["view"]),
             "查看封装定义；项目中的实际层和对象请使用项目查询工具。"]
    if "io" in result:
        lines.append("公共保存接口（本次只列一次）：")
        for kind, fields in result["io"]["inputs"].items():
            lines.append(f"  save_{kind}(connection, project_id, 字典)：" + ", ".join(fields))
        lines.append("  返回：" + result["io"]["output"])
    for item in result["items"]:
        lines.extend(["", *_format_entry(item)])
    if result.get("object_details"):
        lines.extend(["", "支持的对象类详情（共用的说明只展开一次）："])
        for item in result["object_details"]:
            lines.extend(["", *_format_entry(item)])
    if not result["items"]:
        lines.extend(["", "没有匹配的配置条目。"])
    if "io" in result:
        lines.extend(["", *result["io"]["notes"]])
    if result.get("audience") != "developer":
        lines.append("完整字段、继承、汇报和原文：添加 --dev（Python 使用 audience='developer'）。")
    for issue in result.get("issues", []):
        lines.extend(["", format_issue(issue)])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="LayerWeave 配置 help：查看支持的层/对象封装，无需项目或数据库", epilog=help_examples(COMMANDS), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("view", nargs="?", default="overview", choices=VIEWS, help="overview 总览；layers 层；objects 对象类；combined 联查")
    parser.add_argument("targets", nargs="*", help="详情目标，可传多个配置路径、type 或唯一 Python 类名")
    parser.add_argument("--config-root", help="配置根目录，默认使用项目 configs")
    parser.add_argument("--dev", action="store_true", help="开发 help：完整定义、字段来源、汇报设置和当前原文")
    parser.add_argument("--raw", action="store_true", default=None, help="使用详情中也附带当前 TOML 原文及注释")
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON，默认输出文字")
    args = parser.parse_args()
    try:
        if args.view != "overview" and not args.targets:
            parser.error("详情查询需要目标；先运行 overview 查看支持列表")
        result = config_help(args.view, None if args.view == "overview" and not args.targets else args.targets,
                             config_root=args.config_root, audience="developer" if args.dev else "usage", include_source=args.raw)
    except (OSError, ValueError, TypeError) as error:
        result = {"view": args.view, "status": "failed", "items": [],
                  "issues": [{"severity": "error", "message": str(error), **getattr(error, "details", {})}]}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) if args.json else format_help(result))
    return 1 if result["status"] == "failed" else 0



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'config_help',
  'summary': '查看层/对象封装的支持能力与保存示例',
  'entrypoint': 'layerweave.tool.builtin.shared.help.config_help:config_help',
  'cli': 'python -m layerweave.tool.builtin.shared.help.config_help',
  'read_only': True,
  'context': [],
  'parameters': {'view': {'type': 'string',
                          'description': '查询范围',
                          'default': 'overview',
                          'choices': ['overview', 'layers', 'objects', 'combined']},
                 'targets': {'type': 'array', 'description': '详情的配置路径/type/Python 类名列表'},
                 'audience': {'type': 'string',
                              'description': '使用版或开发版',
                              'default': 'usage',
                              'choices': ['usage', 'developer']},
                 'include_source': {'type': 'boolean', 'description': '附带 TOML 原文；开发详情默认提供'},
                 'config_root': {'type': 'string', 'description': '检查或配置查询采用的配置根目录；省略使用项目 configs'}},
  'returns': 'items、配置支持与逐条 issues；不读取项目数据库或导入封装类。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.shared.help.config_help combined text --json'},
               {'cli': 'python -m layerweave.tool.builtin.shared.help.config_help objects model --dev'}]}]


if __name__ == "__main__":
    raise SystemExit(main())

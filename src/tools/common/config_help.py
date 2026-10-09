"""配置 help：总览、层支持、对象类支持、层与对象类联查；不查询项目数据。"""

import argparse
import json

from runtime.api import read_support, format_issue


VIEWS = {"overview": "支持总览", "layers": "层支持详情", "objects": "对象类支持详情", "combined": "层＋对象类支持详情"}
SECTIONS = {"fields": "基础字段", "information": "内容字段", "methods": "方法说明", "rules": "检查约定",
            "constraint": "有效约束", "options": "可调选项", "display": "显示能力",
            "defaults": "可调整默认约定（实际取值见对应项）", "example": "创建参数示例", "tools": "工具声明"}


def config_help(view="overview", targets=None, *, config_root=None, include_source=False):
    """后三种 view 支持一个或多个配置路径、type、完整 class 路径或唯一类名。"""
    return read_support(view, targets, include_source=include_source,
                        **({"config_root": config_root} if config_root is not None else {}))


def _dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _identity(summary):
    return f"{summary.get('name', summary.get('type', ''))} [{summary.get('type', '')}] · {summary.get('class', '')}"


def _format_entry(item):
    kind = "层" if item["kind"] == "layer" else "对象类"
    ref = item.get("config_ref", item["target"])
    definition = item.get("definition", item.get("summary", {}))
    lines = [f"{kind}：{_identity(definition) if definition else item['target']}", f"  配置：{ref}"]
    if item["status"] == "unavailable":
        lines.append("  状态：配置不可用")
    else:
        for name, label in (("when", "用途"), ("note", "说明"), ("not_for", "适用边界")):
            if definition.get(name):
                lines.append(f"  {label}：{definition[name]}")
        if item.get("lineage"):
            lines.append("  继承：" + " → ".join(item["lineage"]))
        if "accepted_objects" in item:
            lines.append("  支持的对象类：")
            for obj in item["accepted_objects"]:
                lines.append(f"    - {_identity(obj)} · {obj['config_ref']}")
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
                if section in {"type", "name", "class", "when", "note", "not_for", "extends", "objects", "open"}:
                    continue
                lines.append(f"  {SECTIONS.get(section, section)}：")
                if section in SECTIONS and value == {}:
                    lines.append("    （无声明）")
                    continue
                if section in {"fields", "information"} and isinstance(value, dict):
                    for name, spec in value.items():
                        text = f"    - {name}: {spec.get('type', '未声明类型')}"
                        if "default" in spec:
                            text += " · 声明默认=" + _dump(spec["default"])
                        if spec.get("note"):
                            text += " · " + str(spec["note"])
                        lines.append(text)
                        extras = {key: val for key, val in spec.items() if key not in {"type", "default", "note"}}
                        if extras:
                            lines.append("      附加声明：" + _dump(extras))
                        labels = {"missing_field": "缺少字段", "field_type": "类型错误", "field_typo": "疑似笔误"}
                        grades = reporting.get(section, {}).get(name, {})
                        lines.append("      问题汇报：" + "，".join(f"{labels.get(code, code)}={level}" for code, level in grades.items()))
                elif section in {"rules", "constraint", "display", "options"} and isinstance(value, dict):
                    fixed = item["fixed_contracts"].get(section, {})
                    for name, val in value.items():
                        label = "固定约定" if name in fixed else "可调选项" if section == "options" else "默认约定"
                        grade = reporting.get(section, {}).get(name)
                        suffix = " · 同名问题汇报=" + _dump(grade) if grade is not None else ""
                        lines.append(f"    - {name} = {_dump(val)} · {label}{suffix}")
                else:
                    lines.append("    " + _dump(value))
    if "source" in item:
        lines.extend(["  当前 TOML 原文：", *["    " + line for line in item["source"].splitlines()]])
    return lines


def format_help(result):
    """同一结构化结果生成文字；新封装/字段/额外节无需增加显示分支。"""
    lines = ["LayerWeave 配置 help · " + VIEWS.get(result["view"], result["view"]),
             "查看封装定义；项目中的实际层和对象请使用项目查询工具。"]
    for item in result["items"]:
        lines.extend(["", *_format_entry(item)])
    if result.get("object_details"):
        lines.extend(["", "支持的对象类详情（共用的说明只展开一次）："])
        for item in result["object_details"]:
            lines.extend(["", *_format_entry(item)])
    if not result["items"]:
        lines.extend(["", "没有匹配的配置条目。"])
    if result["view"] != "overview":
        lines.extend(["", "创建提示：按 class 路径导入类，example 是配置作者提供的参数示例。",
                      "字典保存时添加对应 config_ref；示例编号应替换为实际编号，新增记录不填写 id。",
                      "字段 default 是声明说明；保存不会据此自动补写 information 内容。"])
    for issue in result.get("issues", []):
        lines.extend(["", format_issue(issue)])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="LayerWeave 配置 help：查看支持的层/对象封装，无需项目或数据库")
    parser.add_argument("view", nargs="?", default="overview", choices=VIEWS, help="overview 总览；layers 层；objects 对象类；combined 联查")
    parser.add_argument("targets", nargs="*", help="详情目标，可传多个配置路径、type 或唯一 Python 类名")
    parser.add_argument("--config-root", help="配置根目录，默认使用项目 configs")
    parser.add_argument("--raw", action="store_true", help="详情中附带当前 TOML 原文及注释")
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON，默认输出文字")
    args = parser.parse_args()
    try:
        if args.view != "overview" and not args.targets:
            parser.error("详情查询需要目标；先运行 overview 查看支持列表")
        result = config_help(args.view, None if args.view == "overview" and not args.targets else args.targets,
                             config_root=args.config_root, include_source=args.raw)
    except (OSError, ValueError, TypeError) as error:
        result = {"view": args.view, "status": "failed", "items": [],
                  "issues": [{"severity": "error", "message": str(error), **getattr(error, "details", {})}]}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) if args.json else format_help(result))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

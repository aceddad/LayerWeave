"""操作结果与逐条诊断的共用表达，不执行写入或约束检测。"""

import json
from layerweave.core.identity import reference as target


class InputError(ValueError):
    """在普通错误原因旁保留机器可读的修正线索。"""

    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details


def error_detail(error):
    return {"type": type(error).__name__, "message": str(error), **getattr(error, "details", {})}


def operation_result(status, changes=()):
    return {"status": status, "changes": [
        {"action": change["action"], "target": target(change["kind"], change["project_id"], change["id"])}
        for change in changes
    ]}


def _location(value):
    if not value:
        return ""
    kind, id = value.get("kind", ""), value.get("id")
    if kind in {"layer", "object"}:
        return f"{kind} ({value.get('project_id')}, {id if id is not None else '未分配'})"
    return f"{kind} {id}" if id is not None else kind


def format_issue(issue):
    """一条诊断独立定位目标、字段、原因与检查范围。"""
    location = _location(issue.get("target"))
    if issue.get("field"):
        location += (" · " if location else "") + issue["field"]
    lines = [f"[{issue.get('severity', 'error').upper()}] {location}".rstrip(),
             f"  {issue['message']}"]
    if issue.get("code"):
        lines.append(f"  代码：{issue['code']}")
    if "request_index" in issue:
        lines.append(f"  请求：第 {issue['request_index'] + 1} 条")
    if issue.get("allowed"):
        lines.append("  可选值：" + " / ".join(issue["allowed"]))
    if issue.get("suggestions"):
        lines.append("  建议：" + "；".join(f"{key} → {value}" for key, value in issue["suggestions"].items()))
    if issue.get("candidates"):
        lines.append("  配置候选：" + " / ".join(issue["candidates"]))
        if issue.get("candidate_count", 0) > len(issue["candidates"]):
            lines.append(f"  共 {issue['candidate_count']} 份配置，仅列出最相关的 {len(issue['candidates'])} 份")
    if issue.get("rule") and not issue.get("affected_checks"):
        lines.append(f"  检查：{issue['rule']}")
    for check in issue.get("affected_checks", []):
        lines.append(f"  受影响检查：{check['rule']} · {_location(check.get('target'))}")
    if issue.get("skipped"):
        lines.append("  结果：此项检查无法完成")
    if issue.get("checked_target") and not issue.get("affected_checks"):
        lines.append("  检查对象：" + _location(issue["checked_target"]))
    scopes = {"direct": "本次直接修改的目标", "related": "关联目标，本次未直接修改", "manual": "主动复查"}
    if issue.get("scope") in scopes:
        lines.append("  范围：" + scopes[issue["scope"]])
    for related in issue.get("related", []):
        lines.append("  涉及：" + _location(related))
    return "\n".join(lines)


def format_feedback(result):
    """操作结果先单独列出；检查逐项显示，错误严重程度不改变提交状态。"""
    operation = result["operation"]
    labels = {"create": "已创建", "update": "已更新", "delete": "已删除"}
    if operation["status"] == "committed":
        lines = [f"[写入成功] {_location(item['target'])}：{labels[item['action']]}" for item in operation["changes"]]
    else:
        lines = [{"read": "[读取成功]", "unchanged": "[无变化] 本次没有写入变更。",
                  "failed": "[操作失败] 本次未写入。"}[operation["status"]]]
    if result.get("error"):
        lines.extend(["", format_issue(result["error"])])
    # 文字模式的读取仍返回数据，不能只显示一行“成功”。
    reads = [item for item in result.get("results", [result]) if item.get("action") == "read"]
    for item in reads:
        lines.extend(["", json.dumps(item.get("data"), ensure_ascii=False, indent=2)])
    checks = result.get("checks", {})
    if checks.get("status") == "failed":
        lines.extend(["", format_issue({**checks["error"], "field": "检测执行器", "skipped": True})])
    for issue in checks.get("issues", []):
        lines.extend(["", format_issue(issue)])
    return "\n".join(lines)

"""把独立检测结果与已经提交的数据操作结果区分开。"""

import json

from layerweave.support.feedback import error_detail

_NOT_CONFIGURED = object()


def report(issues):
    """completed 表示检查执行完成；是否符合约定仍须查看 issues。"""
    return {"status": "partial" if any(item.get("skipped") for item in issues) else "completed",
            "issues": [{**item, "severity": item.get("severity", "warn")} for item in issues if item.get("severity") != "none"]}


def run_checks(changes, read_record, checker=None):
    """checker(changes, read_record) 返回问题列表；只提供记录查询入口。"""
    if not changes:
        return {"status": "not_run", "reason": "no_changes", "issues": []}
    if checker is None:
        return {"status": "not_run", "reason": "not_configured", "issues": []}
    try:
        issues = checker(changes, read_record)
        if issues is _NOT_CONFIGURED:
            return {"status": "not_run", "reason": "not_configured", "issues": []}
        if not isinstance(issues, list) or any(not isinstance(issue, dict) for issue in issues):
            raise TypeError("检测器应返回由问题字典组成的列表")
        # 检测输出也须能够通过 JSON 入口返回，不能让反馈格式错误掩盖已提交的写入。
        json.dumps(issues, ensure_ascii=False, allow_nan=False)
    except Exception as error:
        return {
            "status": "failed", "issues": [],
            "error": error_detail(error),
        }
    return report(issues)

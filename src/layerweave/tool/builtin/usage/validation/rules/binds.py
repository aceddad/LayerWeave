"""软关联两端共用检测；失效关联保留并报告。"""

from layerweave.tool.builtin.usage.validation.rules.fields import problem


def check(record, config, read_record):
    issues = []
    for side in ("source", "target"):
        kind = record[f"{side}_kind"]
        if kind not in {"layer", "object"}:
            issues.append(problem(f"关联端点 kind 应为 layer 或 object，实际为 {kind!r}", field=f"{side}_kind", code="bind_kind"))
            continue
        project_id, entity_id = record[f"{side}_project_id"], record[f"{side}_id"]
        if read_record(kind, project_id=project_id, id=entity_id) is None:
            issues.append(problem(f"关联端点不存在：{kind} ({project_id}, {entity_id})",
                                  field=side, code="bind_reference_missing"))
    return issues

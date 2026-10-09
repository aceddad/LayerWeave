"""项目概览：只读层级和数量，Python 字典及纯文本输出共用同一结果。"""

from support.api import read_project_index
from tool.builtin.usage.query._hierarchy import order_layers


def project_overview(connection, project_id):
    """返回 project/counts/layers；项目不存在返回 None。depth=None 表示未归入根层。"""
    index = read_project_index(connection, project_id)
    if index is None:
        return None
    layers = order_layers(index["layers"])
    return {
        "project": index["project"],
        "counts": {"layers": len(index["layers"]),
                   "objects": sum(layer["object_count"] for layer in index["layers"]),
                   "roots": sum(layer["father"] is None for layer in layers),
                   "unplaced_layers": sum(layer["depth"] is None for layer in layers)},
        "layers": layers,
    }


def format_overview(overview):
    """将已有概览格式化为纯文本，不再次查询数据库。"""
    if overview is None:
        return "项目不存在。"
    project, counts = overview["project"], overview["counts"]
    lines = [f"项目 [{project['id']}] {project['name']!r}",
             f"{counts['layers']} 个层 · {counts['objects']} 个对象 · {counts['roots']} 个根层"]
    unplaced_header = False
    for layer in overview["layers"]:
        label = f"[{layer['id']}] {layer['name']!r} ({layer['type']!r}) · {layer['object_count']} 个对象"
        if layer["depth"] is None:
            if not unplaced_header:
                lines.append("未归入根层的层（保留原父编号）：")
                unplaced_header = True
            lines.append(f"- {label} · father={layer['father']}")
        else:
            lines.append("  " * layer["depth"] + "- " + label)
    return "\n".join(lines)


def main():
    from support.cli import parser_for, run_cli

    return run_cli(parser_for("LayerWeave 项目概览（只读）", commands=COMMANDS),
                   lambda connection, args: project_overview(connection, args.project_id), formatter=format_overview)



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'project_overview',
  'summary': '查看项目树、层类型和直属对象数量',
  'entrypoint': 'tool.builtin.usage.query.project_overview:project_overview',
  'cli': 'python -m tool.builtin.usage.query.project_overview',
  'read_only': True,
  'context': ['database', 'project_id'],
  'parameters': {},
  'returns': '项目与层树摘要；项目不存在返回 None。',
  'examples': [{'cli': 'python -m tool.builtin.usage.query.project_overview DATABASE 1 --json'}]}]


if __name__ == "__main__":
    raise SystemExit(main())

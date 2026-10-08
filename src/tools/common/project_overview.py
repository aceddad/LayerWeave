"""项目概览：只读层级和数量，Python 字典及纯文本输出共用同一结果。"""

from collections import defaultdict

from runtime.api import read_project_index


def project_overview(connection, project_id):
    """返回 project/counts/layers；项目不存在返回 None。depth=None 表示未归入根层。"""
    index = read_project_index(connection, project_id)
    if index is None:
        return None
    children = defaultdict(list)
    for layer in index["layers"]:
        children[layer["father"]].append(layer)

    roots = children[None]
    pending = [(layer, 0) for layer in reversed(roots)]
    ordered, placed = [], set()
    while pending:
        layer, depth = pending.pop()
        if layer["id"] in placed:
            continue
        placed.add(layer["id"])
        ordered.append({**layer, "depth": depth})
        pending.extend((child, depth + 1) for child in reversed(children[layer["id"]]))

    # 存储允许父链问题先保存后诊断；概览保留未归入根的层，不伪造根或递归成环。
    unplaced = [{**layer, "depth": None} for layer in index["layers"] if layer["id"] not in placed]
    return {
        "project": index["project"],
        "counts": {"layers": len(index["layers"]),
                   "objects": sum(layer["object_count"] for layer in index["layers"]),
                   "roots": len(roots), "unplaced_layers": len(unplaced)},
        "layers": ordered + unplaced,
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
    from tools._cli import parser_for, run_cli

    return run_cli(parser_for("LayerWeave 项目概览（只读）"),
                   lambda connection, args: project_overview(connection, args.project_id), formatter=format_overview)


if __name__ == "__main__":
    raise SystemExit(main())

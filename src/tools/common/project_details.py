"""详细展开项目或指定子树，可按存储数值筛选对象；不换算轴、不读取外部资源。"""

import json

from runtime.api import read_project_details
from ._hierarchy import order_layers


def project_details(connection, project_id, *, layer_id=None, begin=None, end=None):
    """指定层包含自身和全部子孙层；时间仅筛选对象，保留原位置及命中对象的父层路径。"""
    result = read_project_details(connection, project_id, layer_id=layer_id, begin=begin, end=end)
    if result is None:
        return None
    layers = order_layers(result["layers"], result["scope"]["layer_id"])
    return {**result, "layers": layers,
            "counts": {"layers": len(layers), "objects": sum(len(layer["objects"]) for layer in layers),
                       "unplaced_layers": sum(layer["depth"] is None for layer in layers)}}


def format_details(result):
    """文本树保留完整记录内容，层级用缩进表示；关联保持引用，不递归展开目标。"""
    if result is None:
        return "项目或指定层不存在。"
    dump = lambda value: json.dumps(value, ensure_ascii=False, allow_nan=False)
    lines = ["项目 " + dump(result["project"]), "范围 " + dump(result["scope"]),
             f"{result['counts']['layers']} 个层 · {result['counts']['objects']} 个对象"]
    for layer in result["layers"]:
        indent = "  " * (layer["depth"] or 0)
        suffix = "（未归入根层）" if layer["depth"] is None else ""
        metadata = {key: value for key, value in layer.items() if key not in {"objects", "depth"}}
        lines.append(indent + "- 层 " + dump(metadata) + suffix)
        lines.extend(indent + "  - 对象 " + dump(obj) for obj in layer["objects"])
    return "\n".join(lines)


def main():
    from tools._cli import parser_for, run_cli

    parser = parser_for("LayerWeave 项目详细展开（只读）")
    parser.add_argument("--layer-id", type=int, help="指定起始层，包含该层及全部子孙层")
    parser.add_argument("--begin", type=float, help="位置范围起点，不换算单位")
    parser.add_argument("--end", type=float, help="位置范围终点；两端相等时查询该点")
    return run_cli(parser, lambda connection, args: project_details(
        connection, args.project_id, layer_id=args.layer_id, begin=args.begin, end=args.end,
    ), formatter=format_details)


if __name__ == "__main__":
    raise SystemExit(main())

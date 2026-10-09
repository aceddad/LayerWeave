"""详细展开项目或指定子树，可按存储数值筛选对象；不换算轴、不读取外部资源。"""

import json

from runtime.api import read_project_details, diagnostic_report
from ._hierarchy import order_layers


def _compact_record(record, excluded=()):
    """只省略可由容器确定的身份字段和空展示元数据，不进入 information/axis/bind。"""
    return {key: value for key, value in record.items() if key not in excluded
            and not (key in {"name", "tips"} and value == "")
            and not (key == "bind" and value == [])
            and not (key in {"father", "axis"} and value is None)}


def _compact_details(result):
    layers = []
    for layer in result["layers"]:
        slim = _compact_record(layer, {"project_id", "objects"})
        slim["objects"] = [_compact_record(obj, {"project_id", "layer"}) for obj in layer["objects"]]
        layers.append(slim)
    return {**result, "compact": True, "project": _compact_record(result["project"], {"max_id"}), "layers": layers}


def project_details(connection, project_id, *, layer_id=None, layer_ids=None, begin=None, end=None,
                    compact=False, config_root=None):
    """展开所选子树并保留空层；只在缺失多层目标时读取诊断汇报配置。"""
    result = read_project_details(connection, project_id, layer_id=layer_id, layer_ids=layer_ids, begin=begin, end=end)
    if result is None:
        return None
    layers = order_layers(result["layers"], root_ids=result["scope"]["root_ids"])
    layers = [{**layer, "object_count": len(layer["objects"])} for layer in layers]
    issues = [{"code": "target", "rule": "project_details", "field": "layer_ids",
               "target": {"kind": "layer", "project_id": project_id, "id": id},
               "message": "指定层不存在，已跳过该编号并继续展开其他层"} for id in result["missing_layer_ids"]]
    result = {**result, "layers": layers, "status": "partial" if issues else "completed",
              "issues": diagnostic_report(issues, config_root=config_root)["issues"] if issues else [],
              "counts": {"layers": len(layers), "objects": sum(layer["object_count"] for layer in layers),
                         "unplaced_layers": sum(layer["depth"] is None for layer in layers)}}
    return _compact_details(result) if compact else result


def format_details(result):
    """完整和精简结果共用文本树；每层明确标注本范围内直属对象数量。"""
    if result is None:
        return "项目或指定层不存在。"
    dump = lambda value: json.dumps(value, ensure_ascii=False, allow_nan=False)
    lines = ["项目 " + dump(result["project"]), "范围 " + dump(result["scope"]),
             f"{result['counts']['layers']} 个层 · {result['counts']['objects']} 个对象"]
    for layer in result["layers"]:
        indent = "  " * (layer["depth"] or 0)
        suffix = "（未归入根层）" if layer["depth"] is None else ""
        metadata = {key: value for key, value in layer.items() if key not in {"objects", "depth", "object_count"}}
        lines.append(indent + "- 层 " + dump(metadata) + f" · 本范围 {len(layer['objects'])} 个直属对象" + suffix)
        lines.extend(indent + "  - 对象 " + dump(obj) for obj in layer["objects"])
    return "\n".join(lines)


def main():
    from tools._cli import parser_for, run_cli

    parser = parser_for("LayerWeave 项目详细展开（只读）", commands=COMMANDS)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--layer-id", type=int, help="指定起始层，包含该层及全部子孙层")
    selection.add_argument("--layer-ids", nargs="*", type=int, help="指定多个起始层；不跟编号表示空选择")
    parser.add_argument("--compact", action="store_true", help="省略重复身份和空展示字段，保留内容及配置引用")
    parser.add_argument("--config-root", help="仅用于缺失目标的诊断汇报配置")
    parser.add_argument("--begin", type=float, help="位置范围起点，不换算单位")
    parser.add_argument("--end", type=float, help="位置范围终点；两端相等时查询该点")
    return run_cli(parser, lambda connection, args: project_details(
        connection, args.project_id, layer_id=args.layer_id, layer_ids=args.layer_ids, begin=args.begin, end=args.end,
        compact=args.compact, config_root=args.config_root,
    ), formatter=format_details)



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'project_details',
  'summary': '展开项目或子树的完整/精简内容，支持时间相交筛选',
  'entrypoint': 'tools.common.project_details:project_details',
  'cli': 'python -m tools.common.project_details',
  'read_only': True,
  'context': ['database', 'project_id'],
  'parameters': {'layer_id': {'type': 'integer', 'description': '指定单棵子树，包含后代'},
                 'layer_ids': {'type': 'array', 'description': '子树起始层编号列表，包含全部后代；空列表为空选择'},
                 'begin': {'type': 'number', 'description': '轴上的数值位置，不换算单位'},
                 'end': {'type': 'number', 'description': '轴上的数值位置，不换算单位'},
                 'compact': {'type': 'boolean', 'description': '省略重复容器信息与空说明', 'default': False},
                 'config_root': {'type': 'string', 'description': '检查或配置查询采用的配置根目录；省略使用项目 configs'}},
  'returns': 'project、scope、layers/objects/bind、数量、缺失目标和逐条 issues；空层保留。',
  'examples': [{'cli': 'python -m tools.common.project_details DATABASE 1 --layer-ids 4 7 --begin 10 --end 20 '
                       '--compact --json'}],
  'notes': ['不指定层时展开整个项目；时间只筛选对象，层本身不因零命中被省略。']}]


if __name__ == "__main__":
    raise SystemExit(main())

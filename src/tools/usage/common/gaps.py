"""插空档的封装入口：范围选择、跨界分割和后移共用一个事务。"""

import json
from pathlib import Path
from runtime.api import insert_gap, format_feedback


def format_gap(result):
    lines = [f"插空档操作：{result['operation_id']}", format_feedback(result)]
    if result["ok"]:
        for gap in result["data"]["gaps"]:
            lines.append(f"层 {gap['layer_id']}：插入时段 [{gap['begin']}, {gap['end']})，实际长度 {gap['length']}")
        for split in result["data"]["splits"]:
            lines.append(f"对象 {split['object_id']} 分为：" + ", ".join(str(row["id"]) for row in split["segments"]))
        for item in result["data"].get("kept", []):
            lines.append(f"对象 {item['id']} 保持原样：[{item['begin']}, {item['end']})，仍可能覆盖插入时段。")
        for item in result["data"].get("stretched", []):
            lines.append(f"对象 {item['id']} 延长终点：{item['previous_end']} → {item['end']}，起点 {item['begin']} 保持。")
        for item in result["data"].get("moved", []):
            lines.append(f"对象 {item['id']} 整体后移：[{item['previous_begin']}, {item['previous_end']}) → [{item['begin']}, {item['end']})")
        lines.append(f"另外平移 {len(result['data']['shifted'])} 个对象。")
    else:
        for item in result.get("error", {}).get("required_crossings", result.get("error", {}).get("required_splits", [])):
            choices = " / ".join(result.get("error", {}).get("allowed", ["split", "keep", "stretch", "move"]))
            lines.append(f"需为对象 {item['object_id']} 选择 {choices}：层 {item['layer_id']}，[{item['begin']}, {item['end']})，切点 {item['at']}")
        if result.get("error", {}).get("unused_object_ids"):
            lines.append("这些对象当前不跨界：" + str(result["error"]["unused_object_ids"]))
    return "\n".join(lines)


def main():
    from tools.shared._cli import parser_for, run_cli
    parser = parser_for(COMMANDS[0]["summary"], commands=COMMANDS)
    parser.add_argument("at", type=float, help=COMMANDS[0]["parameters"]["at"]["description"])
    parser.add_argument("length", type=float, help=COMMANDS[0]["parameters"]["length"]["description"])
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--layer-id", type=int, help="仅此层直接装载的对象")
    scope.add_argument("--layer-ids", type=int, nargs="*", help="子树起始层列表，包含全部后代；空列表不选对象")
    scope.add_argument("--project", dest="whole_project", action="store_true", help="明确选择整个项目")
    parser.add_argument("--contents-file", type=Path, help="JSON 列表：每个跨界对象提供 object_id/action；split 另需两段 information，格式见下方示例")
    parser.add_argument("--config-root", help=COMMANDS[0]["parameters"]["config_root"]["description"])
    def execute(connection, args):
        contents = json.loads(args.contents_file.read_text(encoding="utf-8-sig")) if args.contents_file else None
        return insert_gap(connection, args.project_id, at=args.at, length=args.length, layer_id=args.layer_id,
                          layer_ids=args.layer_ids, whole_project=args.whole_project, crossing_actions=contents,
                          **({"config_root": args.config_root} if args.config_root is not None else {}))
    return run_cli(parser, execute, formatter=format_gap)



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'insert_gap',
  'summary': '明确选范围并插入时间；跨界对象逐个选择 split、keep、stretch 或 move',
  'entrypoint': 'runtime.api:insert_gap',
  'cli': 'python -m tools.usage.common.gaps',
  'read_only': False,
  'context': ['database', 'project_id'],
  'parameters': {'at': {'type': 'number', 'description': '插入位置，按每个所选层的轴精度落点；不是相对偏移量', 'required': True},
                 'length': {'type': 'number', 'description': '正的插入长度，单位按所在轴解释，落点后仍须大于零', 'required': True},
                 'layer_id': {'type': 'integer', 'description': '该项目内的层编号，仅直属对象'},
                 'layer_ids': {'type': 'array', 'description': '子树起始层编号列表，包含全部后代；空列表为空选择'},
                 'whole_project': {'type': 'boolean',
                                   'description': '显式选择整个项目；CLI 使用 --project',
                                   'default': False},
                 'crossing_actions': {'type': 'array',
                                      'description': 'object_id/action 项列表；action 为 split、keep、stretch 或 '
                                                     'move；split 另需 first_information/second_information'},
                 'split_contents': {'type': 'array', 'description': '旧版分段内容参数，仅作兼容，不能与 crossing_actions 同传'},
                 'config_root': {'type': 'string', 'description': '检查或配置查询采用的配置根目录；省略使用项目 configs'}},
  'returns': '标准操作结果；data 含 scope、插入时段 gaps、splits、kept、stretched、moved、shifted；不保证该时段完全空白。',
  'examples': [{'cli': 'python -m tools.usage.common.gaps DATABASE 1 10 2 --layer-ids 4 --contents-file '
                       'actions.json --json',
                'files': {'actions.json': [{'object_id': 8,
                                            'action': 'split',
                                            'first_information': {'text': '前段'},
                                            'second_information': {'text': '后段'}},
                                           {'object_id': 9, 'action': 'keep'},
                                           {'object_id': 10, 'action': 'stretch'},
                                           {'object_id': 11, 'action': 'move'}]}},
               {'cli': 'python -m tools.usage.common.gaps DATABASE 1 10 2 --project --json'}],
  'aliases': ['gaps', 'gap'],
  'notes': ['必须明确选择 --layer-id、--layer-ids、--project 之一；子树包含后代，直属层不包含子层。',
            '文件最外层是 JSON 列表，列出的对象必须实际跨界；缺少处理方式时本批不写。',
            'keep 保持原样；stretch 仅将终点后移实际插入长度；move 将起终点一起后移该长度。',
            '这三种动作都可能覆盖插入时段；内容和关联不变，不做音视频变速、补帧或资源裁切。',
            '没有跨界对象时可以省略内容文件。旧文件含完整的两段内容但未写 action 时按 split 兼容。']}]


if __name__ == "__main__":
    raise SystemExit(main())

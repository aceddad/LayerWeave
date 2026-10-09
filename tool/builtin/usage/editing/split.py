"""按显式内容分割对象，支持单点或多点，不推测媒体切片。"""

import json
from pathlib import Path
from tool.builtin.usage.editing.timeline import split_object
from support.api import format_feedback


def format_split(result):
    lines = [f"分割操作：{result['operation_id']}", format_feedback(result)]
    if result["ok"]:
        for segment in result["data"]["segments"]:
            lines.append(f"对象 {segment['id']}：[{segment['begin']}, {segment['end']})")
        lines.append("实际切点：" + json.dumps(result["data"]["cuts"], ensure_ascii=False))
    return "\n".join(lines)


def main():
    from support.cli import parser_for, run_cli
    parser = parser_for("LayerWeave 分割：数据文件提供 first_information 与 cuts", commands=COMMANDS)
    parser.add_argument("object_id", type=int, help=COMMANDS[0]["parameters"]["object_id"]["description"])
    parser.add_argument("--data-file", type=Path, required=True, help="JSON 对象，含 first_information 和 cuts；每个切点含 at/information，完整示例见下方")
    parser.add_argument("--config-root", help=COMMANDS[0]["parameters"]["config_root"]["description"])
    def execute(connection, args):
        payload = json.loads(args.data_file.read_text(encoding="utf-8-sig"))
        return split_object(connection, args.project_id, args.object_id, **payload,
                            **({"config_root": args.config_root} if args.config_root is not None else {}))
    return run_cli(parser, execute, formatter=format_split)



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'split_object',
  'summary': '按明确切点与各段内容分割对象，第一段保留编号和关联',
  'entrypoint': 'tool.builtin.usage.editing.timeline:split_object',
  'cli': 'python -m tool.builtin.usage.editing.split',
  'read_only': False,
  'context': ['database', 'project_id'],
  'parameters': {'object_id': {'type': 'integer', 'description': '当前项目中待分割的对象编号；原区间由数据库读取', 'required': True},
                 'first_information': {'type': 'object', 'description': '第一段完整内容；非空 cuts 时必需'},
                 'cuts': {'type': 'array',
                          'description': '按升序提供 at/information 项，每个切点对应从该处开始的新段；空列表不写入',
                          'required': True},
                 'config_root': {'type': 'string', 'description': '检查或配置查询采用的配置根目录；省略使用项目 configs'}},
  'returns': '标准操作结果；data 含 project_id、object_id、请求与实际 cuts、各段 segments；支持整批撤销。',
  'examples': [{'cli': 'python -m tool.builtin.usage.editing.split DATABASE 1 8 --data-file parts.json --json',
                'files': {'parts.json': {'first_information': {'text': '前段'},
                                         'cuts': [{'at': 14, 'information': {'text': '后段'}}]}}}],
  'aliases': ['split'],
  'notes': ['示例为文字对象；编号 8 应替换为实际对象，14 是对象区间内部的轴位置。', '文件最外层是 JSON 对象；各段 information 为完整字典，不自动裁切资源。']}]


if __name__ == "__main__":
    raise SystemExit(main())

"""跨项目复制/剪切，共用子树复制与删除实现。"""

from runtime.api import transfer_subtree, format_feedback


def format_transfer(result):
    lines = [f"跨项目操作：{result['operation_id']}"]
    if result["ok"]:
        data = result["data"]
        lines.append(f"{data['mode']}：项目 {data['source_project_id']} 的层 {data['source_layer_id']} → 项目 {data['project_id']} 的层 {data['layer_id']}")
        for kind, pairs in data["id_map"].items():
            lines.extend(f"  {kind} {row['old_id']} → {row['new_id']}" for row in pairs)
        if data["redirected_bind_ids"]:
            lines.append("跟随新地址的外部关联：" + str(data["redirected_bind_ids"]))
    lines.append(format_feedback(result))
    return "\n".join(lines)


def main():
    from tools._cli import parser_for, run_cli
    parser = parser_for("LayerWeave 跨项目复制/剪切：保留数值，目标根层重新发号", commands=COMMANDS)
    parser.add_argument("command", choices=("copy", "cut"))
    parser.add_argument("layer_id", type=int)
    parser.add_argument("target_project_id", type=int)
    parser.add_argument("--name")
    parser.add_argument("--config-root")
    return run_cli(parser, lambda connection, args: transfer_subtree(connection, args.project_id, args.layer_id,
                   args.target_project_id, mode=args.command, name=args.name,
                   **({"config_root": args.config_root} if args.config_root is not None else {})), formatter=format_transfer)



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'transfer_subtree',
  'summary': '同库跨项目复制/剪切子树；剪切的外部入向引用跟随新身份',
  'entrypoint': 'runtime.api:transfer_subtree',
  'cli': 'python -m tools.common.transfer',
  'read_only': False,
  'context': ['database', 'project_id'],
  'parameters': {'layer_id': {'type': 'integer', 'description': '源项目起始层', 'required': True},
                 'target_project_id': {'type': 'integer', 'description': '不同的目标项目', 'required': True},
                 'mode': {'type': 'string', 'description': '复制或剪切', 'default': 'copy', 'choices': ['copy', 'cut']},
                 'name': {'type': 'string', 'description': '目标根层名字'},
                 'config_root': {'type': 'string', 'description': '检查或配置查询采用的配置根目录；省略使用项目 configs'}},
  'returns': '标准操作结果、operation_id、data/results 和提交后 checks；可按操作编号撤销。',
  'examples': [{'cli': 'python -m tools.common.transfer DATABASE 1 copy 4 2 --json'},
               {'cli': 'python -m tools.common.transfer DATABASE 1 cut 4 2 --json'}],
  'aliases': ['transfer'],
  'notes': ['目标根层重新发号，位置数值精确保留，不做单位换算或重新落点。']}]


if __name__ == "__main__":
    raise SystemExit(main())

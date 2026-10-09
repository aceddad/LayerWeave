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
    parser = parser_for("LayerWeave 跨项目复制/剪切：保留数值，目标根层重新发号")
    parser.add_argument("command", choices=("copy", "cut"))
    parser.add_argument("layer_id", type=int)
    parser.add_argument("target_project_id", type=int)
    parser.add_argument("--name")
    parser.add_argument("--config-root")
    return run_cli(parser, lambda connection, args: transfer_subtree(connection, args.project_id, args.layer_id,
                   args.target_project_id, mode=args.command, name=args.name,
                   **({"config_root": args.config_root} if args.config_root is not None else {})), formatter=format_transfer)


if __name__ == "__main__":
    raise SystemExit(main())

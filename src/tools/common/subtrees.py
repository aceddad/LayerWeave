"""子树删除与整层复制，沿用公共 API 和标准操作/诊断反馈。"""

from runtime.api import DEFAULT_CHECKER, copy_subtree as copy, delete_subtree as delete, format_feedback


def delete_subtree(connection, project_id, layer_id, *, config_root=None, checker=DEFAULT_CHECKER):
    return delete(connection, project_id, layer_id, checker=checker,
                  **({"config_root": config_root} if config_root is not None else {}))


def copy_subtree(connection, project_id, layer_id, *, name=None, config_root=None, checker=DEFAULT_CHECKER):
    return copy(connection, project_id, layer_id, name=name, checker=checker,
                **({"config_root": config_root} if config_root is not None else {}))


def format_subtree(result):
    label = "复制子树" if result["tool"] == "copy_subtree" else "删除子树"
    lines = [f"{label} · 操作编号 {result['operation_id']}"]
    if result["ok"]:
        data, counts = result["data"], result["data"]["counts"]
        lines.append(f"项目 {data['project_id']} · {counts['layers']} 个层、{counts['objects']} 个对象、{counts['binds']} 条出向关联")
        if "id_map" in data:
            lines.append(f"副本根层：{data['layer_id']}；原根层：{data['source_layer_id']}")
            for kind, pairs in data["id_map"].items():
                lines.extend(f"  {kind} {pair['old_id']} → {pair['new_id']}" for pair in pairs)
    lines.append(format_feedback(result))
    return "\n".join(lines)


def main():
    from tools._cli import parser_for, run_cli
    parser = parser_for("LayerWeave 子树操作：同一事务执行，可按操作编号撤销")
    parser.add_argument("command", choices=("copy", "delete"))
    parser.add_argument("layer_id", type=int, help="包含该层、全部子孙层和装载对象")
    parser.add_argument("--name", help="副本根层名字，仅用于 copy")
    parser.add_argument("--config-root", help="提交后检查使用的配置目录")

    def execute(connection, args):
        if args.command == "copy":
            return copy_subtree(connection, args.project_id, args.layer_id, name=args.name, config_root=args.config_root)
        if args.name is not None:
            raise ValueError("--name 仅用于 copy")
        return delete_subtree(connection, args.project_id, args.layer_id, config_root=args.config_root)
    return run_cli(parser, execute, formatter=format_subtree)


if __name__ == "__main__":
    raise SystemExit(main())

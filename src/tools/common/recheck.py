"""项目、多棵子树或指定对象的只读复查。"""

from runtime.api import recheck as check


def recheck(connection, project_id, *, layer_ids=None, object_ids=None, config_root=None):
    return check(connection, project_id, layer_ids=layer_ids, object_ids=object_ids,
                 **({"config_root": config_root} if config_root is not None else {}))


def format_recheck(result):
    scope, counts = result["scope"], result["counts"]
    label = {"project": "整个项目", "subtrees": "层的子树", "objects": "指定对象"}[scope["mode"]]
    selected = "" if scope["ids"] is None else f" {scope['ids']}"
    state = "检查执行完成" if result["status"] == "completed" else "部分检查未完成，原因见逐条诊断"
    return (f"复查范围：项目 {scope['project_id']} · {label}{selected}\n"
            f"范围内：{counts['layers']} 个层，{counts['objects']} 个对象\n"
            f"{state}；显示 {result['issue_counts']['error']} 条错误、{result['issue_counts']['warn']} 条警告。")


def main():
    from tools._cli import parser_for, run_cli
    parser = parser_for("LayerWeave 主动复查：省略范围时检查整个项目")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--layer-ids", type=int, nargs="*", help="一个或多个子树起始层；空列表表示空选择")
    scope.add_argument("--object-ids", type=int, nargs="*", help="一个或多个对象；包含必要的关系检查")
    parser.add_argument("--config-root", help="配置根目录")
    return run_cli(parser, lambda connection, args: recheck(connection, args.project_id,
                   layer_ids=args.layer_ids, object_ids=args.object_ids, config_root=args.config_root), formatter=format_recheck)


if __name__ == "__main__":
    raise SystemExit(main())

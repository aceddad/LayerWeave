"""子树删除与整层复制，沿用公共 API 和标准操作/诊断反馈。"""

from layerweave.support.api import DEFAULT_CHECKER, format_feedback
from layerweave.tool.builtin.usage.editing.tree_service import copy_subtree as copy, delete_subtree as delete


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
    from layerweave.support.cli import parser_for, run_cli
    parser = parser_for("LayerWeave 子树操作：同一事务执行，可按操作编号撤销", commands=COMMANDS)
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


# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'copy_subtree',
  'summary': '同项目同父层复制整棵子树并重映射内部关联',
  'entrypoint': 'layerweave.tool.builtin.usage.editing.tree_service:copy_subtree',
  'session_entrypoint': 'layerweave.tool.builtin.usage.editing.tree_service:copy_subtree_in_session',
  'cli': 'python -m layerweave.tool.builtin.usage.editing.subtrees',
  'read_only': False,
  'context': ['database', 'project_id'],
  'returns': '标准操作结果、operation_id、data/results 和提交后 checks；可按操作编号撤销。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.usage.editing.subtrees DATABASE 1 copy 4 --name 副本 '
                       '--json',
                'arguments': {'layer_id': 4}}],
  'notes': ['外部入向关联不复制，外部目标保持原引用。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'project_id': {'type': 'integer', 'description': '明确的项目编号'},
                                  'layer_id': {'type': 'integer', 'description': '起始层，包含全部后代'},
                                  'name': {'type': ['string', 'null'], 'description': '副本根层名字'},
                                  'config_root': {'type': 'string',
                                                  'description': '检查或配置查询采用的配置根目录；省略使用项目 configs'}},
                   'additionalProperties': False,
                   'required': ['database', 'layer_id', 'project_id']},
  'mcp': {'route': 'edit', 'group': 'editing', 'database': 'connection', 'paths': ['config_root']},
  'cli_only': ['command', 'json']},
 {'name': 'delete_subtree',
  'summary': '删除子树、对象和其出向关联，保留外部入向引用',
  'entrypoint': 'layerweave.tool.builtin.usage.editing.tree_service:delete_subtree',
  'session_entrypoint': 'layerweave.tool.builtin.usage.editing.tree_service:delete_subtree_in_session',
  'cli': 'python -m layerweave.tool.builtin.usage.editing.subtrees',
  'read_only': False,
  'context': ['database', 'project_id'],
  'returns': '标准操作结果、operation_id、data/results 和提交后 checks；可按操作编号撤销。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.usage.editing.subtrees DATABASE 1 delete 4 --json',
                'arguments': {'layer_id': 4}}],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'project_id': {'type': 'integer', 'description': '明确的项目编号'},
                                  'layer_id': {'type': 'integer', 'description': '起始层，包含全部后代'},
                                  'config_root': {'type': 'string',
                                                  'description': '检查或配置查询采用的配置根目录；省略使用项目 configs'}},
                   'additionalProperties': False,
                   'required': ['database', 'layer_id', 'project_id']},
  'mcp': {'route': 'edit', 'group': 'editing', 'database': 'connection', 'paths': ['config_root']},
  'cli_only': ['command', 'json']}]


if __name__ == "__main__":
    raise SystemExit(main())

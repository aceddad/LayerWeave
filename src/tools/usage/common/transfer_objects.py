"""选中对象跨项目复制/剪切；事务、发号与关联映射复用存储层。"""

from runtime.api import transfer_objects
from .transfer import format_transfer


def main():
    from tools.shared._cli import parser_for, run_cli
    parser = parser_for("LayerWeave 对象跨项目复制/剪切：放入指定已有层，保留位置数值", commands=COMMANDS)
    parser.add_argument("mode", choices=("copy", "cut"), help="copy 保留源对象；cut 删除源对象并使外部入向引用跟随")
    parser.add_argument("target_project_id", type=int, help="目标项目编号，须与源项目不同")
    parser.add_argument("target_layer_id", type=int, help="目标项目中已有的层编号")
    parser.add_argument("--ids", type=int, nargs="+", required=True, help="源项目中的一个或多个对象编号")
    parser.add_argument("--config-root")
    return run_cli(parser, lambda connection, args: transfer_objects(
        connection, args.project_id, args.ids, args.target_project_id, args.target_layer_id, mode=args.mode,
        **({"config_root": args.config_root} if args.config_root is not None else {})), formatter=format_transfer)


COMMANDS = [{'name': 'transfer_objects',
  'summary': '同库跨项目复制/剪切选中对象及出向关联，放入指定已有层',
  'entrypoint': 'runtime.api:transfer_objects',
  'cli': 'python -m tools.usage.common.transfer_objects',
  'read_only': False,
  'context': ['database', 'project_id'],
  'parameters': {'object_ids': {'type': 'array[integer]',
                                'required': True,
                                'description': '源项目对象编号列表；去重，空列表不写入'},
                 'target_project_id': {'type': 'integer', 'required': True, 'description': '不同的目标项目编号'},
                 'target_layer_id': {'type': 'integer', 'required': True, 'description': '目标项目中已有的层编号'},
                 'mode': {'type': 'string',
                          'default': 'copy',
                          'choices': ['copy', 'cut'],
                          'description': '复制或剪切'},
                 'config_root': {'type': 'string', 'description': '提交后检查的配置根目录，省略使用项目 configs'}},
  'returns': '标准操作结果与 checks；data 含源对象编号、目标层、counts、id_map 和 redirected_bind_ids；按 operation_id 整批撤销。',
  'examples': [{'cli': 'python -m tools.usage.common.transfer_objects DATABASE 1 copy 2 4 --ids 8 9 --json'},
               {'cli': 'python -m tools.usage.common.transfer_objects DATABASE 1 cut 2 4 --ids 8 --json'}],
  'notes': ['源对象可以来自不同层；目标为一个已有层，层本身不复制。',
            '位置原数值保留；不换算轴、不复制媒体或改写 information。兼容性与重叠提交后检查。',
            '内部关联映射新编号，外部出向目标不变；剪切使外部入向引用跟随新地址，源层保留。']}]


if __name__ == "__main__":
    raise SystemExit(main())

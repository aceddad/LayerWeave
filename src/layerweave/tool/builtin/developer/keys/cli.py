"""本地 KEY 管理 CLI；实际密钥通过隐藏输入、标准输入或本地数据文件录入。"""
import argparse
import getpass
import json
from pathlib import Path
import sys
import warnings

from layerweave.support.commands import help_examples
from layerweave.support.feedback import InputError, error_detail
from .service import ACTIONS, manage_keys


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse 的默认错误会原样回显未知参数；误传 --key 时也不能打印密钥。
        self.print_usage(sys.stderr)
        self.exit(2, "参数格式不正确，请用 --help 查看用法；KEY 请用 --prompt-key 或 --key-stdin 提供。\n")


def _data(path):
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError) as error:
        raise InputError("输入文件不是有效的 UTF-8 JSON", field="data_file") from error


def main():
    parser = _Parser(description="管理本地 KEY 与连接说明；普通查询不显示密钥原文", allow_abbrev=False,
                                     epilog=help_examples(COMMANDS), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=ACTIONS, help="connections 查看连接信息；不发送网络请求")
    parser.add_argument("name", nargs="?", help="条目名称；create/update/delete 必填")
    parser.add_argument("--store", type=Path, help="真实 JSON 文件，默认用户目录 .layerweave/keys.json")
    parser.add_argument("--data-file", type=Path, help="create/update 的字段对象，used 为字符串列表")
    parser.add_argument("--template", type=Path, help="init 使用的示例，默认包内 example.json")
    parser.add_argument("--output", type=Path, help="export 写出的示例文件；省略时仅返回模板数据")
    secret = parser.add_mutually_exclusive_group()
    secret.add_argument("--prompt-key", action="store_true", help="隐藏输入 KEY，不放进命令行参数")
    secret.add_argument("--key-stdin", action="store_true", help="从标准输入读取 KEY，去掉末尾换行")
    parser.add_argument("--json", action="store_true", help="输出 JSON；不包含真实 KEY")
    args = parser.parse_args()
    try:
        if args.action in {"create", "update", "delete"} and args.name is None:
            raise InputError("此操作需要 KEY 条目名称", field="name")
        if (args.prompt_key or args.key_stdin) and args.action not in {"create", "update"}:
            raise InputError("密钥输入只用于 create/update", field="action")
        data = _data(args.data_file)
        if args.prompt_key or args.key_stdin:
            if data is None:
                data = {}
            if not isinstance(data, dict):
                raise InputError("输入文件需要字段对象", field="data_file")
            if args.prompt_key:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", getpass.GetPassWarning)
                        data["key"] = getpass.getpass("KEY（输入不显示）：")
                except getpass.GetPassWarning as error:
                    raise InputError("此终端不支持隐藏输入，请使用 --key-stdin 或本地数据文件", field="key") from error
            else:
                data["key"] = sys.stdin.read().rstrip("\r\n")
        result = manage_keys(args.action, args.name, data=data, store=args.store, template=args.template, output=args.output)
        if args.output is not None:
            result["output"] = str(args.output.expanduser().resolve())
    except (OSError, ValueError, EOFError) as error:
        result = {"ok": False, "error": error_detail(error)}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print(f"已完成：{result['action']}\n本地文件：{result['store']}")
        if "output" in result:
            print(f"示例文件：{result['output']}")
        print(json.dumps(result["data"], ensure_ascii=False, indent=2))
    else:
        print("操作失败：" + result["error"]["message"])
        if result["error"].get("allowed"):
            print("可选值：" + " / ".join(result["error"]["allowed"]))
    return 0 if result["ok"] else 1


COMMANDS = [{'name': 'manage_keys',
  'aliases': ['keys'],
  'summary': '管理本地 KEY、环境变量名、服务地址、默认模型与通用 used 指引；导出空密钥示例',
  'entrypoint': 'layerweave.tool.builtin.developer.keys.service:manage_keys',
  'cli': 'python -X utf8 -m layerweave.tool.builtin.developer.keys.cli',
  'read_only': False,
  'context': [],
  'returns': 'ok/action/store/data；普通结果包含 key_configured，不含 key。程序读取密钥使用本包 service.get_key。',
  'examples': [{'cli': 'python -X utf8 -m layerweave.tool.builtin.developer.keys.cli init --json',
                'arguments': {'action': 'read'}},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.developer.keys.cli create image-service --data-file '
                       'connection.json --prompt-key --json',
                'files': {'connection.json': {'env_name': '<请填上环境变量名>',
                                              'base_url': '<请填上模型服务地址>',
                                              'model': '<请填上你的所选模型>',
                                              'used': []}}},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.developer.keys.cli connections image-service --json'},
               {'cli': 'python -X utf8 -m layerweave.tool.builtin.developer.keys.cli export --output keys.example.json '
                       '--json'}],
  'notes': ['used 是技能、脚本、工具或其他调用方的使用指引，不是权限限制。',
            'KEY 从隐藏输入、标准输入或本地文件录入；不提供把 KEY 直接放入命令行的参数。',
            '真实文件只在本机维护；上传生成的示例，三个连接字段保留中文填写提示。'],
  'input_schema': {'type': 'object',
                   'properties': {'action': {'type': 'string',
                                             'default': 'read',
                                             'description': 'connections 只展示连接和 used，不检测网络；export 不含实际 KEY',
                                             'enum': ['init',
                                                      'create',
                                                      'read',
                                                      'update',
                                                      'delete',
                                                      'connections',
                                                      'export']},
                                  'name': {'type': ['string', 'null'],
                                           'description': '任意调用方共用的条目名称；create/update/delete 必填'},
                                  'data': {'type': ['object', 'null'],
                                           'description': 'create/update 字段：key/env_name/base_url/model 字符串、used '
                                                          '字符串列表；CLI 用 --data-file'},
                                  'store': {'type': ['string', 'null'],
                                            'description': '本地明文 JSON，默认用户目录 .layerweave/keys.json，不随软件分发'},
                                  'template': {'type': ['string', 'null'],
                                               'description': 'init 来源，默认包内 example.json；建立空条目，不覆盖已有文件'},
                                  'output': {'type': ['string', 'null'],
                                             'description': 'export 示例输出文件；名称和 used 保留，KEY 清空，连接字段替换为中文提示'}},
                   'additionalProperties': False,
                   'required': []},
  'mcp': {'route': 'admin',
          'group': 'developer',
          'paths': ['output', 'store', 'template'],
          'route_by': 'action',
          'action_routes': {'init': 'admin',
                            'create': 'admin',
                            'read': 'query',
                            'update': 'admin',
                            'delete': 'admin',
                            'connections': 'query',
                            'export': 'query'},
          'output_path_route': 'admin'},
  'cli_mapping': {'data': ['data_file', 'key_stdin', 'prompt_key']},
  'cli_only': ['json']}]


if __name__ == "__main__":
    raise SystemExit(main())

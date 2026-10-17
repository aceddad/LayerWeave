"""python -X utf8 -m layerweave.tool.builtin.shared.mcp --config mcp.json。"""
import argparse
import json
import logging
from pathlib import Path


def main():
    from layerweave.support.commands import help_examples
    parser=argparse.ArgumentParser(description='LayerWeave 可选 MCP 服务（stdio）；安装 layerweave[mcp]。',
        epilog=help_examples(COMMANDS),formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config',type=Path,help='本地 JSON 配置；相对工作目录以配置文件目录为基准')
    parser.add_argument('--list',action='store_true',help='只输出有效动作和问题，不启动服务')
    args=parser.parse_args()
    from .runtime import Runtime
    try:
        runtime=Runtime(args.config)
    except (OSError,ValueError,TypeError) as error:
        parser.error(str(error))
    if args.list:
        print(json.dumps({'items':[runtime.catalog.summary(b) for b in runtime.catalog.bindings.values()],
                          'issues':runtime.catalog.issues},ensure_ascii=False,indent=2))
        return 0
    try:
        import anyio
        from mcp.server.stdio import stdio_server
        from .server import create_server
    except ImportError as error:
        parser.error('缺少可选依赖，请安装 pip install "layerweave[mcp]"：'+str(error))
    logging.basicConfig(level=logging.INFO)
    server=create_server(runtime)

    async def serve():
        async with stdio_server() as (read,write):
            await server.run(read,write,server.create_initialization_options())
    anyio.run(serve)
    return 0


COMMANDS = [{'name': 'mcp_server',
  'summary': '启动标准 stdio MCP；四个通用入口与按声明暴露的常用动作',
  'entrypoint': 'layerweave.tool.builtin.shared.mcp:create_server',
  'cli': 'python -X utf8 -m layerweave.tool.builtin.shared.mcp',
  'read_only': False,
  'input_schema': {'type': 'object',
                   'properties': {'config': {'type': ['string', 'object', 'null'],
                                             'description': '启动 JSON 配置路径或配置对象'}},
                   'additionalProperties': False},
  'examples': [{'cli': 'python -X utf8 -m layerweave.tool.builtin.shared.mcp --config mcp.json',
                'files': {'mcp.json': {'workspace': '.', 'exposure': {}, 'disabled': []}}}],
  'mcp': {'enabled': False, 'reason': '服务启动入口使用 CLI，不经运行中的 MCP 再启动一个服务'},
  'cli_only': ['list']}]


if __name__=='__main__':
    raise SystemExit(main())

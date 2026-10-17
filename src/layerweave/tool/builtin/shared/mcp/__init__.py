"""可选 MCP 接入；导入本包不加载 SDK、不启动服务。"""


def create_runtime(config=None):
    from .runtime import Runtime
    return Runtime(config)


def create_server(config=None):
    from .server import create_server as build
    return build(config)


__all__ = ['create_runtime', 'create_server']

# 内部工具 · 共用支持

这里为使用、开发和未来视图工具提供共用实现。[返回内部工具导航](../README.md)。shared 不单独构成第四类受众。

| 文件 | 职责 |
|---|---|
| [command_help.py](command_help.py) | 命令总览或多目标详情 |
| [config_help.py](config_help.py) | 配置支持说明；既有使用版和开发版共用实现 |
| [catalog.py](catalog.py) | 静态发现各命令自己的 COMMANDS，不执行工具或连接数据库 |
| [_cli.py](_cli.py) | 数据库打开、JSON/文字输出、退出码等 CLI 共用代码 |

## 使用

```sh
python -m tools.shared.command_help
python -m tools.shared.command_help split insert_gap undo --json
python -m tools.shared.config_help combined text
python -m tools.shared.config_help objects model --dev
```

从项目 src 运行。命令 help、配置 help 的参数、返回和默认展示保持原有行为；本次不增加分类筛选、权限限制或 MCP 执行器。

完整说明见[命令声明与 CLI 帮助](COMMANDS.md)、[配置 help](../../runtime/configuration/HELP.md)。runtime.api.command_help/read_support 仍可供 Python 调用方使用。

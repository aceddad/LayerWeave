# 内部工具 · 帮助包

本包提供命令展示与封装支持查询。可以独立增减；其他工具的 --help 直接复用基础支撑，不依赖本包。

[MCP 接入](https://gitee.com/emotion1354414/layer-weave/blob/visualization/src/layerweave/tool/builtin/shared/mcp/README.md)提供分层能力目录、JSON 调用与 direct/routed。命令参数来自同一份 input_schema，技能和插件帮助按需读取；本包继续提供独立的 CLI 与配置支持查询。

| 文件 | 作用 |
|---|---|
| command_help.py | 命令总览和多目标详情的文字/JSON 入口 |
| config_help.py | 封装使用帮助与开发帮助的文字/JSON 入口 |
| catalog.py、help_data.py | 动态发现层/对象配置、组织用途、参数、继承说明与示例 |

```sh
python -X utf8 -m layerweave.tool.builtin.shared.help.command_help
python -X utf8 -m layerweave.tool.builtin.shared.help.command_help split insert_gap undo --json
python -X utf8 -m layerweave.tool.builtin.shared.help.config_help combined text
python -X utf8 -m layerweave.tool.builtin.shared.help.config_help objects model --dev
```

完成可编辑安装即可调用，无需数据库。静态命令数据由 layerweave.support.commands.command_help 提供；配置数据由本包 catalog.read_support 提供。完整说明见[命令](COMMANDS.md)与[配置 help](CONFIG_HELP.md)。

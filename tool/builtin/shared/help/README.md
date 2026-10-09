# 内部工具 · 帮助包

本包提供命令展示与封装支持查询。可以独立增减；其他工具的 --help 直接复用基础支撑，不依赖本包。

| 文件 | 作用 |
|---|---|
| command_help.py | 命令总览和多目标详情的文字/JSON 入口 |
| config_help.py | 封装使用帮助与开发帮助的文字/JSON 入口 |
| catalog.py、help_data.py | 动态发现层/对象配置、组织用途、参数、继承说明与示例 |

```sh
python -m tool.builtin.shared.help.command_help
python -m tool.builtin.shared.help.command_help split insert_gap undo --json
python -m tool.builtin.shared.help.config_help combined text
python -m tool.builtin.shared.help.config_help objects model --dev
```

完成可编辑安装即可调用，无需数据库。静态命令数据由 support.commands.command_help 提供；配置数据由本包 catalog.read_support 提供。完整说明见[命令](COMMANDS.md)与[配置 help](CONFIG_HELP.md)。

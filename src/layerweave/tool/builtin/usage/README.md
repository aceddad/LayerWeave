# 内部工具 · 使用工具

本页供 AI 或程序使用现成工具操作项目内容，支持 Python、CLI 和可选 [MCP](../shared/mcp/README.md) 调用。开发自己的工具见[扩展指南](../../../../../docs/build-with-layerweave/README.md)，修改 LayerWeave 本身见[源码开发指南](../../../../../docs/developer-conventions.md)。[返回内部工具](../README.md)。

## 从当前任务开始

不熟悉已有项目时，可用 project_overview 查看层树和对象数量，再按需要用 project_details 展开，或用 find_objects 定位。目标和编号已明确时，可以直接定向读取或操作，不必每次重读整个项目。

```sh
python -X utf8 -m layerweave.tool.builtin.usage.query.project_overview DATABASE PROJECT_ID
```

DATABASE/PROJECT_ID 使用实际数据库路径和项目编号。命令 help 可用 overview 别名查这项能力。

- **选择读取范围**：按层、对象或区间读取当前需要的内容；项目概览用于理解结构，详细展开用于取得正文。
- **查询支持能力**：不知道用哪个工具时查询命令 help；不确定某种层或对象的用途、内容字段和示例时查询配置 help，无需翻阅 TOML 或源码。
- **更新已有内容**：需要保留对象身份、关联和批注时，更新原对象；重复同步可用按名字或稳定键匹配的工具。大量修改可使用 JSON 交换，具体范围与冲突行为见对应说明。
- **阅读反馈**：先看 operation/ok 确认本次写入，再读 checks 中的诊断。诊断出现 error 不代表写入失败，不据此重复 create。需要复查或追溯时再使用验证、历史和撤销工具。
- **结合用户画面**：用户说“这里”或提供视图链接时，按需读取 view_state、view_at、批注或截图，见[视图协作](../view/GUIDE.md#给-ai-用)。

这些路径按任务选用；详细参数、默认范围和返回含义以当前 help 为准。

## 按操作查说明

| 要做什么 | 详细说明 |
|---|---|
| 创建、读取、修改、删除，或发送一批请求 | [CRUD 请求与反馈协议](CRUD.md) |
| JSON 导入导出、直接套用场景模板 | [交换工具](exchange/README.md) |
| 看项目、查对象、查关联、汇集文字 | [使用手册](GUIDE.md) |
| 按名字或稳定键更新对象，保留原编号 | [匹配更新](GUIDE.md#匹配更新或创建) |
| 沿关联展开相关内容 | [关联展开](GUIDE.md#沿关联展开) |
| 接续新增、排列、对齐、修改时长、复制对象 | [使用手册](GUIDE.md) |
| 查找空档 | [使用手册](GUIDE.md#空档查询) |
| 平移、分割、插空档、跨项目复制或剪切 | [编辑说明](EDITING.md) |
| 复制或删除整棵子树 | [子树说明](SUBTREES.md) |
| 复查、历史、撤销或重做 | [历史与恢复](HISTORY.md) |
| 查询工具和可用封装 | [共用 help](../shared/help/README.md) |

## 命令行编码

中文 Windows 的 Python 在输出重定向到管道时可能使用 GBK，而 AI 调用工具通常按 UTF-8 读取。请按文档和 help 的示例显式使用 `python -X utf8 ...`；`-X utf8` 放在 `-m` 或脚本文件之前。普通 help、概览、JSON 输出、错误消息及 MCP 启动入口的 `--list` 都适用。

也可以为启动 Python 的环境设置 `PYTHONUTF8=1`。例如 PowerShell 中的同一次调用：

```powershell
$env:PYTHONUTF8 = "1"
layerweave-mcp --list
```

Bash 中可只为这一条命令设置：

```sh
PYTHONUTF8=1 layerweave-mcp --list
```

环境设置作用于对应进程及其子进程；相互独立的终端调用不一定共享设置，因此文档优先写单次命令的 `-X utf8`。读取输出的一方也需使用 UTF-8。如果显式设置了 `PYTHONIOENCODING`，它会覆盖标准流编码，需保持一致。原理见 [Python UTF-8 模式](https://docs.python.org/3.11/library/os.html#python-utf-8-mode)。

MCP 正常通信由 SDK 处理协议编码；`--list` 与 `--help` 是普通 CLI 文本输出。程序不依据“是否管道”自动改写标准流编码，也不修改系统或终端的全局设置。

## 调用起点

完成可编辑安装后运行命令 help，或查看某个命令的 --help。输入、输出和完整示例由工具自己的说明提供：

```sh
python -X utf8 -m layerweave.tool.builtin.shared.help.command_help
python -X utf8 -m layerweave.tool.builtin.shared.help.command_help project_details append_object --json
python -X utf8 -m layerweave.tool.builtin.shared.help.config_help
python -X utf8 -m layerweave.tool.builtin.shared.help.config_help combined text
```

Python 公共读写接口见 [API](../../../support/API.md)。实际执行例子见[示例索引](../../../../../docs/examples.md)。写入结果与检测反馈需要分别阅读，格式由 CRUD 协议统一说明。

命令 help 展示实际发现的工具；配置 help 展示当前层和对象声明。普通使用保持默认模式；编写封装才按需查询 `config_help --dev`。本页只选择入口，不另行维护参数或支持类型的副本。

## 代码位置

- [records/](records)：CDUR 请求协议和默认实例保存。
- [exchange/](exchange/README.md)：分层 JSON 交换、工具表数据、编号映射和场景模板。
- [query/](query)：概览、展开、对象、关联与空档查询。
- [editing/](editing)：位置、对象、子树、分割、插空档和迁移。
- [history/](history) 与 [undo/](undo)：历史展示与撤销规划，各自独立。
- [validation/](validation/README.md)：内容检查及复查。
- [text/](text)：文字内容工具，当前为文本汇集。

本页负责选择入口；详细参数、返回与边界放在相应手册中。

# 命令目录与命令行帮助

静态说明入口是 `layerweave.support.commands.command_help`。它列出内部工具、基础 CRUD 分流和开发工具命令，或按名称展开说明；不会执行命令，也不需要数据库。可选 [MCP](../mcp/README.md) 复用同源 Schema 与声明，按分类提供帮助并执行已登记的动作。

```python
from layerweave.support.commands import command_help

overview = command_help()
details = command_help(["split", "insert_gap", "undo"])
```

```sh
# 完成可编辑安装后运行。
python -X utf8 -B -m layerweave.tool.builtin.shared.help.command_help
python -X utf8 -B -m layerweave.tool.builtin.shared.help.command_help split insert_gap undo --json
python -X utf8 -B -m layerweave.tool.builtin.usage.editing.gaps --help
python -X utf8 -B -m layerweave.tool.builtin.usage.editing.split --help
```

read_only 是命令级的粗粒度说明：会修改业务数据或持久化设置的入口标为 false，查询与修改混合的入口也按可写标记。true 不保证没有输出文件、缓存或临时资源；生成截图、导出文件等行为需同时读用途与参数说明，不直接把该字段当作 MCP 的完整副作用描述。

CLI 总览有 name、summary、read_only 和可选 cli。详情包含 input_schema、由它派生的 parameters 展示、可选 Python entrypoint、返回说明、notes、examples 与 source。可组合写工具另有 session_entrypoint，指向接受 write 的事务内入口。参数以标准 JSON Schema 维护，展示会派生是否必需和 choices/default。示例中的 files 是完整 JSON 值；MCP 示例参数可放 examples.arguments，不要求有 CLI。

名称支持规范命令名、别名或完整 Python 入口，比如 split、split_object、layerweave.tool.builtin.usage.editing.timeline:split_object。重复指向同一命令的查询去重，names=[] 返回空列表。名称不明或有歧义时给出问题和候选，其他目标继续；有歧义时可以用不同的完整 entrypoint 区分。

返回 view、status、items、issues。completed 表示说明读取完成，partial 表示部分声明或目标不可用。说明不验证命令的业务执行结果。CLI 查询失败或源目录错误返回失败，部分目标不可用仍返回有效部分。

事务内入口的返回是业务数据，不含独立提交反馈，完整约定见[组合开发指导](../../../../../../docs/build-with-layerweave/04-composing-tools.md)。

## 同一份说明用于目录与 CLI

各工具在自己的 Python 文件中放置字面量 COMMANDS 列表，使用普通赋值，且放在执行 main 的语句之前。统一目录按文件递归发现，无需修改中央命令名单；下次查询重新读取。目录只使用 AST 读取字面量，不导入被发现的工具模块。

使用工具位于 src/layerweave/tool/builtin/usage，开发工具位于 developer，共用 help 位于 shared/help；视图命令位于 view。每个命令的 Schema 在自身声明处维护一次；MCP 的 route/exposure 与函数适配也随包声明。通过 discover_commands(sources=...) 可合并开发来源与已安装的 layerweave.tools entry points，发现不会导入模块。旧 command_help 的 source_root 仍表示替换一次查询的扫描范围。

`layerweave.support.cli.parser_for(..., commands=COMMANDS)` 将同一份 examples/notes 放进根级 --help。使用独立 argparse 的入口通过 layerweave.support.commands.help_examples 复用它。split 和 gaps 的关键参数 help 也直接引用参数描述。

最小声明示意：

```python
COMMANDS = [{
    "name": "example_tool",
    "summary": "说明这个工具处理什么",
    "entrypoint": "layerweave.tool.builtin.usage.custom.example:example_tool",
    "cli": "python -m layerweave.tool.builtin.usage.custom.example",
    "read_only": True,
    "context": ["database", "project_id"],
    "input_schema": {"type": "object", "properties": {
        "database": {"type": "string", "description": "数据库路径"},
        "project_id": {"type": "integer", "description": "项目编号"},
        "object_id": {"type": "integer", "description": "项目内对象编号"}
    }, "required": ["database", "project_id", "object_id"], "additionalProperties": False},
    "mcp": {"route": "query", "group": "query", "database": "connection"},
    "returns": "返回对象说明",
    "examples": [{"cli": "python -m layerweave.tool.builtin.usage.custom.example DATABASE 1 8"}]
}]
```

这里只示范声明格式，实际可调用工具需提供对应函数；CLI 可省略。context 描述可补的上下文，标准 input_schema 明确声明其字段。旧 parameters 格式仍可读取并转换，新增声明使用 input_schema。mcp.database=connection 时适配器打开连接传给首参，路径型入口用 path；checker 等 Python 回调不作为 JSON 参数。

命令目录本身始终只读。MCP 在启动时生成绑定与独立入口，调用时才导入已登记函数；没有 mcp 声明的条目只展示说明。input_schema 约束调用参数，不复制 TOML 内容约束。具体启用范围、名称、变体与 SDK 启动见 [MCP 接入](../mcp/README.md)。

有 CLI 的命令使用 cli_mapping 显式记录 Schema 参数到 argparse dest 的映射，例如 cuts/first_information 都来自 data_file；cli_only 列出 json/text 等只属于命令行的选项。参数同名时无需重复映射。对应测试同时核对两端，新增参数若没有对应或专用说明会失败；没有 CLI 的工具不受此项约束。

## 参数与业务说明的维护位置

COMMANDS 可选 keywords 字符串列表与 help_order 整数，例如概览声明 keywords=["概览", "总览", "项目结构"]、help_order=10。MCP 搜索匹配身份、摘要、别名和关键词；关键词不注册为调用别名。同类中显式顺序较小者优先，同值按完整身份排序，未填写的排在其后。总览 common 展示可用条目的前三个，表示推荐入口；禁用与 direct 暴露独立决定。MCP 变体可自行覆盖顺序和关键词。

每条 examples.arguments 独立表示一次 MCP 调用，可附 title；所有这类示例都会展示并按 Schema 核对。只带 cli/files 的例子继续用于 CLI，不猜测转换。专用变体可声明自己的 examples 和 properties，避免把其他动作的参数说明套给回复等入口。显式示例优先；继承通用示例的投影只移除该入口不接收的字段，不混入前一条示例的参数。

结果含多个列表时，工具在 mcp.pagination 中声明 items 的字段路径，按需声明已有业务 next_cursor 的路径；有效声明也在使用 help 展示。回复 limit 与命令 arguments.limit、回复 more.cursor 与业务下一批游标的区别，统一见[MCP 返回与续取](../mcp/README.md#返回与续取)。声明只组织输出，不改变业务查询或再次执行命令。

当前命令参数、默认值、JSON 文件示例以实时 command_help 和各工具 --help 为准，直接读取工具自己的 COMMANDS。本文维护发现方式与开发约定，不再复制各工具参数表。

业务含义与边界仍由专题解释。例如 split/keep/stretch/move 的选择和插空档范围见[范围编辑](../../usage/EDITING.md)，数据库的 operation.status 与 checks 分工见[反馈协议](../../usage/CRUD.md#操作与检测的反馈)。配置 help 的使用/开发两种阅读方式见[配置 help](CONFIG_HELP.md)。

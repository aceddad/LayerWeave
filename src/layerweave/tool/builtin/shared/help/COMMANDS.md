# 命令目录与命令行帮助

统一入口是 `layerweave.support.commands.command_help`。它列出内部工具、基础 CRUD 分流和开发工具命令，或按名称展开说明；不会执行命令，也不需要数据库。

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

总览只有 name、summary、read_only 和 cli 模块入口。详情还包括 Python entrypoint、参数说明、返回说明、notes、examples 和声明所在 source。可组合写工具另有 session_entrypoint，指向接受 write 的 Python 事务内入口；不增加命令，也不改变 CLI。参数含类型、用途、是否必需，以及适用的 choices/default。示例中的 files 直接保存可解析的 JSON 值；文件最外层的字典或列表不会用省略号代替。

名称支持规范命令名、别名或完整 Python 入口，比如 split、split_object、layerweave.tool.builtin.usage.editing.timeline:split_object。重复指向同一命令的查询去重，names=[] 返回空列表。名称不明或有歧义时给出问题和候选，其他目标继续；有歧义时可以用不同的完整 entrypoint 区分。

返回 view、status、items、issues。completed 表示说明读取完成，partial 表示部分声明或目标不可用。说明不验证命令的业务执行结果。CLI 查询失败或源目录错误返回失败，部分目标不可用仍返回有效部分。

事务内入口的返回是业务数据，不含独立提交反馈，完整约定见[组合开发指导](../../../../../../docs/build-with-layerweave/04-composing-tools.md)。

## 同一份说明用于目录与 CLI

各工具在自己的 Python 文件中放置字面量 COMMANDS 列表，使用普通赋值，且放在执行 main 的语句之前。统一目录按文件递归发现，无需修改中央命令名单；下次查询重新读取。目录只使用 AST 读取字面量，不导入被发现的工具模块。

使用工具位于 src/layerweave/tool/builtin/usage，开发工具位于 src/layerweave/tool/builtin/developer，共用 help 位于 src/layerweave/tool/builtin/shared/help；view 目前没有命令。目录分类见[内部工具导航](../../README.md)。每个命令只在实现模块声明一次，help 的进一步编排留到 MCP 阶段讨论。

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
    "parameters": {
        "object_id": {"type": "integer", "required": True, "description": "项目内对象编号"}
    },
    "returns": "返回对象说明",
    "examples": [{"cli": "python -m layerweave.tool.builtin.usage.custom.example DATABASE 1 8"}]
}]
```

这里只示范说明格式，实际工具仍需有对应函数和 CLI。context 中的 database/project_id 由目录补入共用参数说明；无数据库的 help 类工具使用空列表。Python 业务接口使用已打开的 connection，database 是 CLI 及未来适配器的连接上下文，不是直接传给 Python 函数的同名参数。checker 等 Python 回调由开发 API 文档说明，不作为普通 JSON 命令参数。

未来 MCP 可以复用这个只读目录进行展示和适配。当前没有新增 MCP 服务，也没有根据字符串名称自动执行 Python 函数；parameters 是接口说明数据，不是完整的 MCP 工具注册协议。

## 参数与业务说明的维护位置

当前命令参数、默认值、JSON 文件示例以实时 command_help 和各工具 --help 为准，直接读取工具自己的 COMMANDS。本文维护发现方式与开发约定，不再复制各工具参数表。

业务含义与边界仍由专题解释。例如 split/keep/stretch/move 的选择和插空档范围见[范围编辑](../../usage/EDITING.md)，数据库的 operation.status 与 checks 分工见[反馈协议](../../usage/CRUD.md#操作与检测的反馈)。配置 help 的使用/开发两种阅读方式见[配置 help](CONFIG_HELP.md)。

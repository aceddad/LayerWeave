# 命令目录与命令行帮助

统一入口是 `runtime.api.command_help`。它列出内部工具、基础 CRUD 分流和数据库初始化命令，或按名称展开说明；不会执行命令，也不需要数据库。

```python
from runtime.api import command_help

overview = command_help()
details = command_help(["split", "insert_gap", "undo"])
```

```sh
# 从 src 运行。
python -X utf8 -B -m tools.common.command_help
python -X utf8 -B -m tools.common.command_help split insert_gap undo --json
python -X utf8 -B -m tools.common.gaps --help
python -X utf8 -B -m tools.common.split --help
```

总览只有 name、summary、read_only 和 cli 模块入口。详情还包括 Python entrypoint、参数说明、返回说明、notes、examples 和声明所在 source。参数含类型、用途、是否必需，以及适用的 choices/default。示例中的 files 直接保存可解析的 JSON 值；文件最外层的字典或列表不会用省略号代替。

名称支持规范命令名、别名或完整 Python 入口，比如 split、split_object、runtime.api:split_object。重复指向同一命令的查询去重，names=[] 返回空列表。名称不明或有歧义时给出问题和候选，其他目标继续；有歧义时可以用不同的完整 entrypoint 区分。

返回 view、status、items、issues。completed 表示说明读取完成，partial 表示部分声明或目标不可用。说明不验证命令的业务执行结果。CLI 查询失败或源目录错误返回失败，部分目标不可用仍返回有效部分。

## 同一份说明用于目录与 CLI

各工具在自己的 Python 文件中放置字面量 COMMANDS 列表，使用普通赋值，且放在执行 main 的语句之前。统一目录按文件递归发现，无需修改中央命令名单；下次查询重新读取。目录只使用 AST 读取字面量，不导入被发现的工具模块。

`tools._cli.parser_for(..., commands=COMMANDS)` 将同一份 examples/notes 放进根级 --help。使用独立 argparse 的入口通过 tools.catalog.help_examples 复用它。split 和 gaps 的关键参数 help 也直接引用参数描述。

最小声明示意：

```python
COMMANDS = [{
    "name": "example_tool",
    "summary": "说明这个工具处理什么",
    "entrypoint": "tools.custom.example:example_tool",
    "cli": "python -m tools.custom.example",
    "read_only": True,
    "context": ["database", "project_id"],
    "parameters": {
        "object_id": {"type": "integer", "required": True, "description": "项目内对象编号"}
    },
    "returns": "返回对象说明",
    "examples": [{"cli": "python -m tools.custom.example DATABASE 1 8"}]
}]
```

这里只示范说明格式，实际工具仍需有对应函数和 CLI。context 中的 database/project_id 由目录补入共用参数说明；无数据库的 help 类工具使用空列表。Python 业务接口使用已打开的 connection，database 是 CLI 及未来适配器的连接上下文，不是直接传给 Python 函数的同名参数。checker 等 Python 回调由开发 API 文档说明，不作为普通 JSON 命令参数。

未来 MCP 可以复用这个只读目录进行展示和适配。当前没有新增 MCP 服务，也没有根据字符串名称自动执行 Python 函数；parameters 是接口说明数据，不是完整的 MCP 工具注册协议。

## 插空档调用变化

明确选择 --layer-id、--layer-ids、--project 之一；Python 对应 layer_id、layer_ids、whole_project=True。直属层不包含子层，子树包括所有后代，省略范围会报错。

```json
[
  {"object_id": 8, "action": "split", "first_information": {"text": "前段"}, "second_information": {"text": "后段"}},
  {"object_id": 9, "action": "keep"},
  {"object_id": 10, "action": "stretch"},
  {"object_id": 11, "action": "move"}
]
```

这是 --contents-file 的完整列表格式，Python 参数为 crossing_actions。split 需要两段内容；keep 原样保留；stretch 只让终点后移；move 让起终点一起后移，使用本层实际插入长度。这三项不需要重新提供 information，不改编号或关联，不处理媒体内容。未写 action、但明确给出两段内容的旧文件仍按 split 兼容。旧 split_contents 参数仍可用，但不能与 crossing_actions 同传。

缺少跨界处理时，required_crossings 列出需要决定的对象，allowed 为 split/keep/stretch/move；required_splits 暂保留为同一列表的兼容别名。未命中的处理项列入 unused_object_ids。data.kept/stretched/moved 分别列出三种跨界处理结果，data.shifted 仍为自动后移对象；data.gaps 描述插入位置和长度，不承诺整个区间无对象。

# MCP 接入

以标准 stdio MCP 调用现有工具。help 按需展开，JSON 直接读写，常用工具或技能说明可独立暴露；视图和其他工具使用相同绑定规则。

## 安装与启动

在源码仓库的虚拟环境中安装可选依赖：

```sh
python -m pip install -e ".[mcp]"
python -m layerweave.tool.builtin.shared.mcp --config mcp.json
```

安装后也可运行 `layerweave-mcp --config mcp.json`。本地 wheel 可用 `python -m pip install "路径/layerweave-0.7.3-py3-none-any.whl[mcp]"`。基础 Python/CLI 不需要 MCP SDK；本服务使用官方 MCP Python SDK 2.3 系列兼容接口。

标准输出是协议流，日志在标准错误；这不是交互式命令行。`--list` 只输出有效动作、实际 direct 名称和声明问题。最小配置是 `{}`；[example.json](example.json) 提供可编辑示例：

```json
{
  "workspace": ".",
  "database": "project.sqlite3",
  "project_id": 1,
  "exposure": {"layerweave.project_overview": "direct"},
  "disabled": []
}
```

数据库和编号替换为实际值。没有默认库仍可读 help；新库通过 admin 的 layerweave.initialize_database 创建。workspace 相对于配置文件目录，其后的相对文件参数按 workspace 解析；未提供配置时使用启动目录。

MCP 客户端配置示意，解释器与文件使用实际绝对路径：

```json
{
  "mcpServers": {
    "layerweave": {
      "command": "D:/my-project/.venv/Scripts/python.exe",
      "args": ["-m", "layerweave.tool.builtin.shared.mcp", "--config", "D:/my-project/mcp.json"]
    }
  }
}
```

## 发现与调用

总览的 common 是声明推荐的入口，不是使用次数统计。查看项目优先展示 project_overview；搜索“概览／总览”可以找到它，搜索“修改／更新”可以找到 dispatch。关键词不自动成为调用别名。详情显示工具声明的多个示例，编号与路径换成实际值。

dispatch 的单项请求结构直接在 Schema 展示，每条 layer/object 或有项目归属的工具表请求自行填写 project_id；启动默认项目不会补入 request。创建 project 不需要 project_id。update 只修改传入字段，information 等 JSON 字段整体替换。

| 工具 | 用途 |
|---|---|
| layerweave_help | 默认给分类；names/search/group 展开，topic 支持 commands/configs/skills/plugins/context |
| layerweave_query | 查询、JSON 导出、看图、材料读取；cursor 续取已生成结果 |
| layerweave_edit | 项目写入、JSON 导入、批量 CRUD、撤销 |
| layerweave_admin | 初始化库、安装、配置、明确的文件输出 |

查询帮助：

```json
{"topic": "commands", "names": ["layerweave.split_object", "layerweave.insert_gap"]}
```

query 调用示意：

```json
{"command": "layerweave.project_overview", "arguments": {"database": "project.sqlite3", "project_id": 1}}
```

edit 直接批量写入示意，数组在同一事务执行；编号替换为实际值：

```json
{
  "command": "layerweave.dispatch",
  "arguments": {
    "database": "project.sqlite3",
    "request": [
      {"action": "update", "kind": "object", "project_id": 1, "id": 8, "data": {"name": "开场"}},
      {"action": "update", "kind": "object", "project_id": 1, "id": 9, "data": {"tips": "待检查"}}
    ]
  }
}
```

export_project 直接返回交换文档，import_project 的 document 直接接收 JSON 对象；无需先导出或生成文件。分割、插空档、按键同步也直接传对象/数组。具体参数与完整示例以实时 help 为准，路径、编号和素材需换成实际上下文。

文件只是可选包装：export_project_file 经 admin 保存 JSON，默认不覆盖，overwrite=true 明确覆盖；import_project_file 经 edit 读取 document_file。两者继续调用同一业务函数。

## 配置与暴露

| 配置字段 | 含义 |
|---|---|
| workspace、database、project_id | 可选默认上下文；换库不沿用旧项目编号 |
| groups.enable、groups.disable | 选用/禁用分组，省略 enable 表示不限制分组 |
| exposure | 完整身份到 direct/routed 的映射 |
| disabled | 禁用完整命令身份，两条调用路径都不可用 |
| sources | 开发来源，含 namespace/path 和按需提供的 import_root |
| installed、include_builtin | 发现已安装 entry points / 包内命令，默认 true |
| skills_roots | 替换技能扫描目录；省略用自带 skills，空列表不扫描 |
| limit、max_chars | 默认回复每页项数和 JSON 回复体字符预算，默认 100、24000；不替命令填写 arguments.limit |
| result_cache_size | 内存中保留的续取结果数量，默认 32 |

禁用优先；direct 不重新启用能力。配置与来源在启动时加载，改动后重启。独立名称默认将完整身份的点号/连字符换成下划线；声明可用 mcp.name 自定义。名称冲突报告来源，不覆盖；只有独立名称冲突时仍可通过完整身份 routed 调用。

direct 是暴露方式，不保证客户端置顶，不改变权限。客户端允许通用 edit 时，其授权范围可能包含全部已启用写动作。help 显示实际可用、禁用和仅有说明的条目。

默认项目只补到声明允许的位置：import_project 保留文档的项目/新建语义，dispatch 保留 request 中的显式项目。结果 context 给出实际路径和范围。config_ref、技能 route 和 information 内的资源字符串不统一改写。

## 技能与视图

MCP 新建批注与回复要求非空 author，专用 view_reply 和通用 view_note 的 add/reply 使用同一检查。作者与 waiting 使用同一标签，例如先查 waiting="Claude"，再以 author="Claude" 回复；不自动推断身份，不自动标已读或已处理。Python/CLI 仍可保存未署名内容。

view_reply 的 note_id 是被回复的批注编号，text 只表示回复正文。有默认库与项目时，传给 layerweave_view_reply 的示例（编号替换为收件箱返回值）：

```json
{"note_id": 41, "text": "已调整这一段。", "author": "Claude"}
```

`{"topic":"skills"}` 列出身份，指定 names 读取正文；支持文本文件可用 resource 指定技能内相对路径。将该身份设为 direct，会产生只读材料入口，不执行脚本。例如自带文本整理技能为 `skill.layerweave.layers.text.text-normalize`，独立名默认 `skill_layerweave_layers_text_text_normalize`。自定义材料使用 help 返回的身份。

视图包推荐 view_inbox、view_reply、view_screenshot 为 direct。看图不接收 output，直接返回图片；view_screenshot_save 明确接收 output，经 admin 排他创建。query 不自动标记批注已读，视图未安装不影响其他工具。

截图需 Chrome、Edge 或 Chromium。timeout_ms 默认 60000，是启动至抓图预算；wait_ms 默认 20000，是页面绘制等待。关闭阶段另有短暂清理时间，客户端请求超时宜更长。截图不改项目和用户视图状态，但可能生成缩略图/波形缓存；state_root 可隔离设置、插件和缓存。params 直接传插件参数对象，复用原解释规则。view_server、view_bench 保留 CLI 指引，不经 MCP 再启动服务或开发测量。

## 返回与续取

局部导出默认只带实际涉及的工具表及其定义依赖；完整项目保留空表结构。原库编辑或目标库已有所需表声明时，可传 compact=true，省略 tables/source_numbering；业务记录、关联和请求的 baseline 保留。include_tools 另行控制是否收集工具数据。直接 JSON、文件和 CLI 使用同一规则，见[交换说明](../../usage/exchange/README.md)。

只读失败及执行前的参数/路由错误不附写入重试提醒。写动作已进入业务执行但无法确认结果时才提示核对；已明确提交而返回整理失败时保留操作编号和提交状态。

普通返回含 context、result、result_complete。先看 result.operation.status，再看 result.checks：committed 加检查 error 仍是已提交；导入的 data.status=partial 表示有跳过，不代表提交失败。

已提交且有可撤销业务记录时给出 undo 调用。视图旧入口只给 operation_id 时，适配器读取该操作的日志补充反馈。文件、KEY、安装、表结构准备不虚构内容撤销能力。

查询数量与回复分页分开。以历史为例，`arguments.limit=3` 查询最近三次操作；外层 `limit=3` 将本次已经查到的结果每三项展示，不修改命令自己的默认查询数量。独立工具入口中的 limit 就是该命令的参数；默认回复预算仍来自启动配置。full=true 只绕过回复预算，不扩大查询范围。

最近三次操作，传给 layerweave_query 的示例（项目编号换成实际值）：

```json
{"command":"layerweave.read_history","arguments":{"project_id":1,"limit":3}}
```

分页优先使用工具声明的主列表，例如历史的 items、详细展开的 layers。未声明时只选择唯一最外层列表；同层多个列表不猜主次，也不进入某项内部寻找更长的列表。未能确定主列表时不按项数拆分，超出 max_chars 才以整个结果的 JSON 文本分段。单个业务项过大也用明确片段处理，历史的 changes 不会被伪装成完整操作而部分返回。

more.cursor 续取本次已生成的回复，向 query 只传 `{"cursor":"返回的游标"}`；不重做命令，沿用首次回复预算。业务 next_cursor 用来查询下一批，例如历史将它传给 arguments.before，两种游标不能互换。声明了业务游标的命令，在回复尚未续取完时将该字段暂置 null，并给 more.business_cursor_pending=true 与 business_cursor_path；读完后恢复原值。null 加 pending=true 不代表业务已到末尾。若回复为整体 JSON 片段，需在所有片段结束后还原文档，再读取其中的业务游标。

文本片段以 json_text 标明并按 offset 拼接；result_complete=false 的局部页或片段不能整体写回。more.unit 区分项数和字符数。业务数据变化时提示 cursor_stale；文件、材料等从同次结果快照续取。

完整交换文档只按字符预算判断过大，忽略外层项数 limit；超出时返回 result_too_large，不截断、不自动保存。可缩小范围、明确 full=true，或选文件输出。预算不减少已执行操作；JSON 包装、图片数据和客户端 token 消耗并不等同。

缓存只在当前服务内有效，重启或淘汰后提示 cursor_expired。写入结果失效、取消或超时后先核对历史和目标，不自动重做。服务日志记录请求、命令、操作编号和状态，不打印调用参数或密钥。

## 扩展一个无 CLI 的工具

COMMANDS 可选 keywords（字符串列表）与 help_order（整数，较小优先），见[命令声明](../help/COMMANDS.md)。MCP 变体可覆盖 keywords/help_order、properties、notes 和 examples。变体默认不继承主体的推荐顺序；不填写时排在显式推荐项之后。

可选 mcp.open_world 为布尔值，省略为 true；direct 入口从绑定生成标准 openWorldHint，routed 的详情显示同一声明。false 表示该能力在声明的封闭范围内工作，不代表是否写入或获准调用。一份绑定包含多个动作时须覆盖全部动作，不自动推断。自带技能材料读取、视图收件箱与回复为 false；截图、通用 help/query 保持 true，因为插件页面、详情、市场或外部扩展可能联网。该字段不改变授权和启用规则。

工具可用 mcp.pagination 声明分页主列表，字段路径相对于业务 result，用字符串列表表示；items=[] 表示结果本身是列表。例如历史声明 `{"items":["items"],"next_cursor":["next_cursor"]}`。next_cursor 可省略，只在工具自身已有下一批游标时填写；MCP 不发明业务游标、不自动发起下一次查询。嵌套包装可写 items=["data","rows"]。声明路径未命中列表时按整体结果处理，不猜其他字段；变体可覆盖 pagination，设为 null 恢复自动选择。详情 help 会展示有效分页声明。

在 alice_tools/commands.py 定义：

```python
def echo(text):
    return {"text": text}

COMMANDS = [{
    "name": "echo",
    "summary": "返回给出的文本",
    "entrypoint": "alice_tools.commands:echo",
    "read_only": True,
    "input_schema": {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False
    },
    "mcp": {"route": "query", "group": "text", "exposure": "direct"}
}]
```

开发配置 sources 加入 `{"namespace":"alice","path":"extensions/alice_tools/commands.py","import_root":"extensions"}`。完整命令是 alice.echo，默认独立名 alice_echo。COMMANDS 使用字面量；发现时不导入业务模块。

安装包的 pyproject.toml 可声明：

```toml
[project.entry-points."layerweave.tools"]
alice = "alice_tools.commands:COMMANDS"
```

静态读取安装元数据和声明文件。可编辑安装依靠导入钩子而定位不到时，会明确报告并提示 sources，不执行模块兜底。实际调用才导入函数。

普通函数接收 Schema 字段；需要连接的函数声明 mcp.database="connection"，Schema 使用 database 字符串，适配器打开连接并作为首参传入。直接接收路径用 mcp.database="path"。文件参数列在 mcp.paths，路径数组列在 path_arrays，只有这些字段会解析为绝对路径。回调和写会话不进入 JSON，业务写入仍走公共事务接口。

按动作变化的文件字段可用 action_paths，例如插件 add 的 target；同时接受 HTTP(S) URL 与本地文件的字段用 uri_paths，例如 catalog，URL 保留原值。层编号 root、ZIP 内部 source_dir 等逻辑值不作为文件系统路径处理。

混合动作可声明 route_by="action"、action_routes；实际函数适配可用 mcp.handler。每个动作继续维护自己的输入、返回和效果。内容约束不移入调用 Schema。

Python 内嵌入口是 `from layerweave.tool.builtin.shared.mcp import create_runtime, create_server`；前者提供同一目录与调用适配，后者返回官方 SDK 服务器。协议包可卸载，core/support 不依赖 SDK。

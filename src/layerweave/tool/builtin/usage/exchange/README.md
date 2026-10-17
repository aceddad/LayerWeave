# JSON 导入导出与模板

AI 可以导出所需范围，修改 JSON，再一次导入；无需为每次操作编写 Python。没有 op 的节点只提供上下文，已有记录以 ID 定位，新增记录按目标库规则发号。完整字段见 [FORMAT](FORMAT.md)，扩充方式见 [DEVELOPMENT](DEVELOPMENT.md)。

## 先看模板，再创建

从已安装 LayerWeave 的 Python 环境运行。DATABASE 是实际数据库路径；输出文件位置由 AI 按项目安排。

~~~sh
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli templates
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli templates storyboard
python -X utf8 -m layerweave.tool.builtin.developer.database.cli DATABASE
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply DATABASE --template storyboard --new-project --result-file result.json
~~~

已有数据库省略初始化一步。模板总览只给名称、用途和路径；按名称查询才读取完整正文。apply 默认给简短计数与逐条警告，--result-file 保存包括编号映射的完整反馈，--json 则打印完整反馈。

| 随包模板 | 用途 |
|---|---|
| [subtitles](templates/subtitles.json) | 字幕文字层与一条可替换的字幕 |
| [storyboard](templates/storyboard.json) | 分镜、参考图两个 root，以及跨根引用 |
| [hand-drawn-video](templates/hand-drawn-video.json) | 含义、图片、视频、资源四个独立 root 的手书结构 |

模板都是普通 JSON 操作文件。用 --template-root 替换模板目录，或直接用 --data-file 读取任何工作目录中的 JSON。个人文件不必放进安装包；随包模板作为起始示例，复制到工作目录再修改即可。

## 导出、修改、写回

~~~sh
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli export DATABASE PROJECT_ID --output project.json
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply DATABASE --data-file project.json --result-file result.json
~~~

导出默认 op=update；真实编号仍保留。修改某个节点 data 后导入，更新该记录提供的字段。删掉文件中的某个节点只表示本次不处理它；要删除数据库记录必须明确写 op=delete。information 仍整体替换。

不必每次导出整个项目：

~~~sh
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli export DATABASE PROJECT_ID --layer-ids 4 7 --output selected.json
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli export DATABASE PROJECT_ID --object-ids 8 12 --include-baseline --output selected.json
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli export DATABASE PROJECT_ID --layer-ids 4 --begin 10 --end 20 --output window.json
~~~

编号只是语法示意，实际使用查询返回的编号。导出写文件，只在终端返回路径、数量与范围；已有的概览、详细展开和对象查询仍用于交互阅读。时间范围不换算轴单位；用于 update/delete 的时间筛选中，层只作为上下文，不随命中的几个对象一起删除。

--include-baseline 可附原状态摘要；数据库内容与导出时不同的节点会跳过并报告，层节点跳过时下级也跳过。没有摘要则普通覆盖；明确允许覆盖旧文件时用 --ignore-baseline，归属检查仍然执行。

## 复制与删除

~~~sh
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli export DATABASE PROJECT_ID --op add --output copy.json
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply OTHER_DATABASE --data-file copy.json --new-project --result-file copied.json
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply DATABASE --data-file copy.json --project-id TARGET_PROJECT_ID
~~~

OTHER_DATABASE 需要先初始化。add 为自动发号表生成新身份，原 ID 只用来重建引用；provided 工具表按自身声明处理。多次执行 add 会创建多份数据，不把它当作幂等更新。

复制子树时，原父层可能在文件外面。可用 --parent-layer-id 指定目标已有层；文件外的其他引用默认令依赖项跳过，按需提供 --reference-map 或明确使用 --external-refs preserve。跨库时不要仅因数字相同就选择保留引用。

导出 --op delete 可生成显式删除文件。完整项目导出含 project.op=delete；局部导出只删除选中范围，项目本身保留。工具不补做未列出的子项删除。引用残留等数据库错误会令本批实际写入回滚；已经准备好的表结构单独保留并报告。

## 工具自有数据

完整项目默认保留工具表结构，包括空表。局部导出只带实际导出工具记录涉及的表，以及 references/logical_references 递归依赖的工具表定义；补结构不扩大业务记录范围。

原库修改或目标库已有所需表声明时，可传 compact=True（CLI --compact，MCP compact: true）。文档省略 tables/source_numbering，并标明 scope.compact=true；业务数据、关联、定位信息、计数、外部引用和请求的 baseline 都保留。include_tools 仍决定是否收集工具数据，与 compact 分开。目标缺少所需 kind 时导入明确失败，应先登记表或使用默认结构导出，不会猜测结构或静默丢记录。精简选项同时适用于 JSON 直接返回和文件输出。

默认包括本项目的 scoped 工具记录、通过声明引用关联到所选内容的工具记录，以及它们明确依赖的工具数据。与项目无归属关系的全局记录不自动全部带入；omitted_tool_records 列出未选数量，--include-global 明确带上所有全局工具记录。--no-tools 则只导出层、对象及标准关联。

附着状态可用 logical_references 声明目标，复制时随目标换号而不增加硬外键；临时状态可用 exchange.on_copy=skip 跳过旧记录复制。导出保留状态，导入逐条说明跳过原因，普通 update 不受影响。字段写法、旧库补登记与复制判定见 [FORMAT](FORMAT.md#工具表)。

导出带有工具表声明，导入默认先准备这些表，然后执行业务事务。schema.prepared_kinds 明确说明结构准备；表结构不属于操作日志与内容撤销。源发号配置以 source_numbering 作为说明保存，实际创建沿用目标库的发号平台注册；不会从 JSON 加载 Python 规则、封装或技能。

## Python 调用

~~~python
from layerweave.tool.builtin.usage.exchange import (
    export_project, import_project, load_document, save_document, template_help,
)

# connection 是已初始化连接，project_id 是已有项目。
document = export_project(connection, project_id, include_baseline=True)
save_document(document, "my-work/project.json")
result = import_project(connection, load_document("my-work/project.json"))
~~~

返回沿用 operation_id、operation、ok、applied、checks。data.status=partial 表示存在跳过，counts/items/issues 给出明细；ok=true 表示实际执行的业务批次提交成功，不代表文件中每一项都已执行。已提交部分可以按 operation_id 一次撤销。写入失败不返回可继续使用的新编号映射，已发现的跳过警告保留在 import_issues。

# LayerWeave 内部工具开发

这里保存 LayerWeave 自身的内部工具说明。工具使用普通 Python 函数与核心 API，保持非可视化运行。

## 已有工具

| 工具 | 代码 | 用途 |
|---|---|---|
| 项目概览 | [project_overview.py](../src/tools/common/project_overview.py) | 项目层级、层类型、名字与对象数量；只读 |
| 对象检索 | [find_objects.py](../src/tools/common/find_objects.py) | 按层、名字、内容、位置范围查找对象；只读 |
| 关联查询 | [relations.py](../src/tools/common/relations.py) | 查询直接引用与被引用，保留跨项目完整身份；只读 |
| 文本汇集 | [collect.py](../src/tools/text/collect.py) | 按顺序提取文字，保留来源，逐项报告不可读取的内容；只读 |

第一批四个工具已齐备，完整内存示例见 [first_batch.py](../src/examples/first_batch.py)。从 src/ 运行 `python -X utf8 -B -m examples.first_batch`，不改动真实项目数据库。

## 项目概览

```python
from tools.common.project_overview import project_overview, format_overview

# connection 使用 runtime.api.open_database 打开。
overview = project_overview(connection, project_id)
print(format_overview(overview))
```

结构化结果是一个普通字典：

- project：项目记录，包含 id、name、tips、max_id。
- counts：layers、objects、roots、unplaced_layers，分别为层总数、对象总数、根层数和未归入根层的层数。
- layers：按根层/子层顺序排列的扁平列表。每条包含 project_id、id、name、type、config_ref、father、object_count、depth。

object_count 只计本层直接装载的对象，不重复计算子层对象。depth=0 表示根，后代深度依次增加。同级按 id 排列；扁平结果方便 JSON 传输，不依赖递归嵌套。

无法从根层到达的层放在列表末尾，depth=None，原 father 保留。工具不修改父层关系，也不代替主动检测。项目不存在返回 None；存在但没有层的项目返回空列表和零计数。

核心通过 read_project_index 提供摘要，工具只负责排列与展示。一次概览使用两次 SELECT，不加载对象正文、轴数据、关联目标或配置文件，不写数据、日志，不发号；已有事务由调用方继续管理。

从 src/ 目录查看自己的项目：

```sh
python -X utf8 -B -m tools.common.project_overview ../output/ai-production.sqlite3 1
python -X utf8 -B -m tools.common.project_overview ../output/ai-production.sqlite3 1 --json
```

默认输出纯文本树，--json 输出结构化结果。项目不存在时退出码为 1；数据库路径不存在时不会创建空数据库。

不使用真实项目数据的演示：

```sh
python -X utf8 -B -m examples.project_overview
```

示例输出：

```text
项目 [1] '短片示例'
3 个层 · 3 个对象 · 2 个根层
- [1] '主线' ('text') · 2 个对象
  - [4] '配音' ('audio') · 1 个对象
- [6] '参考图' ('image') · 0 个对象
```

## 对象检索

```python
from tools.common.find_objects import find_objects

objects = find_objects(connection, project_id, layer_id=1,
                       name="开场", content="你好", begin=10, end=20)
```

- 除 project_id 外均可省略，多个条件同时满足（AND）。layer_id 仅限定该层直属对象，不递归子层。
- name 是名字中的字面子串；content 搜索 information 中的字符串值，包括嵌套字典/列表，不搜索键名，不将数字/布尔值转换为文字。两者区分大小写，`%`、`_` 不作为通配符。
- begin/end 查询对象与范围的交集：范围 [begin,end)，相等时表示占用该点的对象。只给一端可查询向前/向后的范围；两端均省略时不筛选位置。
- 首尾相接不重叠，瞬间对象占一个点。位置筛选只匹配有效数值区间；未筛位置时，原有无效区间记录仍可按其他字段找到。查询不做单位转换。
- 返回普通对象记录列表，保留 project_id、id、layer、config_ref 和 information，不装载关联。多个层先按 layer 排列，层内按 begin/end/id 排列；没有匹配时返回空列表。

```sh
python -X utf8 -B -m tools.common.find_objects ../output/ai-production.sqlite3 1 --layer-id 1 --content 你好 --begin 10 --end 20
```

命令行默认输出 JSON。结构条件在存储层使用参数化 SQL；内容匹配处理已经按结构条件筛选的 JSON 值，不打开内容引用的资源文件。

## 关联查询

```python
from tools.common.relations import query_relations

relations = query_relations(connection, project_id, "object", object_id)
```

返回 entity、direction、outgoing、incoming。entity 是查询实体的 kind/project_id/id；两个方向的列表保留完整 bind 记录及 tips。direction 可为 both（默认）、outgoing、incoming；只选一个方向时，另一列表未查询，返回空列表。

自关联在 outgoing/incoming 中各出现一次。按 kind、项目和编号共同匹配，不把其他项目的同号记录混入结果。实体或目标已删除时仍可查询保留的关联；工具不声称端点一定存在，也不自动装载或递归目标。需要存在性诊断时使用核心 validate。

```sh
python -X utf8 -B -m tools.common.relations ../output/ai-production.sqlite3 1 object 2 --direction both
```

命令行默认输出 JSON。查询直接关联只使用一次 SELECT。

## 文本汇集

```python
from tools.text.collect import collect_text

result = collect_text(connection, project_id, layer_id, separator="\n")
text = result["text"]
sources = result["items"]
```

只读取指定层的直属对象，不要求该层的名称或类型一定叫 text。根据对象配置继承链选择 text 及其派生类型；仅拥有 text 字段的基础 Object 或图片对象不会自动算作文字对象。无需导入 Python 封装类。

按 begin/end/id 顺序提取 information.text。每个 items 条目保留 project_id、id、layer、name、config_ref、begin、end、text；text 为按 separator 连接的汇集结果，默认换行。空字符串保留，文字不裁剪，不修改原对象。

可传 begin/end 使用与对象检索相同的位置范围，也可传 config_root 指定配置目录。一次调用内共享配置读取结果。

- 非文字对象、未填写可选 text 的对象会跳过，不作为错误。
- 配置缺失或文字类型错误逐条放入 issues，附 severity、target、field 和 message，其他对象继续。
- status=completed 表示本次汇集完成；存在无法汇集的条目时为 partial。skipped_count 包含非文字、未填写文字及错误条目。
- 文字基准配置本身不可用时返回 partial，明确说明未能汇集；层不存在返回 None。

```sh
python -X utf8 -B -m tools.text.collect ../output/ai-production.sqlite3 1 1
python -X utf8 -B -m tools.text.collect ../output/ai-production.sqlite3 1 1 --json
```

默认输出汇集文字；需要来源与诊断时用 --json。纯文本模式仍会把诊断写到标准错误，不静默隐藏未读取的内容。条目诊断不改成查询失败退出码；SQL/参数错误或目标层不存在时退出码非零。

## 开发下一个工具

AI 开发工具时按这个顺序阅读：

1. [公共读写 API](../src/runtime/API.md)：完整层/对象的读取、装载和保存。
2. 对应的 [层配置](../configs/layers/README.md) 与 [对象配置](../configs/objects/README.md)：理解内容结构和约定。
3. [第一批工具示例](../src/examples/first_batch.py)与[完整往返示例](../src/examples/read_write.py)：查询组合，以及关闭数据库后重开、修改、再保存。
4. 仅在新增约束时阅读 [规则扩充说明](../src/runtime/validation/README.md)。

Python 工具实现放在 src/tools/<内容类型>/，通用功能放在 src/tools/common/；具体分类按需要创建。这里的 tools/README.md 作为说明入口，不提前增加工具注册框架。

工具使用 `from runtime.api import ...`，只处理自己的业务内容。读取时可选择完整字典或 Python 实例；修改后调用 save_layer/save_object。ID、事务、日志、配置继承、检测由核心处理。

小工具采用普通函数，参数显式带 connection、project_id 和目标编号。需要哪些输入、会修改哪些内容、返回什么，写在函数说明和一个可运行示例中。新工具无需进入核心的 __init__ 批量导入，也不要求 MCP、Skill 或可视化依赖。

命令行的打开数据库、JSON 输出和错误反馈由 [tools/_cli.py](../src/tools/_cli.py) 复用；它不注册或扫描工具。范围与关联 SQL 放在核心 [storage/queries.py](../src/runtime/storage/queries.py)，工具通过 runtime.api 调用。需要连续几次一致的读取，可使用 read_snapshot 复用现有读取事务。

涉及删除的工具应明确调用 delete；不要用省略对象或清空局部列表来表达删除。纯查询工具不写数据。模型的 config_ref 留在数据库记录中，自定义用途创建时可明确指定。

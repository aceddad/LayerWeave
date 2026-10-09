# LayerWeave 内部工具开发

这里保存 LayerWeave 自身的内部工具说明。工具使用普通 Python 函数与核心 API，保持非可视化运行。

## 已有工具

| 工具 | 代码 | 用途 |
|---|---|---|
| 配置 help | [config_help.py](../src/tools/common/config_help.py) | 动态查看支持总览、层/对象类定义和联合说明；无需数据库 |
| 命令 help | [command_help.py](../src/tools/common/command_help.py) | 所有命令的总览或多目标详情，含参数、返回与 JSON 示例；只读 |
| 主动复查 | [recheck.py](../src/tools/common/recheck.py) | 项目、多棵子树或指定对象按当前配置重新检查；只读 |
| 历史 | [history.py](../src/tools/common/history.py) | 按操作分页展示字段变化、前后快照和撤销来源；只读 |
| 撤销/重做 | [undo.py](../src/tools/common/undo.py) | 原子撤销完整批次；更新按顶层字段判断，创建/删除按整条记录 |
| 删除子树 | [subtrees.py](../src/tools/common/subtrees.py) | 删除起始层、子孙层、对象及出向关联；保留外部入向关联 |
| 整层复制 | [subtrees.py](../src/tools/common/subtrees.py) | 同项目同父层复制完整子树，重映射内部引用，返回编号映射 |
| 对象分割 | [split.py](../src/tools/common/split.py) | 按单点/多点与明确的各段 information 分割，第一段保留编号和关联 |
| 插空档 | [gaps.py](../src/tools/common/gaps.py) | 明确选范围、位置和长度，跨界对象逐个 split/keep/stretch/move，整批原子执行 |
| 跨项目复制/剪切 | [transfer.py](../src/tools/common/transfer.py) | 目标重新发号、原数值保留；剪切时外部入向引用跟随新地址 |
| 项目概览 | [project_overview.py](../src/tools/common/project_overview.py) | 项目层级、层类型、名字与对象数量；只读 |
| 项目详细展开 | [project_details.py](../src/tools/common/project_details.py) | 展开项目/子树的层、对象内容和关联引用，可按数值范围筛选；只读 |
| 对象检索 | [find_objects.py](../src/tools/common/find_objects.py) | 按层、名字、内容、位置范围查找对象；只读 |
| 关联查询 | [relations.py](../src/tools/common/relations.py) | 查询直接引用与被引用，保留跨项目完整身份；只读 |
| 文本汇集 | [collect.py](../src/tools/text/collect.py) | 按顺序提取文字，保留来源，逐项报告不可读取的内容；只读 |
| 接续新增 | [objects.py](../src/tools/common/objects.py) | 自动从层尾或指定对象后新增；写入 |
| 连续排列 | [positions.py](../src/tools/common/positions.py) | 同层对象首尾接续，保留各自时长；写入 |
| 整体平移 | [positions.py](../src/tools/common/positions.py) | 同时移动所选对象的开始和结束位置；写入 |
| 起终点对齐 | [positions.py](../src/tools/common/positions.py) | 共享开始位置或结束位置，保持各自时长；写入 |
| 修改时长 | [positions.py](../src/tools/common/positions.py) | 保持起点，计算新的终点；写入 |
| 复制对象 | [objects.py](../src/tools/common/objects.py) | 复制内容与配置、发放新编号，不复制关联；写入 |

第一批四个工具已齐备，完整内存示例见 [first_batch.py](../src/examples/first_batch.py)。从 src/ 运行 `python -X utf8 -B -m examples.first_batch`，不改动真实项目数据库。

第二批六个通用写入工具的完整内存示例见 [second_batch.py](../src/examples/second_batch.py)：`python -X utf8 -B -m examples.second_batch`。两批工具都不依赖可视化、Skill 或 MCP。

复查、历史与撤销的 Python/CLI 参数和恢复语义见 [完整说明](../src/runtime/storage/HISTORY.md)。从 src 运行 `python -X utf8 -B -m examples.review_history` 可查看独立内存数据库示例。新工具继续使用 runtime.api，数据库查询与恢复代码在存储层；它们不需要 Skill 或 MCP。

子树删除与整层复制也已提供，范围包含起始层及全部后代；每次操作可整批撤销。用法、关联边界和 id_map 格式见 [子树工具说明](../src/runtime/storage/SUBTREES.md)，内存演示为 `python -X utf8 -B -m examples.subtrees`。

分割、按起点筛选平移、插空档和跨项目复制/剪切的参数与完整示例见 [编辑工具说明](../src/runtime/storage/EDITING.md)。内存演示为 `python -X utf8 -B -m examples.editing`。位置工具的 shift 入口保持兼容，新增 --layer-ids、--from-position 和 --config-root；其与插空档共用底层数值计算。

## 命令 help

不知道该调用哪个工具时，先用 `python -m tools.common.command_help`；指定多个名字可查看详情，例如 `python -m tools.common.command_help split insert_gap undo --json`。Python 入口为 `runtime.api.command_help()` 或 `command_help(["split", "insert_gap"])`。

各工具在自身模块的 COMMANDS 字面量中声明用途、参数、返回和示例。统一目录自动发现，根级 CLI --help 共用其中的示例；新增工具不必改中央名单。它仅提供只读说明，未来 MCP 可以复用这些数据。完整规则见 [命令目录说明](../src/tools/COMMANDS.md)。

插空档必须明确选择 --layer-id、--layer-ids 或 --project。--contents-file 是 object_id/action 列表；split 带两段 information，keep 保持原样，stretch 只延长终点，move 将起终点一起后移本层实际插入长度。后两者不处理媒体内容，数据与关联保持。漏传范围不会默认扩大到整个项目，未选择的对象不被修改；这些跨界动作可能覆盖插入时段。

## 配置 help

这是封装说明查询，不查询项目中的实际层或对象，也不需要数据库。四种范围共用动态配置目录：

```python
from tools.common.config_help import config_help, format_help

catalog = config_help()
layers = config_help("layers", ["text", "image"])
objects = config_help("objects", ["Text", "Title", "objects/model.toml"])
combined = config_help("combined", ["TextLayer", "ImageLayer"])
developer = config_help("objects", ["model", "Title"], audience="developer")
print(format_help(combined))
```

- overview：简短列出所有层及其可接受的对象类。
- layers：层支持详情，兼容对象类只列摘要。
- objects：对象类支持详情，包含用途、有效内容字段、约束和保存示例。
- combined：层与其兼容对象类的联合详情，共用的对象说明只展开一次。

```sh
python -X utf8 -B -m tools.common.config_help
python -X utf8 -B -m tools.common.config_help layers text image --json
python -X utf8 -B -m tools.common.config_help objects Title --raw
python -X utf8 -B -m tools.common.config_help objects model Title --dev
python -X utf8 -B -m tools.common.config_help combined text audio
python -X utf8 -B -m examples.config_help
```

默认使用版精简展示传入/返回、用途和带 config_ref 的保存示例；--dev / audience="developer" 展开完整定义、继承与字段来源、汇报设置和当前原文。两种模式均支持四种范围与多目标。目标支持配置路径、唯一 type、完整 Python 类路径或唯一类名，歧义会列出候选。--raw 可为使用版附当前 TOML 原文。坏配置逐项提示，其他继续。新增封装无需修改 help 代码，查看也不导入封装模块。格式和开发约定见 [配置 help 说明](../src/runtime/configuration/HELP.md)。

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

## 项目详细展开

```python
from tools.common.project_details import project_details, format_details

whole = project_details(connection, project_id)
subtree = project_details(connection, project_id, layer_id=1)
window = project_details(connection, project_id, begin=10, end=20)
multiple = project_details(connection, project_id, layer_ids=[1, 7], begin=10, end=20)
compact = project_details(connection, project_id, layer_ids=[1, 7], begin=10, end=20, compact=True)
print(format_details(compact))
```

| 层范围 | 时间/位置范围 | 结果 |
|---|---|---|
| 未指定 | 未指定 | 全部层和对象，包括空层 |
| layer_id 或 layer_ids | 未指定 | 所选层自身及子孙层的并集，所有对象 |
| 未指定 | 指定 begin/end | 全部层保留，对象按数值范围筛选 |
| layer_id 或 layer_ids | 指定 begin/end | 所选子树完整保留，对象按数值范围筛选 |
| layer_ids=[] | 任意 | 空选择，不展开全项目 |

layer_id 与 layer_ids 互斥。多层编号去重；同时选择父层和子层时，每个层/对象只返回一次。输出按全项目的父子树序排列，不按传入编号的先后排列；每个独立选中子树从 depth=0 开始，原 father 保留。父链异常也不会无限展开。

位置条件与对象检索共用：[begin,end)，两端相等为点查询，可只提供一端。严格按已保存的数值比较，不按轴单位、precision 或 fps 换算、取整查询范围，也不裁剪命中对象的原位置或内容。未命中的层返回 objects=[]、object_count=0；该数量仅表示本次范围内的直属对象，子层独立统计。

返回 project、scope、counts、layers、missing_layer_ids、status、issues。scope.layer_ids 是去重后的请求编号，root_ids 是按树序排列的有效起始编号；原 layer_id 字段为单层入口保留。层仍为扁平列表，带 depth 和嵌套的 objects。

多层请求里不存在的编号单独列入 missing_layer_ids，issues 给出可配置的诊断，其余有效子树继续返回；全部编号都不存在时也返回空 layers 与这些诊断。status 为 partial，不会把不存在的层伪装成“0 个对象的层”。项目不存在，或旧单层入口 layer_id 不存在时，仍返回 None。CLI 在文字模式将诊断逐条写入 stderr，JSON 模式将它们保留在 issues；Python 调用方也可用 runtime.api.format_issue 单独格式化。

### 完整与精简输出

默认保留完整字段、information 和发出的 bind。compact=True 同时适用于 Python 返回值、JSON 和文字：

- 项目身份在 project.id 保留一次，省略层/对象中重复的 project_id；对象的 layer 由所属 objects 容器确定。
- 省略空 name、tips、bind，以及值为 None 的 father/axis；project.max_id 属于发号状态，精简查看时省略。
- 保留编号、对象 config_ref、起止位置、非空备注和完整关联引用。Text 和 Title 等派生对象仍可区分，跨项目关联的目标身份仍完整。
- 不清理 information 内部的任何值；0、false、空字符串、空列表、空字典、null 均原样保留。显式 axis={} 也保留，因为它表示自有轴。
- 每层保留 objects（即使为空）和本范围 object_count。精简只是查看投影，不修改数据库；需要完整记录时使用默认模式或 read_project_details。

原始数据在一个读取快照内批量获取。非空全项目展开通常为 4 次查询，指定单层/多层为 5 次；多层查询批量读取项目的 id/father 来确定树序，范围外正文和关联不读取。核心不加载配置、不写日志；只有工具遇到不存在的编号时，才读取独立的日志汇报配置。可传 config_root（CLI 为 --config-root）指定该配置根目录。

```sh
python -X utf8 -B -m tools.common.project_details ../output/ai-production.sqlite3 1 --json
python -X utf8 -B -m tools.common.project_details ../output/ai-production.sqlite3 1 --layer-id 1 --begin 10 --end 20
python -X utf8 -B -m tools.common.project_details ../output/ai-production.sqlite3 1 --layer-ids 1 7 --begin 10 --end 20 --compact
python -X utf8 -B -m tools.common.project_details ../output/ai-production.sqlite3 1 --layer-ids 1 7 --compact --json
python -X utf8 -B -m examples.project_details
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

- 非文字对象会跳过。文字对象未填写 text 且未声明 optional=true 时产生 missing_field 后跳过；默认 warn，可通过独立 configs/logging/diagnostics.toml 改变汇报等级。即使设置 none，提取不完整的状态和 skipped_count 仍如实保留。optional=true 的合法缺省只计入 skipped_count，不导致 partial；提供了错误类型仍报告。空字符串视为已填写，正常保留。
- 配置缺失或文字类型错误逐条放入 issues，附 severity、target、field 和 message，其他对象继续。
- status=completed 表示本次汇集完成；存在无法汇集的条目时为 partial。skipped_count 包含非文字、未填写文字及错误条目。
- 文字基准配置本身不可用时返回 partial，明确说明未能汇集；层不存在返回 None。

```sh
python -X utf8 -B -m tools.text.collect ../output/ai-production.sqlite3 1 1
python -X utf8 -B -m tools.text.collect ../output/ai-production.sqlite3 1 1 --json
```

默认输出汇集文字；需要来源与诊断时用 --json。纯文本模式仍会把诊断写到标准错误，不静默隐藏未读取的内容。条目诊断不改成查询失败退出码；SQL/参数错误或目标层不存在时退出码非零。

## 第二批：通用写入约定

六个工具都是普通函数，使用同一项目内的明确编号，不改项目号或对象编号。位置只按数值计算，允许负位置，不自动换算轴单位、裁剪内容或留出间隔。

工具生成的坐标使用十进制计算，再按当前轴的 precision（正数步长）落到最近刻度；正好半格时远离 0 取整。默认沿父链使用根轴，若子层显式提供自己的 axis，则它和后代使用该轴；自有轴未声明 precision 时不借用另一轴的精度。没有轴或该轴没有 precision 时默认步长 1e-6，fps 不用于换算。轴查找在同一次操作内复用，下一次操作重新读取。

例如 precision=0.001 时三次追加 0.1 的终点为 0.1、0.2、0.3，不留下浮点尾差。连续排列先累计未量化的位置，再分别落点，避免每段取整后继续累计造成额外误差。独立追加使用实际已保存的层尾，不保存隐藏的时间残差。

量化可能使实际位置或时长相对原请求产生精度范围内的差异，短区间也可能变成瞬间。修改时长按原起点计算终点，提交的两端统一落点；普通复制也按目标层刻度保存。直接 CRUD 与普通保存同样落点，原始读取和只读范围查询保留原数值，不批量改写已有数据；旧数据再次写入位置时才归一并记日志。

读取当前位置、计算请求、写入数据与日志在一次 BEGIN IMMEDIATE 事务内完成；接续新增不会先在事务外读取旧的层尾。一个工具调用共用一个 operation_id，提交后检测一次。底层约定问题仍作为 checks 返回，已经提交的数据保留。

输入不是可计算的有限数值、指定目标不存在或写入失败时，本次操作整体回滚。可计算的负时长不会被改成正数：begin<=end 等约定仍在提交后反馈。瞬间对象继续占一个点；它后面直接接续可能产生重叠提示，工具不猜一个微小间隔。

以下函数都可传 checker，含义与 dispatch 一致：默认内置检测，None 关闭自动检测，或传入自定义检查器。单对象动作返回单次 dispatch 结果，批量动作返回 results 列表；无变化时 applied=false，不写日志。不得在调用方尚未提交的事务中再调用这些完整操作入口。

### 接续新增

```python
from tools.common.objects import append_object

result = append_object(connection, project_id, layer_id, {
    "config_ref": "objects/text.toml", "name": "下一句",
    "information": {"text": "正文"},
}, duration=3)
```

先用该层所有对象中最大的 end 计算 begin、end=begin+duration，再按当前轴精度落点。空层从 0 开始，可用 empty_start 指定空层起点。after_id 可指定同层的某个对象，以它的 end 为计算起点；不会移动这个对象后面的其他内容。

data 是原有 create 的对象字段字典，需要 config_ref；工具决定其中的 layer、begin、end，其他字段交给核心保存，不修改传入字典。新编号从结果 id 取得。关联仍使用明确的关联操作添加。

### 连续排列、平移与对齐

```python
from tools.common.positions import arrange_objects, shift_objects, align_objects

# 不传 object_ids：排列该层全部对象，默认保留首个对象的起点。
result = arrange_objects(connection, project_id, layer_id)
# 显式列表决定排列顺序；其余对象保持原状。
result = arrange_objects(connection, project_id, layer_id, object_ids=[5, 2, 8], start=0)

result = shift_objects(connection, project_id, [2, 5], offset=-3)
result = shift_objects(connection, project_id, layer_id=layer_id, offset=5)

result = align_objects(connection, project_id, [2, 5], position=10, edge="begin")
result = align_objects(connection, project_id, [2, 5], position=10, edge="end")
```

连续排列限定在同一层。默认按当前 begin/end/id 排序，显式 object_ids 按给定顺序；以各对象实际存储的 end-begin 累计位置，再按精度落点，依次首尾衔接。

平移和对齐可选同项目不同层的对象，调用方负责选择轴含义一致的对象。也可通过 layer_id 明确选择整层；不会隐式修改整个项目。重复编号只处理一次，显式空列表表示不修改对象。

起点对齐以 position 为新起点、终点按原时长计算；终点对齐以 position 为终点、起点按原时长倒推，再将生成的端点按各自轴精度落点。内容不变；实际时长可能有量化差异。在同一层可能产生重叠，沿用提交后诊断。

### 修改时长与复制

```python
from tools.common.positions import set_duration
from tools.common.objects import copy_object

result = set_duration(connection, project_id, object_id, 4)
result = copy_object(connection, project_id, object_id)
result = copy_object(connection, project_id, object_id, layer_id=target_layer_id, begin=10, name="副本")
result = copy_object(connection, project_id, object_id, layer_id=target_layer_id, append=True)
```

修改时长保持 begin，设置 end=begin+duration，不自动后推其他对象。

复制默认保留内容、配置、名字、备注、所属层与位置，新编号由核心发放。可另选同项目目标层、名字或起点；指定起点时保留原时长。append=True 将副本接到目标层末尾，空层从 0 开始，不能同时指定 begin。

单对象复制不修改原对象，不复制出向/入向关联，也不复制媒体文件；information 中的资源引用保持原样。需要连同内部关联复制完整子树时，使用 [copy_subtree](../src/runtime/storage/SUBTREES.md)。跨项目的子树复制/剪切使用 [transfer_subtree](../src/runtime/storage/EDITING.md)，单独对象的跨项目入口暂未提供。

### 第二批命令行

从 src/ 目录运行，默认返回标准操作与检测 JSON。在子命令之前加 `--text` 可逐条显示写入结果与诊断，例如 `python -X utf8 -B -m tools.common.positions ../output/ai-production.sqlite3 1 --text duration 2 4`。成功和无变化操作退出码为 0，操作失败为 1；检测报告问题不会把已经成功写入的操作改成失败。

```sh
python -X utf8 -B -m tools.common.positions ../output/ai-production.sqlite3 1 arrange 1 --start 0
python -X utf8 -B -m tools.common.positions ../output/ai-production.sqlite3 1 shift --ids 2 5 --offset -3
python -X utf8 -B -m tools.common.positions ../output/ai-production.sqlite3 1 align --ids 2 5 --edge end --position 10
python -X utf8 -B -m tools.common.positions ../output/ai-production.sqlite3 1 duration 2 4
python -X utf8 -B -m tools.common.objects ../output/ai-production.sqlite3 1 append 1 3 --data-file object.json
python -X utf8 -B -m tools.common.objects ../output/ai-production.sqlite3 1 copy 2 --append
```

object.json 为对象创建字段，例如 `{"config_ref":"objects/text.toml","information":{"text":"下一句"}}`。平移与对齐可用 --layer-id 选择整层；arrange 用 --ids 指定排列顺序；append 可用 --after-id 或 --empty-start。

## 开发下一个工具

AI 开发工具时按这个顺序阅读：

1. [公共读写 API](../src/runtime/API.md)：完整层/对象的读取、装载和保存。
2. 对应的 [层配置](../configs/layers/README.md) 与 [对象配置](../configs/objects/README.md)：理解内容结构和约定。
3. [第一批工具示例](../src/examples/first_batch.py)、[第二批工具示例](../src/examples/second_batch.py)与[完整往返示例](../src/examples/read_write.py)：查询组合、位置编辑，以及关闭数据库后重开再保存。
4. 仅在新增约束时阅读 [规则扩充说明](../src/runtime/validation/README.md)。

Python 工具实现放在 src/tools/<内容类型>/，通用功能放在 src/tools/common/；具体分类按需要创建。这里的 tools/README.md 作为说明入口，不提前增加工具注册框架。

工具使用 `from runtime.api import ...`，只处理自己的业务内容。读取时可选择完整字典或 Python 实例；修改后调用 save_layer/save_object。ID、事务、日志、配置继承、检测由核心处理。

小工具采用普通函数，参数显式带 connection、project_id 和目标编号。需要哪些输入、会修改哪些内容、返回什么，写在函数说明和一个可运行示例中。新工具无需进入核心的 __init__ 批量导入，也不要求 MCP、Skill 或可视化依赖。

命令行的打开数据库、JSON 输出和错误反馈由 [tools/_cli.py](../src/tools/_cli.py) 复用；它不注册或扫描工具。范围与关联 SQL 放在核心 [storage/queries.py](../src/runtime/storage/queries.py)，工具通过 runtime.api 调用。需要连续几次一致的读取，可使用 read_snapshot 复用现有读取事务。

需要先读取再计算写入的工具，使用 `dispatch(connection, request_factory)`：工厂接收 read_record 查询函数，在写事务内返回一个请求字典或请求列表。不要在事务外先计算层尾再单独保存，也不要在工厂中自行写 SQL 或调用另一个完整事务入口。现有位置工具可作为例子。

生成新坐标时复用 [PositionMath/decimal_value](../src/runtime/positions.py)，从 runtime.api 导入，共享十进制运算、轴来源查找与精度落点；原 tools/common/_precision.py 仅保留导入兼容。纯读取工具继续使用原始存储数值，不调用取整逻辑。

涉及删除的工具应明确调用 delete；不要用省略对象或清空局部列表来表达删除。纯查询工具不写数据。模型的 config_ref 留在数据库记录中；实例保存按实际 Python 类取得唯一配置。新增封装同时提供自己的类与 TOML，字典保存明确指定 config_ref。Title/Text 的继承与往返示例见 `src/examples/title.py`。

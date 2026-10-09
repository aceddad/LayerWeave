# 查询与常用编辑

这里说明项目查询、接续、排列、对齐、时长、对象复制和空档查询。[返回使用入口](README.md)。

范围平移、分割、插空档和跨项目搬移见[编辑工具](EDITING.md)，整层操作见[子树工具](SUBTREES.md)，复查与恢复见[历史工具](HISTORY.md)。Python 示例使用已有连接和真实编号，CLI 从 src 运行。

## 帮助入口

查工具用途与调用示例使用命令 help；查可用层、对象类与配置示例使用配置 help。两个入口均无需数据库：

```sh
python -m tools.shared.command_help split insert_gap undo --json
python -m tools.shared.config_help combined text
```

完整说明分别维护在[命令说明](../shared/COMMANDS.md)和[配置 help](../shared/CONFIG_HELP.md)。

## 项目概览

```python
from tools.usage.common.project_overview import project_overview, format_overview

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

概览只读，不返回对象正文或轴详情；需要内容时使用详细展开。

从 src/ 目录查看自己的项目：

```sh
python -X utf8 -B -m tools.usage.common.project_overview ../output/ai-production.sqlite3 1
python -X utf8 -B -m tools.usage.common.project_overview ../output/ai-production.sqlite3 1 --json
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
from tools.usage.common.project_details import project_details, format_details

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

详细展开只读；config_root（CLI 为 --config-root）选择缺失目标提示所用的诊断配置目录。

```sh
python -X utf8 -B -m tools.usage.common.project_details ../output/ai-production.sqlite3 1 --json
python -X utf8 -B -m tools.usage.common.project_details ../output/ai-production.sqlite3 1 --layer-id 1 --begin 10 --end 20
python -X utf8 -B -m tools.usage.common.project_details ../output/ai-production.sqlite3 1 --layer-ids 1 7 --begin 10 --end 20 --compact
python -X utf8 -B -m tools.usage.common.project_details ../output/ai-production.sqlite3 1 --layer-ids 1 7 --compact --json
python -X utf8 -B -m examples.project_details
```

## 对象检索

```python
from tools.usage.common.find_objects import find_objects

objects = find_objects(connection, project_id, layer_id=1,
                       name="开场", content="你好", begin=10, end=20)
```

- 除 project_id 外均可省略，多个条件同时满足（AND）。layer_id 仅限定该层直属对象，不递归子层。
- name 是名字中的字面子串；content 搜索 information 中的字符串值，包括嵌套字典/列表，不搜索键名，不将数字/布尔值转换为文字。两者区分大小写，`%`、`_` 不作为通配符。
- begin/end 查询对象与范围的交集：范围 [begin,end)，相等时表示占用该点的对象。只给一端可查询向前/向后的范围；两端均省略时不筛选位置。
- 首尾相接不重叠，瞬间对象占一个点。位置筛选只匹配有效数值区间；未筛位置时，原有无效区间记录仍可按其他字段找到。查询不做单位转换。
- 返回普通对象记录列表，保留 project_id、id、layer、config_ref 和 information，不装载关联。多个层先按 layer 排列，层内按 begin/end/id 排列；没有匹配时返回空列表。

```sh
python -X utf8 -B -m tools.usage.common.find_objects ../output/ai-production.sqlite3 1 --layer-id 1 --content 你好 --begin 10 --end 20
```

命令行默认输出 JSON。结构条件在存储层使用参数化 SQL；内容匹配处理已经按结构条件筛选的 JSON 值，不打开内容引用的资源文件。

## 关联查询

```python
from tools.usage.common.relations import query_relations

relations = query_relations(connection, project_id, "object", object_id)
```

返回 entity、direction、outgoing、incoming。entity 是查询实体的 kind/project_id/id；两个方向的列表保留完整 bind 记录及 tips。direction 可为 both（默认）、outgoing、incoming；只选一个方向时，另一列表未查询，返回空列表。

自关联在 outgoing/incoming 中各出现一次。按 kind、项目和编号共同匹配，不把其他项目的同号记录混入结果。实体或目标已删除时仍可查询保留的关联；工具不声称端点一定存在，也不自动装载或递归目标。需要存在性诊断时使用核心 validate。

```sh
python -X utf8 -B -m tools.usage.common.relations ../output/ai-production.sqlite3 1 object 2 --direction both
```

命令行默认输出 JSON。

## 文本汇集

```python
from tools.usage.text.collect import collect_text

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
python -X utf8 -B -m tools.usage.text.collect ../output/ai-production.sqlite3 1 1
python -X utf8 -B -m tools.usage.text.collect ../output/ai-production.sqlite3 1 1 --json
```

默认输出汇集文字；需要来源与诊断时用 --json。纯文本模式仍会把诊断写到标准错误，不静默隐藏未读取的内容。条目诊断不改成查询失败退出码；SQL/参数错误或目标层不存在时退出码非零。

## 常用编辑

以下操作使用同一项目的对象。先看调用示例，共用的位置和反馈规则见下方[通用写入约定](#通用写入约定)。

### 接续新增

从层尾或指定对象的终点接着创建一个对象。

```python
from tools.usage.common.objects import append_object

result = append_object(connection, project_id, layer_id, {
    "config_ref": "objects/text.toml", "name": "下一句",
    "information": {"text": "正文"},
}, duration=3)
```

先用该层所有对象中最大的 end 计算 begin、end=begin+duration，再按当前轴精度落点。空层从 0 开始，可用 empty_start 指定空层起点。after_id 可指定同层的某个对象，以它的 end 为计算起点；不会移动这个对象后面的其他内容。

data 是原有 create 的对象字段字典，需要 config_ref；工具决定其中的 layer、begin、end，其他字段交给核心保存，不修改传入字典。新编号从结果 id 取得。关联仍使用明确的关联操作添加。

### 连续排列与对齐

保留各自时长，连续排列或对齐起终点。整体平移见[平移](EDITING.md#平移)。

```python
from tools.usage.common.positions import arrange_objects, align_objects

# 不传 object_ids：排列该层全部对象，默认保留首个对象的起点。
result = arrange_objects(connection, project_id, layer_id)
# 显式列表决定排列顺序；其余对象保持原状。
result = arrange_objects(connection, project_id, layer_id, object_ids=[5, 2, 8], start=0)

result = align_objects(connection, project_id, [2, 5], position=10, edge="begin")
result = align_objects(connection, project_id, [2, 5], position=10, edge="end")
```

连续排列限定在同一层。默认按当前 begin/end/id 排序，显式 object_ids 按给定顺序；以各对象实际存储的 end-begin 累计位置，再按精度落点，依次首尾衔接。

对齐可选同项目不同层的对象，调用方负责选择轴含义一致的对象。也可通过 layer_id 明确选择整层；不会隐式修改整个项目。重复编号只处理一次，显式空列表表示不修改对象。

起点对齐以 position 为新起点、终点按原时长计算；终点对齐以 position 为终点、起点按原时长倒推，再将生成的端点按各自轴精度落点。内容不变；实际时长可能有量化差异。在同一层可能产生重叠，沿用提交后诊断。

### 修改时长与复制

设置对象时长，或创建一个可放到新位置的副本。

```python
from tools.usage.common.positions import set_duration
from tools.usage.common.objects import copy_object

result = set_duration(connection, project_id, object_id, 4)
result = copy_object(connection, project_id, object_id)
result = copy_object(connection, project_id, object_id, layer_id=target_layer_id, begin=10, name="副本")
result = copy_object(connection, project_id, object_id, layer_id=target_layer_id, append=True)
```

修改时长保持 begin，设置 end=begin+duration，不自动后推其他对象。

复制默认保留内容、配置、名字、备注、所属层与位置，新编号由核心发放。可另选同项目目标层、名字或起点；指定起点时保留原时长。append=True 将副本接到目标层末尾，空层从 0 开始，不能同时指定 begin。

单对象复制不修改原对象，不复制出向/入向关联，也不复制媒体文件；information 中的资源引用保持原样。需要连同内部关联复制完整子树时，使用 [copy_subtree](SUBTREES.md)。跨项目子树使用 transfer_subtree；选中一个或多个对象放入目标已有层使用 transfer_objects，后者会复制出向关联。详见 [跨项目工具](EDITING.md)。

### 位置与对象命令行

从 src/ 目录运行，默认返回标准操作与检测 JSON。在子命令之前加 `--text` 可逐条显示写入结果与诊断，例如 `python -X utf8 -B -m tools.usage.common.positions ../output/ai-production.sqlite3 1 --text duration 2 4`。成功和无变化操作退出码为 0，操作失败为 1；检测报告问题不会把已经成功写入的操作改成失败。

```sh
python -X utf8 -B -m tools.usage.common.positions ../output/ai-production.sqlite3 1 arrange 1 --start 0
python -X utf8 -B -m tools.usage.common.positions ../output/ai-production.sqlite3 1 align --ids 2 5 --edge end --position 10
python -X utf8 -B -m tools.usage.common.positions ../output/ai-production.sqlite3 1 duration 2 4
python -X utf8 -B -m tools.usage.common.objects ../output/ai-production.sqlite3 1 append 1 3 --data-file object.json
python -X utf8 -B -m tools.usage.common.objects ../output/ai-production.sqlite3 1 copy 2 --append
```

object.json 为对象创建字段，例如 `{"config_ref":"objects/text.toml","information":{"text":"下一句"}}`。对齐可用 --layer-id 选择整层；arrange 用 --ids 指定排列顺序；append 可用 --after-id 或 --empty-start。

## 通用写入约定

| 事项 | 行为 |
|---|---|
| 编号 | 修改保留原身份；新建和复制由系统发号 |
| 坐标 | 按轴 precision 取最近刻度，半格时远离 0；无精度时用 1e-6 |
| 轴来源 | 默认沿父链查找；显式自有轴覆盖上级，自有轴未声明 precision 时使用默认精度 |
| 单位 | 按数值计算，允许负位置；不做单位或 fps 换算，不裁剪内容 |
| 量化影响 | 实际位置/时长可能有精度范围内差异，极短区间可能变成瞬间 |
| 反馈 | 单对象动作返回单次结果，批量动作有 results；无变化时 applied=false |

- 连续排列累计未量化的时长后再落点，避免逐段取整引入额外误差。独立追加从实际保存的层尾继续，不保留隐藏残差。
- precision=0.001 时，连续三次追加 0.1 的终点为 0.1、0.2、0.3。
- 修改时长会把提交的两端统一落点；普通复制按目标层精度保存。纯读取保留原值，不批量归一旧数据。
- 每次修改对应一个 operation_id。不可计算的值、缺失目标或操作写入失败时整批不写；提交后的检查问题不会自动撤销数据。
- 可计算的负时长不自动改正；瞬间对象占一个点，紧接其后追加可能产生重叠提示。
- Python 可传 checker；默认检查，None 关闭自动检查。自定义回调见[开发 API](../../runtime/API.md#自定义检查器)。
- 完整操作入口不能使用已有待提交操作的连接。反馈字段见[CRUD 协议](CRUD.md)。

## 空档查询

查找指定层在一个区间内的空白，可要求至少容纳一定长度。

```python
from runtime.api import find_gaps

result = find_gaps(connection, project_id, layer_id, begin=0, end=20, min_length=3)
```

```sh
python -m tools.usage.common.free_ranges DATABASE 1 4 0 20 --min-length 3 --json
```

只查询指定层直属对象，不自动包含子层。begin/end 明确限定 [begin,end)，min_length 默认 0；先合并占用区间，再返回正长度空档。相邻对象的首尾相接不产生空档；空层返回整个查询区间，begin=end 返回空列表。负位置可用。

返回 project_id、layer_id、scope、count、gaps。例如已有 [0,3)、[7,20) 时，查询 0–20 返回：

```json
{"begin": 3, "end": 7, "length": 4.0, "begin_inclusive": true}
```

每个空档的终点都不包含。瞬间对象仍占一个点：若 5 处有瞬间对象，其后的空档从 `(5,...` 开始，begin_inclusive=false；工具不猜一个 epsilon 或改写坐标。min_length 按可容纳长度筛选，因此开起点的 `(5,8)` 不算能容纳完整 3 单位的对象。

查询不加载配置、对象正文或关联，不换算轴或取整。与对象检索不同，若本层存在无法解释的位置（非有限数值或 begin>end），本次空档查询会指出对象并失败，避免把未知占用视为空闲；可用 recheck 查看完整诊断。读取使用同一快照，不写入数据库或日志。

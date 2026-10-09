# 分割、平移、插空档与跨项目复制/剪切

本批工具复用现有事务、CRUD、日志与提交后检查；基础类与表结构不增加字段。

跨界动作由调用者明确选择 split、keep、stretch 或 move。stretch 只将 end 增加本层实际插入长度，保持 begin；move 将 begin/end 一起增加该长度，复用普通平移计算。两者都保持编号、内容和关联，按现有轴精度落点，不执行音视频变速、补帧或资源裁切。所有动作只作用于明确选中的跨界对象，未按类型自动选择。

分割从数据库读取原区间，调用者提供 first_information 和 cuts 列表。每个切点包含 at 与从该处开始的 information；N 个切点得到 N+1 段。所有边界按所在轴精度落点后须严格递增且切点在内部。第一段保留原编号和全部现有关联，其余段分配新编号，不复制关联。空切点不写入。内容字段仍由现有规则在提交后检查，工具不猜测或裁切文本、媒体。

批量平移支持显式对象、直属层或子树范围，可再用 from_position 选择 begin 不早于该数值的对象；不是区间相交筛选。偏移可以为负数，重叠按各层配置在整批提交后报告。插空档必须明确选择直属层、子树或整个项目：起点在切点及之后的对象后移，跨界对象逐个选择 split、keep、stretch 或 move，之前的内容不动。缺少处理方式时列出对象清单且整批不写。分割、平移的内部计算共用，组合执行只有一个 operation_id。

跨项目操作限定同一个数据库中不同的项目，以整层/子树为范围，副本根层落在目标项目根部。目标项目重新发号，内部结构与关联使用新身份；自由 information、资源路径保持原样。显式 axis 原样复制，不补出原来从父层继承的轴，不换算单位，也不按目标刻度改写原始 begin/end 数值。

复制保留源数据及指向原地址的外部入向关联。剪切在同一事务内创建目标、将外部入向关联改指新身份，再删除源子树及其出向关联。外部关联的自身 id 保持，目标侧复制出的关联使用新 id。全部动作记为一个可撤销操作，原日志与发号上界不回退。

## 分割接口

```python
from runtime.api import split_object

result = split_object(connection, project_id, object_id,
    first_information={"text": "第一段"},
    cuts=[
        {"at": 14, "information": {"text": "第二段"}},
        {"at": 17, "information": {"text": "第三段"}},
    ])
```

假设原区间为 [10,20)，结果是 [10,14)、[14,17)、[17,20)。切点是当前轴上的位置，不是相对时长、字符编号或均分份数。各段 information 为完整字典；允许空字典，但缺少声明字段时继续按配置产生诊断。只有 cuts=[] 时可省略 first_information，并作为无变化操作返回。需要两段内容相同时，明确提供两份相同内容。

新段沿用 name、tips、layer、config_ref，原对象的入向/出向/自关联继续指向第一段，不复制或自动改指新段；这并不表示原引用还覆盖整个旧区间。资源范围和文本切分由调用者或内容工具解释，自由内容中的编号不会被工具猜测替换。

data 返回 project_id、object_id、cuts（requested/actual 切点）和 segments（含 id、位置和内容的单表记录）。整次操作可按 operation_id 撤销。结构错误、越界、落点后重合、瞬间对象没有内部切点等情形整批不写；内容约定问题仍在写入后诊断。

```sh
# 从 src 运行，DATA.json 包含 first_information 与 cuts。
python -X utf8 -B -m tools.usage.common.split DATABASE PROJECT_ID OBJECT_ID --data-file DATA.json --json
```

## 范围平移

```python
from runtime.api import shift_objects

selected = shift_objects(connection, project_id, [8, 12], offset=-2)
after = shift_objects(connection, project_id, layer_ids=[4, 7], from_position=30, offset=2)
```

object_ids 显式选对象，layer_id 只选择该层直属对象，layer_ids 包含多棵子树且去重。layer_ids 与前两种范围不能混用；object_ids 配合 layer_id 时要求对象属于该层。空列表不写入，所有范围均省略时报告缺少选择。

from_position 按存储的 begin >= 此数值筛选，不是“与这个时间段相交”。跨过筛选起点、但 begin 更早的对象保持原位。平移沿用目标层当前精度，编号、内容及关联保持；返回原来的批量 dispatch 结果协议，包括 results。移动后 overlap=false 的层按最终状态报告重叠，不自动回滚，允许重叠的层不因此报错。

```sh
python -X utf8 -B -m tools.usage.common.positions DATABASE PROJECT_ID shift --ids 8 12 --offset -2
python -X utf8 -B -m tools.usage.common.positions DATABASE PROJECT_ID shift --layer-ids 4 7 --from-position 30 --offset 2
```

## 插空档

```python
from runtime.api import insert_gap

result = insert_gap(connection, project_id, layer_ids=[root_layer_id], at=30, length=2,
    crossing_actions=[{
        "object_id": crossing_object_id,
        "action": "split",
        "first_information": {"text": "切点之前"},
        "second_information": {"text": "切点之后"},
    }])
```

没有跨界对象时可省略 crossing_actions；也可以先显式分割，再单独插空档。每个跨界对象提供一次实际整数 object_id 及 action，不按类型或长度推断。组合调用只有一个操作，任何失败均无部分分割、延长或平移；多余或不再跨界的对象明确报告。

| action | 操作 | 内容要求 |
|---|---|---|
| split | 在切点分割，后段后移 | first_information 和 second_information |
| keep | 原样保留 | 不需要重新提供内容 |
| stretch | 仅 end 增加本层实际插入长度 | 内容、编号、关联不变 |
| move | begin/end 一起增加本层实际插入长度 | 内容、编号、关联不变 |

例如对象 [8,12)，在 10 插入长度 2：stretch 得到 [8,14)，move 得到 [10,14)，不是 [12,16)。stretch 的 begin 不写入，move 复用普通平移计算；更新的坐标按原有轴精度落点。它们只改变对象区间，不处理音视频变速、补帧或文件内容。

旧 split_contents 参数、或未写 action 但明确提供两段内容的旧文件仍按 split 兼容；新旧参数不能同传。

范围须在 layer_id、layer_ids、whole_project=True 中明确选一个；layer_id 仅直属层，layer_ids 含子孙层。省略范围不再扩展为整个项目。长度须为正数，按各层精度落点后仍须形成正长度时段。切点为所在层落点后的实际数值；对象原始 begin/end 用来判断是否跨界。结束恰好在切点的区间保持，起点或瞬间恰好在切点的对象后移。选择 split 时，两段分别结束于插入时段开始、开始于其结束；keep 保留原区间与全部内容。

各层分别计算实际切点和长度，不做轴单位换算；比如不同精度可能产生不同的实际长度。返回 data.scope 明确实际范围，data.gaps 列出插入时段，splits 列出分段结果，kept 列出保留对象，stretched/moved 分别列出明确选择延长/移动的跨界对象，含 previous_begin/previous_end 与实际 begin/end；shifted 仍只列出其余自动后移对象。keep、stretch、move 都可能覆盖插入时段，不宣称它完全空白。没有对象需修改时返回 unchanged，不创建“空白对象”。

缺少跨界处理时 error.required_crossings 列出对象、所属层、原区间和实际切点，allowed 给出 split/keep/stretch/move；required_splits 暂作为兼容别名。unused_object_ids 列出不适用的处理项，本批不写。选择 split 而旧坐标无法在当前刻度上形成两段时报告 invalid_cut；keep 不改写原始坐标。

```sh
python -X utf8 -B -m tools.usage.common.gaps DATABASE PROJECT_ID 30 2 --layer-ids 4 7 --json
# CONTENTS.json 是 object_id/action 列表，split 项另带两段 information。
python -X utf8 -B -m tools.usage.common.gaps DATABASE PROJECT_ID 30 2 --layer-id 4 --contents-file CONTENTS.json
python -X utf8 -B -m tools.usage.common.gaps DATABASE PROJECT_ID 30 2 --project --json
```

## 跨项目复制和剪切

```python
from runtime.api import transfer_subtree, undo_operation

copied = transfer_subtree(connection, source_project_id, source_layer_id, target_project_id, mode="copy")
moved = transfer_subtree(connection, source_project_id, source_layer_id, target_project_id, mode="cut")
if moved["ok"]:
    restored = undo_operation(connection, moved["operation_id"])
```

source_project_id 与目标项目必须不同且都存在，目标不需要是空项目；同项目复制继续使用 copy_subtree。目标根层 father=None，其后代 father 和对象 layer 指向目标的新编号。axis 仅复制记录上的显式值；源祖先提供的轴不会自动补到新根层。原数值精确保留，位置意义由目标上下文解释。

两种模式都为目标层/对象/出向关联重新发号，内部 bind 的 project_id 与 id 同时映射，出向外部目标保留完整旧地址。剪切另外更新所有外部入向关联（可来自任意项目）的目标地址，自身 id 与来源不变；原子删除源子树和源出向关联。information 中的自由引用、媒体文件、TOML 和 Python 文件不搬移。

data 含 mode、source_project_id、project_id（目标）、source_layer_id、layer_id（目标新根）、counts、id_map 和 redirected_bind_ids。id_map 分 layer/object/bind 三组 old_id/new_id；层/对象的旧新项目上下文由顶层两个项目号确定，bind 的编号本身全库唯一。数值 id 即使碰巧相同，跨项目的完整身份仍然不同。

整个剪切是一条操作历史；创建失败、入向改指失败或源删除失败，均回滚目标数据、源数据、关联、发号和日志。恢复时若目标对象或被改指的外部关联后来被修改，现有撤销冲突规则会整批拒绝。源、目标的 max_id 不因已提交的剪切或撤销回退。

```sh
python -X utf8 -B -m tools.usage.common.transfer DATABASE SOURCE_PROJECT copy SOURCE_LAYER TARGET_PROJECT --name "新版本" --json
python -X utf8 -B -m tools.usage.common.transfer DATABASE SOURCE_PROJECT cut SOURCE_LAYER TARGET_PROJECT --json
```

所有新入口支持 config_root 和 checker；CLI 可传 --config-root，默认采用内置检查。示例 `python -X utf8 -B -m examples.editing` 使用内存数据库演示这些工具，不修改真实项目。

## 对象跨项目复制和剪切

`transfer_objects(connection, project_id, object_ids, target_project_id, target_layer_id, mode="copy")`
将明确选择的一个或多个对象放入同库另一项目的已有层。object_ids 是编号列表，可以来自源项目不同层；重复编号只处理一次，空列表不写入。位置数值、配置和内容保留，不复制源层、轴或媒体文件，也不按目标轴重新落点。目标层的兼容性和重叠仍在提交后检查。

对象和它们发出的关联重新发号。选中对象之间的关联换成目标编号，其他出向目标保留原地址；copy 保留源对象与外部入向引用，cut 让外部入向引用跟随新地址后删除源对象和出向关联。整个批次共用一条操作历史，可整批撤销/重做；源层保留，发号上限不回退。

返回标准操作结果，data 含 source_project_id、source_object_ids、project_id（目标）、layer_id（目标已有层）、mode、counts、id_map、redirected_bind_ids。id_map 仍包含 layer/object/bind，layer 为空，因为这次没有创建层。

```python
from runtime.api import transfer_objects

result = transfer_objects(connection, 1, [8, 9], 2, 4, mode="copy")
```

```sh
python -m tools.usage.common.transfer_objects DATABASE 1 copy 2 4 --ids 8 9 --json
python -m tools.usage.common.transfer_objects DATABASE 1 cut 2 4 --ids 8 --json
```

## 代码位置

- storage/timeline.py：对象选择、分段规划、分割和插空档的事务组合；批量平移复用 dispatch。
- positions.shifted_positions：平移与插空档共用的数值计算。
- storage/subtrees.py：同项目复制和跨项目迁移共用的创建/删除逻辑。
- storage/crud.py 的私有 _insert：统一发号、插入和日志；仅跨项目复制在此保留原始坐标，普通写入仍先落点。
- tools/usage/common/split.py、gaps.py、transfer.py、transfer_objects.py：CLI 与展示；原 positions.py 的 shift 入口仍可用。

# 分割、平移、插空档与跨项目搬移

按任务选择：[分割](#分割)、[平移](#平移)、[插空档](#插空档)、[搬移子树](#跨项目复制或剪切子树)、[搬移对象](#跨项目复制或剪切对象)。[返回使用入口](README.md)。

Python 示例中的 connection 是已打开、没有待提交操作的连接，编号来自实际项目。CLI 从 src 运行；DATABASE 和编号替换为实际值。

## 分割

给出切点和每段内容，将一个对象分成多段。

```python
from runtime.api import split_object

result = split_object(connection, project_id, object_id,
    first_information={"text": "第一段"},
    cuts=[
        {"at": 14, "information": {"text": "第二段"}},
        {"at": 17, "information": {"text": "第三段"}},
    ])
```

原区间为 [10,20) 时，上例得到 [10,14)、[14,17)、[17,20)。

| 输入 | 含义 |
|---|---|
| object_id | 要分割的对象 |
| first_information | 第一段的完整内容字典 |
| cuts | 按位置递增的列表；每项包含 at 和从该处开始的一段 information |

**返回：**标准操作结果；data 包含 object_id、project_id、cuts（请求/实际切点）和 segments（各段记录）。

**边界行为：**

- 切点是轴上的绝对位置。N 个切点得到 N+1 段。
- 切点按轴精度落点后，必须严格递增且位于原区间内部；瞬间对象没有内部切点。
- 各段提供完整 information。内容相同时也要明确提供；工具不切分文字或处理媒体文件。
- 第一段保留原编号及全部现有关联。其余段取得新编号，不复制关联；原引用只继续指向第一段。
- 所有段沿用 name、tips、layer、config_ref。自由内容中的编号不改写。
- cuts=[] 表示不修改，此时可省略 first_information。空内容字典可以提交，缺字段等问题在写入后检查。
- 结构错误、越界或落点后切点重合时整批不写。成功后可按 operation_id 整批撤销。

CLI 使用同样的数据格式：

```sh
python -m tools.usage.common.split DATABASE PROJECT_ID OBJECT_ID --data-file DATA.json --json
```

DATA.json：

```json
{"first_information":{"text":"第一段"},"cuts":[{"at":14,"information":{"text":"第二段"}}]}
```

## 平移

选择对象后，将起点和终点统一增加一个偏移量。

```python
from runtime.api import shift_objects

selected = shift_objects(connection, project_id, [8, 12], offset=-2)
after = shift_objects(connection, project_id, layer_ids=[4, 7], from_position=30, offset=2)
```

| 输入 | 含义 |
|---|---|
| object_ids | 明确选择对象，可跨同项目的不同层 |
| layer_id | 选择一个层的直属对象 |
| layer_ids | 选择多棵子树，包含起始层与后代，重复范围去重 |
| from_position | 在所选范围内，再筛选 begin 不早于此值的对象 |
| offset | 正值后移，负值前移 |

**返回：**批量操作结果，results 列出各对象的处理结果。

**边界行为：**

- layer_ids 不能与另两种范围混用。object_ids 可配合 layer_id，但对象必须属于该层。
- 显式空列表不修改；省略所有范围会报缺少选择。
- from_position 按已保存的 begin 比较。跨过该位置、但起点更早的对象保持原位。
- 编号、内容和关联保持，位置按各自层的精度落点，不换算轴单位。
- 调用方选择轴含义一致的对象。移动后的重叠按层配置在提交后报告，不自动撤销写入。

```sh
python -m tools.usage.common.positions DATABASE PROJECT_ID shift --ids 8 12 --offset -2
python -m tools.usage.common.positions DATABASE PROJECT_ID shift --layer-ids 4 7 --from-position 30 --offset 2
```

## 插空档

在指定范围内插入一段长度，后续对象自动后移；跨过插入位置的对象由调用方逐个选择处理方式。

```python
from runtime.api import insert_gap

result = insert_gap(connection, project_id, layer_id=layer_id, at=10, length=2,
    crossing_actions=[{"object_id": crossing_object_id, "action": "stretch"}])
```

上例假定只有 crossing_object_id 跨过 10。原区间 [8,12) 会变成 [8,14)，起点不动。

| 输入 | 含义 |
|---|---|
| layer_id / layer_ids / whole_project=True | 三选一：直属层、多棵子树、整个项目 |
| at | 插入位置，按各层精度取得实际切点 |
| length | 插入长度，请求值及落点后的实际长度都须大于 0 |
| crossing_actions | 每个跨界对象的 object_id 和 action；无跨界对象时可省略 |

| action | 行为 | 内容要求 |
|---|---|---|
| split | 从切点分成两段，后段后移 | first_information、second_information 两个完整字典 |
| keep | 保留原区间 | 不需要重新提供内容 |
| stretch | 只让 end 后移 | 内容、编号、关联保持 |
| move | begin/end 一起后移 | 内容、编号、关联保持 |

**返回：**data.scope 表示实际范围；其他主要字段如下。

| 字段 | 内容 |
|---|---|
| gaps | 各层实际插入的位置和长度 |
| splits、kept | 分割结果、保留对象 |
| stretched、moved | 明确延长/移动的跨界对象，含 previous_begin/previous_end 与实际 begin/end |
| shifted | 自动后移的其余对象 |

**边界行为：**

- layer_id 不包含子层；layer_ids 包含后代。必须明确选择范围。
- 起点在实际切点及之后的对象后移；结束恰好在切点的区间不动，切点上的瞬间对象后移。
- 各层独立计算实际长度，不换算轴单位。跨界判断使用原始 begin/end 与实际切点。
- 对 [8,12) 在 10 插入 2：keep 得 [8,12)，stretch 得 [8,14)，move 得 [10,14)，split 得 [8,10) 和 [12,14)。
- stretch 不改起点，修改的坐标按轴精度落点。以上动作均不处理音视频变速、补帧或资源裁切。
- keep、stretch、move 可能覆盖插入区间，因此 gaps 不保证该处完全没有对象。
- 缺少跨界选择时，error.required_crossings 列出需要处理的对象、区间、实际切点和可选动作。unused_object_ids 表示多余或已不适用的选择；本批不写。
- split 若无法按当前精度形成两段，返回 invalid_cut。任何操作失败均整批不写；没有对象需修改时返回 unchanged。
- 可以先调用分割，再调用插空档；单次 insert_gap 中的组合动作共用一个可撤销操作。

```sh
python -m tools.usage.common.gaps DATABASE PROJECT_ID 10 2 --layer-id 4 --contents-file CONTENTS.json --json
```

CONTENTS.json 示例（编号需替换为本次范围内实际跨界对象）：

```json
[
  {"object_id":8,"action":"split","first_information":{"text":"前段"},"second_information":{"text":"后段"}},
  {"object_id":9,"action":"keep"},
  {"object_id":10,"action":"stretch"},
  {"object_id":11,"action":"move"}
]
```

现有 API 还接受 split_contents，以及未写 action 但完整提供两段内容的 split 项；split_contents 与 crossing_actions 不能同传。required_splits 是 required_crossings 的兼容别名。

## 跨项目复制或剪切子树

将整个子树放入同一数据库中的另一项目。

```python
from runtime.api import transfer_subtree

result = transfer_subtree(connection, source_project_id, source_layer_id,
                          target_project_id, mode="copy", name="新版本")
```

| 输入 | 含义 |
|---|---|
| layer_id | 源项目的起始层，包括其后代与对象；示例变量名为 source_layer_id |
| target_project_id | 不同的目标项目；不要求为空 |
| mode | copy 保留源数据；cut 搬走源数据 |
| name | 可选，新根层名称 |

**返回：**data 包含 mode、source_project_id、project_id（目标）、source_layer_id、layer_id（新根）、counts、id_map 和 redirected_bind_ids。

**子树行为：**

- 副本根层落在目标项目根部，father=None；内部父子关系与对象归属使用新编号。
- 只复制记录上显式存在的 axis，不补造从源祖先继承的轴。
- 位置保留原数值，具体复制/剪切规则见下方[共同行为](#跨项目操作的共同行为)。

```sh
python -m tools.usage.common.transfer DATABASE SOURCE_PROJECT copy SOURCE_LAYER TARGET_PROJECT --name "新版本" --json
python -m tools.usage.common.transfer DATABASE SOURCE_PROJECT cut SOURCE_LAYER TARGET_PROJECT --json
```

## 跨项目复制或剪切对象

将明确选择的一个或多个对象放入另一项目的已有层。

```python
from runtime.api import transfer_objects

result = transfer_objects(connection, source_project_id, [8, 9],
                          target_project_id, target_layer_id, mode="copy")
```

| 输入 | 含义 |
|---|---|
| object_ids | 源项目对象编号列表，可来自不同层；去重后保持选择顺序 |
| target_project_id | 同库中不同的目标项目 |
| target_layer_id | 目标项目内已存在的层 |
| mode | copy 或 cut，默认 copy |

**返回：**data 包含 mode、source_project_id、source_object_ids、project_id（目标）、layer_id（目标已有层）、counts、id_map 和 redirected_bind_ids。没有创建层，因此 id_map.layer 为空。

**对象行为：**

- 空 object_ids 列表不写入。
- 所有选中对象放入同一个目标层；源层和轴不搬移。
- 目标层的类型兼容性及重叠在提交后检查。已经提交的数据保留，见[结果判断](#操作结果与选项)。
- 关联与编号按下方共同行为处理。

```sh
python -m tools.usage.common.transfer_objects DATABASE 1 copy 2 4 --ids 8 9 --json
python -m tools.usage.common.transfer_objects DATABASE 1 cut 2 4 --ids 8 --json
```

## 跨项目操作的共同行为

| 内容 | copy | cut |
|---|---|---|
| 源范围内的数据 | 保留 | 搬移成功后删除 |
| 复制出的实体和出向关联 | 重新发号 | 重新发号 |
| 范围内部的关联目标 | 映射到目标新身份 | 映射到目标新身份 |
| 出向外部的关联目标 | 保留完整原地址 | 保留完整原地址 |
| 外部指向源范围的入向关联 | 继续指向源 | 跟随目标新身份，关联自身 id 不变 |

- 精确保留 begin/end，不换算单位或按目标轴重新落点。位置含义由目标上下文解释。
- information、资源引用保持原样；不改写自由内容中的编号，也不复制媒体、Python 或 TOML 文件。
- id_map 按 layer/object/bind 分组，每项为 old_id/new_id。项目上下文由 source_project_id 与 project_id 给出；局部编号碰巧相同仍是不同身份。
- 创建、改指和删除组成一次可撤销操作。任一步骤失败，源、目标、关联及本次发号都不留下部分修改。
- 已提交的编号进度不因剪切或撤销回退。恢复冲突处理见[撤销与重做](HISTORY.md#撤销与重做)。

## 操作结果与选项

- 用 ok、applied、operation 判断是否写入；checks 中的问题不表示提交已撤销。完整字段见 [CRUD 协议](CRUD.md)。
- 成功修改后的 operation_id 可交给 undo_operation，整批撤销；详见[历史与恢复](HISTORY.md)。
- Python 接口支持 config_root 和 checker；默认检查，checker=None 关闭自动检查。自定义回调用法见[开发 API](../../runtime/API.md)。
- CLI 的 --config-root 选择检查所用配置目录；不会复制配置文件。带 --json 可读取结构化结果。

完整内存示例：`python -m examples.editing`。

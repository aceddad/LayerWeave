# 基础支撑 API

从 layerweave.support.api 导入读取、实例装配、写会话和通用反馈。默认配置从 layerweave 包内 configs 读取，也可传入自己的 config_root。所有能力在没有内置工具时仍可运行。CDUR 请求协议、编辑、历史、撤销、内容检测和 help 从对应[完整工具包](../tool/builtin/README.md)导入，不通过本模块转接。

本页说明 LayerWeave 自身的 Python 读写接口。若要配置出图、生视频等外部服务的 API KEY、地址与模型，使用[KEY 与连接说明](../tool/builtin/developer/keys/README.md)；技能选择和调用顺序见[工具区](../tool/README.md#选择与定位技能)。

首次用它开发自己的工具，可先读[AI 开发指导](../../../docs/build-with-layerweave/README.md)，选择嵌套时序、有序管理或工具自有表的示例，再按需查本页参数。配置路径、技能路由和发号词条的区别见[入口与标识](../../../docs/developer-conventions.md#入口路径与调度标识)。

## 统一写会话

一次事务中组合读取和修改：

```python
from layerweave.support.api import initialize_database, open_database, run_operation

path = initialize_database("scratch/example.sqlite3")
connection = open_database(path)
try:
    def work(write):
        project = write.create("project", {"name": "示例"})
        layer = write.create("layer", {"type": "text", "config_ref": "layers/text.toml"}, project_id=project["id"])
        return {"project": project, "layer": layer}

    result = run_operation(connection, work)
finally:
    connection.close()
```

work(write) 返回任意业务数据；run_operation 返回 operation_id、operation、ok、applied、data/error 和 checks。实际日志从写入收集，工具不传日志列表。业务变化或成功领号都会令 applied=true、operation.status=committed；仅有业务变化才写 changes 日志。失败回滚本批记录、发号和日志，不接管调用方未提交事务。

write 提供 read(kind, ...)、create(kind, data, ...)、update(kind, id, data, ...)、delete(kind, id, ...)；层、对象及 scoped 工具表使用 project_id，独立表按 id 定位。create/update/delete 返回实际记录或 None。read 传 id 返回一条，否则返回列表；JSON 字段整体替换。write.operation_id 是本次入口生成的操作编号。

希望直接处理异常时使用 `with transaction(connection) as write:`；成功自动提交，异常自动回滚。已有写会话内组合 write 原语或公开 *_in_session 函数，不嵌套独立操作。独立入口在已有 LayerWeave 会话内调用时直接抛出 ValueError，供外层回滚；不会返回藏在业务数据中的内层失败。父链无环按批次最终状态检查，编号、外键和必需存储列由支撑保证，内容规则不在此执行。

需要原始数值创建时使用 write.create_exact；需要恢复原身份时使用 write.restore(kind, id, record, project_id=..., undo_of=..., fields=...)。record 是完整历史快照或删除用的 None，fields 可限定已有记录要恢复的顶层字段，空列表不修改；这些接口仍通过本次会话维护结构、编号和日志。撤销冲突策略由工具决定，支撑不猜测覆盖。write.defer_references() 可将本次外键验证延迟到提交，以便恢复整批父子记录。

普通位置写入按轴精度落点，无精度时为 1e-6；改所属层会重新落点 begin/end，只改其他内容不会重写历史位置。精确创建/恢复保留原值。轴单位不自动换算。

## 增量读取业务日志

change_cursor(connection) 返回当前快照最后一个 changes.id，空日志返回 0。read_changes(connection, after=0, limit=100) 按递增编号读取后续业务日志，after/limit 为关键字参数。它们从 support.api 导入，不依赖 history 或任何其他工具包。

返回 changes、next_cursor、has_more。changes 使用原始日志字段：id（日志游标）、operation_id、kind、project_id、target_id、action、before_data、after_data、undo_of、created_at；JSON 快照已解码。limit 是日志行数软上限，页尾延伸至该次操作的末尾，可能超过 limit。只在调用方处理成功后保存 next_cursor，has_more=true 时继续读取；空页保留原游标。

使用 change_cursor 或上次返回的 next_cursor；手填到操作内部会报 cursor_inside_operation，超过当前日志末尾会报 cursor_ahead。不要使用 operation_id、时间戳或目标记录 id 代替游标。首次读取项目内容和取得游标必须在同一个 read_snapshot 内；[增量接入指导](../../../docs/build-with-layerweave/05-incremental-reading.md)给出调用次序。

返回全库托管业务记录的变化，包括工具表、bind 和撤销。没有项目过滤，以免丢掉跨项目关联和移动前后的信息；调用方依据前后快照判断影响范围。项目上下文 project_id 不总是目标主键的一部分，目标身份以对应 table_specs 的 scoped 约定为准。

该接口不创建日志、不删除日志、不追踪外部直接 SQL、结构登记或单独领号；记录写入附带的计数更新也不单列成项目事件。需要最新 max_id 时另外读取项目。监听使用没有待提交写入的读取连接；若在已有事务内调用，按统一读取约定使用该事务的可见状态。切换数据库或直接替换文件时重新载入初始快照，不能把另一个库的数字游标沿用过来。

## 工具表接入

register_tables(connection, definitions) 创建工具声明的表、追加列，或更新 logical_references/exchange 元信息；内部使用独立写会话，调用时连接没有待提交事务。已有列、身份和硬引用不变。table_specs(connection) 返回本数据库内置表与工具表的声明副本，普通读取不创建元数据表。

声明持久化后，write 原语、read_record、dispatch、历史和撤销都能识别新 kind，无需依赖工具代码。工具表默认自动发号，也可声明 id_source="provided"，创建时在 data.id 提供正整数。项目范围与簇成员分开管理；日志仍由真实写入生成。字段、引用、结构升级和业务边界统一见[工具表开发指导](../../../docs/build-with-layerweave/03-managed-tables.md)。

logical_references 只描述目标身份，不建立外键或阻止删除/撤销；exchange.on_copy 为 include/skip，由交换工具处理已有记录的复制。新元信息可给旧表补登记；省略时保留已登记值。声明用法和旧库接入步骤见[逻辑引用与复制策略](../../../docs/build-with-layerweave/03-managed-tables.md#逻辑引用与复制策略)。

## 发号与自定义身份

allocate(name, data=...) 在当前写会话中调度发号规则，连接由会话提供；只更新计数并返回身份，不写业务行。register_numbering(connection, definitions) 登记词条、计数位置和成员；numbering_entries(connection) 只读查询登记。register_numbering_rule(name, function) 登记本进程的规则函数，规则可复用 increment(entry, data)。完整声明、计数保护和示例见[编号模块](numbering/README.md)。

工具表的 provided 模式通过 data.id 接收正整数。未入簇的表只检查自身主键，允许与层、对象复用相同 (project_id, id)；加入同一计数范围的表共同遵守编号唯一约定。发号、业务记录和日志仍在同一事务内完成。

## 六个读写函数

| 调用 | 返回 |
|---|---|
| read_layer(connection, project_id, id) | 完整层字典，含直接装载的 objects 和各实体发出的 bind |
| read_object(connection, project_id, id) | 完整对象字典，含发出的 bind |
| load_layer(connection, project_id, id) | 对应 Layer 派生实例，objects 已装载为各自派生实例 |
| load_object(connection, project_id, id) | 对应 Object 派生实例 |
| save_layer(connection, project_id, layer) | 原子保存层、传入对象和发出关联，返回操作与检测结果 |
| save_object(connection, project_id, obj) | 原子保存对象和传入发出关联，返回操作与检测结果 |

read/load 不写数据或日志，不自动运行检测；目标不存在返回 None。完整层只包含直接装载对象，不递归子层或关联目标，因此关联环不会递归展开。read 的各部分来自同一个 SQLite 读取事务；已有事务时使用调用方事务，不替调用方提交。

read 返回保留 project_id/config_ref 的普通字典，不需要配置文件可用。load 才读取配置、按 class 路径导入对应 Python 类；配置或类不可用时抛出包含目标和配置路径的 ValueError，仍可通过 read 取得原始完整记录。配置应来自调用方信任的项目代码，因为 class 导入会执行模块代码。

项目摘要使用 read_project_index(connection, project_id)：返回 project 与层摘要列表，每个层带直属 object_count，不读取正文或配置文件。它提供一次读取事务内的平面数据；层级排列与纯文本展示由 [项目概览工具](../tool/builtin/usage/query/project_overview.py) 完成。

完整范围读取使用 read_project_details(connection, project_id, layer_id=None, layer_ids=None, begin=None, end=None)，可选参数用关键字传入。未指定层表示全项目；单层或多层均包含自身与全部子孙层，父子重选自动去重。layer_id 与 layer_ids 互斥，显式 layer_ids=[] 表示空选择。时间只筛选对象，所选范围内未命中的层也保留。原始数值相交筛选不转换轴、不量化查询值、不裁剪对象位置。

返回 project/scope/layers/missing_layer_ids。多层请求中的不存在编号列入 missing_layer_ids，其余有效子树继续读取；项目不存在或旧单层入口 layer_id 不存在时仍返回 None。scope.layer_ids 保留去重后的请求，scope.root_ids 给出有效起始层的树序。数据保持完整，读取不加载配置、不写日志。工具 project_details 增加树序、depth、本范围直属 object_count、counts 与缺失目标的逐条提示；compact=True 可生成文字/JSON 共用的精简视图，详见 [详细展开工具](../tool/builtin/usage/query/project_details.py)。

基础支撑的 save_layer/save_object 默认 checker=None，返回明确的未检查状态。需要默认内容检测时，使用 layerweave.tool.builtin.usage.records.save 的 save_layer_with_checks/save_object_with_checks；工具层原同名函数已移除。这两个包装复用基础保存能力，并可选接入已安装的检测包。

组合保存使用同样从 support.api 导出的 save_layer_in_session(write, project_id, layer, config_root=...) 和 save_object_in_session(write, project_id, obj, config_root=...)；config_root 使用关键字参数。它们返回完整记录，不提交、不检测、不回填输入实例或字典。使用返回记录继续操作，外层提交前编号仍是临时值。其他项目内容工具的组合入口与返回见[事务内组合](../../../docs/build-with-layerweave/04-composing-tools.md)。

## 通用只读查询
以下能力也经 layerweave.support.api 提供，供各类型工具复用：

| 调用 | 用途 |
|---|---|
| read_record(connection, kind, ...) | 现有单表 CRUD.read 的公开只读入口，支持 id 和等值 filters |
| read_snapshot(connection) | with 上下文中的读取快照；借用已有事务时不会替调用方提交 |
| query_objects(connection, project_id, layer_id=None, name=None, begin=None, end=None) | 参数化筛选对象记录；可选参数用关键字传入，name 是区分大小写的字面子串 |
| read_bindings(connection, kind, project_id, id, direction="both") | 按完整实体身份查询 outgoing/incoming/both 直接关联，direction 使用关键字传入 |
| read_layer_positions(connection, project_id, layer_id) | 返回层身份和直属对象的 id/begin/end；不存在返回 None，不加载正文或隐藏异常位置 |

位置查询采用相交语义：[begin,end)，begin=end 表示点查询，一端 None 表示该方向未限定。提供位置条件时排除无效区间；没有位置条件时不因此过滤记录。query_objects 不读取配置文件、不装载关联或换算单位；read_bindings 保留失效引用且不装载端点。

对象检索、关联分组和文字提取的业务整理放在对应工具中，完整用法见 [使用手册](../tool/builtin/usage/GUIDE.md)。SQL 只在存储层维护，工具不复制查询实现。

## 字典输入
save 同样接受完整或部分记录字典。新记录没有 id；已有 id 表示更新，目标不存在会返回失败，不改成新建。新字典记录需要 config_ref；已有记录省略 config_ref 则保留数据库原值。

```python
result = save_layer(connection, project_id, {
    "config_ref": "layers/text.toml", "name": "新层",
    "objects": [
        {"config_ref": "objects/text.toml", "information": {"text": "开场"}},
    ],
})
```

整层保存先发放层编号，再用这个编号保存所传 objects；因此嵌套字典中的对象可以由容器补齐 layer。将已有对象显式放入另一层的保存请求，会更新其所属层。单独 save_object 则使用对象自身的 layer，数据库要求它非空且实际存在。

字典按明确提供的字段更新；Python 实例保存其基础存储字段的当前值，并从实际类确定配置。缺少 objects/bind、空列表或列表中未带上的已有记录均不会触发删除。删除使用写会话的 delete，或 records 包的 dispatch。save 返回的 data 是保存后的完整记录，可能包含本次未修改的既有对象或关联。

整个保存只有一个 operation_id，数据与日志在同一个事务提交，检测在提交后执行一次。返回包含 ok、applied、operation_id、kind、project_id、data、checks。成功后回填输入的 id、对象 layer 和关联 id；失败不回填回滚掉的编号。检测异常不撤销成功的数据写入。

操作结果另由 operation 明确表达：status 为 committed（变更已提交）、unchanged（成功但没有变更）、read（只读成功）或 failed（本次未写入）。operation.changes 按执行顺序列出已提交的 action 和 target；失败批次不返回临时创建编号。原有 ok/applied/data/checks 保留。成功领号时另有 operation.numbering 列表：counter 为 kind/project_id/id/field，before/after 为计数，allocate 成功时还包括 entry、rule 和 identity；直接调用 increment 时这些附加项可能缺席。没有领号时省略 numbering，失败时不返回回滚掉的编号。changes 为空但 numbering 非空也是 committed，并显示“发号成功”；这类操作没有可撤销的业务日志。

内置诊断仍逐条放在 checks.issues，包含 severity、target、rule、message，可带 field。scope=direct 表示问题目标在本次操作中发生过修改，related 表示关联检查涉及但本次未直接修改的目标；主动 validate 使用 manual。checked_target 在规则执行目标与问题目标不同时补充，例如检查 layer 却发现其中一个 object 的配置缺失。scope 只说明检查范围，不判断问题新旧。

错误可附 code、allowed、suggestions、candidates、reference 等修正线索；候选仅用于提示，不自动替换输入。format_feedback(result) 可将操作结果与各条诊断分别格式化成编译器式文字；format_issue(issue) 格式化单条诊断，也适用于主动复查和只读工具。这两个函数均从 layerweave.support.api 导入。JSON 返回不依赖字段顺序，原有 JSON/退出码保持不变。完整内存示例为 `python -X utf8 -B examples/feedback.py`。

写入前先排除可判定无变化的字段，日志以实际存储的前后值为准。JSON 保留类型差异，普通 SQL 列接受数据库规范化；unchanged 不承诺从未执行 UPDATE。规则与 name=1 的例子见[什么算改动](storage/SCHEMA.md#什么算改动)。

## 配置与自定义类型
- 每份层/对象封装 TOML 必须明确声明自己的 type 和 class；一个 Python 类在同一配置根目录内只绑定一份配置。class 使用类定义处的“模块:类”，不继承父配置的类绑定。
- Python 实例保存时根据实际类确定配置，新建与更新一致；不再接受 config_ref 参数覆盖或 object_config_refs 下标映射。已有 id 的实例换用其他类，表示将该记录改为对应封装。
- 字典保存通过 config_ref 确定封装，已有字典省略引用则保留数据库原值。层的 type 从 TOML 读取；读回字典带有相同 type 可以直接再次保存，矛盾的 type 会使本次保存失败。
- save 需要对应配置可解析；缺失/无效配置的原始记录仍可通过写会话原语写入、通过 read 读取，再由独立检测报告。原始层新建若无法读取配置，须保留原数据已有的 type，接口不猜测。
- save/load 接受 config_root；records 包的保存与 dispatch 同样支持配置根目录。仅装载实际需要的 Python 类，不加载全部封装。
- 同一次调用复用配置索引和文件内容，下次调用重新读取；编辑配置后不会被长期缓存掩盖。
- 模型不持有 type 字符串、project_id/config_ref；Python 类是实例的类型，封装标识由 TOML 提供。自定义内容仍使用 information 或现有字段，不自动为新增 Python 属性创建数据库列。

派生示例为 [Title](../models/objects/title.py) 与 [标题配置](../configs/objects/title.toml)：Python 的 Title 继承 Text，配置的 title 继承 text，并明确绑定 Title。两者都不新增限制；TextLayer 接受 Title，文本汇集也会包含它。运行 `python -X utf8 -B examples/title.py` 可查看保存、重新装载和修改的过程。

新增普通封装只需类和配置。若从具体模块导入，不必修改统一模型导出入口。继承约定见 [配置说明](configuration/README.md)。

## 关联格式
模型的 bind 是发出的关联列表。新关联可以只提供目标三元组和说明：

```python
obj.bind.append({
    "target_kind": "layer", "target_project_id": other_project_id,
    "target_id": target_layer_id, "tips": "引用它的说明",
})
result = save_object(connection, project_id, obj)
```

来源由当前保存的实体补齐；读回和保存成功后，关联条目包含 id、source_kind/source_project_id/source_id、target_kind/target_project_id/target_id、tips。已有 id 更新原关联，不能借此改写别的实体持有的关联。目标失效时引用仍保留；安装的检测工具可报告问题，等级来自汇报配置。

指向当前实体的入向关联不混入 bind。需要时用 read_bindings，或 read_record 查询 bind 的 target_kind/target_project_id/target_id 条件。旧的 `[编号, 说明]` 简写不用于持久化。

## 提交后的可选检查

run_operation 和独立的基础 save_layer/save_object 接受 checker；省略或传 checker=None 时不执行内容检查。*_in_session 接口不接受 checker，检测统一交给最外层配置。checker(changes, read_record) 必须返回问题字典列表。检查异常或输出不合法标记 checks.status=failed，已经提交的操作仍是成功。

changes 包含 action、kind、project_id、id、before、after、change_id 和 operation_id；记录来自实际写入。read_record(kind, project_id=..., id=..., filters=...) 只提供读取。通用汇报使用 format_feedback、format_issue 和 diagnostic_report。

默认工具以 DEFAULT_CHECKER 为参数默认值，并调用 layerweave.support.providers.optional_checker；它在提交后静态寻找包 __init__.py 中的字面量 PROVIDERS，再按需导入声明的能力。没有提供者返回 not_run/not_configured；加载失败返回检查失败，不能伪装成写入失败。内容规则在[检测包](../tool/builtin/usage/validation/README.md)，等级和同因合并在[诊断说明](DIAGNOSTICS.md)。

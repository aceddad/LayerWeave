# LayerWeave 读写与工具开发入口

工具统一从 `runtime.api` 导入。数据读写先初始化数据库再打开连接；配置 help 不需要数据库。项目创建、单条删除和任意记录查询继续使用 dispatch。Python 3.11+，当前从项目 src/ 目录运行。

## 配置 help（查询支持能力）

read_support(view="overview", targets=None, config_root=DEFAULT_ROOT, include_source=False) 动态读取 configs/layers 与 configs/objects，包含子目录。四种 view：overview 总览层与兼容对象类；layers 层支持详情；objects 对象类支持详情；combined 层＋兼容对象类详情。后三项支持一个目标或目标列表；目标为 config_ref、唯一 type、完整 class 路径或唯一类名。它们均查询封装定义，不查询项目实例，不导入 Python 类。

返回 items 与逐项状态、issues；联合查看的共享对象说明放在 object_details，通过 accepted_objects 中的 config_ref 对应。默认展示继承合并后的 definition、lineage、fixed_contracts 和实际汇报等级；include_source=True 附带当前文件 source 原文。新增类和 TOML 后，下次查询自动发现；损坏配置逐项提示，其余继续。文字/JSON 入口为 tools.common.config_help，详见 [配置 help 说明](configuration/HELP.md)。

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

项目摘要使用 read_project_index(connection, project_id)：返回 project 与层摘要列表，每个层带直属 object_count，不读取正文或配置文件。它提供一次读取事务内的平面数据；层级排列与纯文本展示由 [项目概览工具](../tools/common/project_overview.py) 完成。

完整范围读取使用 read_project_details(connection, project_id, layer_id=None, layer_ids=None, begin=None, end=None)，可选参数用关键字传入。未指定层表示全项目；单层或多层均包含自身与全部子孙层，父子重选自动去重。layer_id 与 layer_ids 互斥，显式 layer_ids=[] 表示空选择。时间只筛选对象，所选范围内未命中的层也保留。原始数值相交筛选不转换轴、不量化查询值、不裁剪对象位置。

返回 project/scope/layers/missing_layer_ids。多层请求中的不存在编号列入 missing_layer_ids，其余有效子树继续读取；项目不存在或旧单层入口 layer_id 不存在时仍返回 None。scope.layer_ids 保留去重后的请求，scope.root_ids 给出有效起始层的树序。数据保持完整，读取不加载配置、不写日志。工具 project_details 增加树序、depth、本范围直属 object_count、counts 与缺失目标的逐条提示；compact=True 可生成文字/JSON 共用的精简视图，详见 [详细展开工具](../tools/common/project_details.py)。

## 通用只读查询

以下能力也经 runtime.api 提供，供各类型工具复用：

| 调用 | 用途 |
|---|---|
| read_record(connection, kind, ...) | 现有单表 CRUD.read 的公开只读入口，支持 id 和等值 filters |
| read_snapshot(connection) | with 上下文中的读取快照；借用已有事务时不会替调用方提交 |
| query_objects(connection, project_id, layer_id=None, name=None, begin=None, end=None) | 参数化筛选对象记录；可选参数用关键字传入，name 是区分大小写的字面子串 |
| read_bindings(connection, kind, project_id, id, direction="both") | 按完整实体身份查询 outgoing/incoming/both 直接关联，direction 使用关键字传入 |

位置查询采用相交语义：[begin,end)，begin=end 表示点查询，一端 None 表示该方向未限定。提供位置条件时排除无效区间；没有位置条件时不因此过滤记录。query_objects 不读取配置文件、不装载关联或换算单位；read_bindings 保留失效引用且不装载端点。

对象检索、关联分组和文字提取的业务整理放在对应工具中，完整用法见 [第一批工具](../../tools/README.md)。SQL 只在存储层维护，工具不复制查询实现。

## Python 实例的完整往返

```python
from contextlib import closing
from models import TextLayer, Text
from runtime.api import (
    initialize_database, open_database, dispatch,
    save_layer, load_layer, read_layer,
)

path = initialize_database("../scratch/example.sqlite3")
with closing(open_database(path)) as connection:
    result = dispatch(connection, {
        "action": "create", "kind": "project", "data": {"name": "示例"},
    })
    project_id = result["id"]
    layer = TextLayer(name="主线")
    result = save_layer(connection, project_id, layer)
    if not result["ok"]:
        raise RuntimeError(result["error"])

    # 层已有实际编号后构造对象。
    layer.objects.append(Text(layer=layer.id, information={"text": "初稿"}))
    result = save_layer(connection, project_id, layer)
    if not result["ok"]:
        raise RuntimeError(result["error"])

# 关闭并重开后，恢复为 TextLayer，内部对象是 Text。
with closing(open_database(path)) as connection:
    loaded = load_layer(connection, project_id, layer.id)
    loaded.objects[0].information["text"] = "修改后"
    result = save_layer(connection, project_id, loaded)
    complete_record = read_layer(connection, project_id, layer.id)
```

可直接运行不留下项目数据的示例：`python -X utf8 -B -m examples.read_write`。它创建临时数据库，经过三次打开/关闭验证落盘、装载、修改和关联保留。

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

字典按明确提供的字段更新；Python 实例保存其基础存储字段的当前值，并从实际类确定配置。缺少 objects/bind、空列表或列表中未带上的已有记录均不会触发删除。删除继续用 dispatch 的 delete。save 返回的 data 是保存后的完整记录，可能包含本次未修改的既有对象或关联。

整个保存只有一个 operation_id，数据与日志在同一个事务提交，检测在提交后执行一次。返回包含 ok、applied、operation_id、kind、project_id、data、checks。成功后回填输入的 id、对象 layer 和关联 id；失败不回填回滚掉的编号。检测异常不撤销成功的数据写入。

操作结果另由 operation 明确表达：status 为 committed（变更已提交）、unchanged（成功但没有变更）、read（只读成功）或 failed（本次未写入）。operation.changes 按执行顺序列出已提交的 action 和 target；失败批次不返回临时创建编号。原有 ok/applied/data/checks 保留。

内置诊断仍逐条放在 checks.issues，包含 severity、target、rule、message，可带 field。scope=direct 表示问题目标在本次操作中发生过修改，related 表示关联检查涉及但本次未直接修改的目标；主动 validate 使用 manual。checked_target 在规则执行目标与问题目标不同时补充，例如检查 layer 却发现其中一个 object 的配置缺失。scope 只说明检查范围，不判断问题新旧。

错误可附 code、allowed、suggestions、candidates、reference 等修正线索；候选仅用于提示，不自动替换输入。format_feedback(result) 可将操作结果与各条诊断分别格式化成编译器式文字；format_issue(issue) 格式化单条诊断，也适用于主动复查和只读工具。这两个函数均从 runtime.api 导入。JSON 返回不依赖字段顺序，原有 JSON/退出码保持不变。完整内存示例为 `python -X utf8 -B -m examples.feedback`。

无变化的字段不会执行 UPDATE。JSON 内容按解码后的实际类型比较，`1`、`1.0`、`true` 互相变化会被记录；字典键顺序不影响结果。普通 SQL 数值列仍遵循存储的数值语义，例如 begin=1 与已有的 1.0 不产生额外修改。

## 在事务内计算写入请求

dispatch 除了接收字典/列表，也接受 Python 请求工厂。核心先开启 BEGIN IMMEDIATE，再把 read_record 查询函数交给工厂；工厂返回一个请求字典或列表，实际写入、日志和提交后检测仍由核心处理。

```python
def plan(read_record):
    obj = read_record("object", project_id=project_id, id=object_id)
    return {"action": "update", "kind": "object", "project_id": project_id,
            "id": object_id, "data": {"begin": obj["begin"] + 3, "end": obj["end"] + 3}}

result = dispatch(connection, plan)
```

这样读取和计算使用本次写事务的状态，适用于接续新增、批量平移等工具。工厂只读取并构建请求，不自行写入或开启嵌套事务。纯查询继续用只读 API。JSON CLI 的原有字典/列表协议保持不变。

自定义工具可从 runtime.api 导入 DEFAULT_CHECKER 作为可选 checker 参数的默认值：省略时使用核心检测，显式 None 关闭检测。工厂失败、请求失败时整体回滚；检测失败不撤销已提交操作。

位置工具与 dispatch/save/CRUD 的对象写入共用 runtime.positions：按最近声明的轴取得 precision，没有轴或该轴没有精度时使用 1e-6，按最近刻度落点，中点远离零。写入位置或更改所属层时归一对应位置；只改名字/内容不重写历史坐标。保存返回值、日志与回填的 Python 实例使用实际落点。检查按同样的整数刻度比较旧、新记录；原始读取和范围查询保持数值读取，不换算单位、不批量修改旧数据。

检查是否执行继续由原有约束控制。汇报等级独立配置在 configs/logging/diagnostics.toml：error/warn/none，未配置默认 warn；none 只隐藏输出，无法执行的检查仍使 checks.status=partial。缺字段与字段类型错误采用不同 code，模型/动作的 source/data 缺失可静音而类型错误仍报告。同一对象同一配置失败合并成一条，affected_checks 保留受影响检查。文字输出只显示操作结果和逐条问题。

## 配置与自定义类型

- 每份层/对象封装 TOML 必须明确声明自己的 type 和 class；一个 Python 类在同一配置根目录内只绑定一份配置。class 使用类定义处的“模块:类”，不继承父配置的类绑定。
- Python 实例保存时根据实际类确定配置，新建与更新一致；不再接受 config_ref 参数覆盖或 object_config_refs 下标映射。已有 id 的实例换用其他类，表示将该记录改为对应封装。
- 字典保存通过 config_ref 确定封装，已有字典省略引用则保留数据库原值。层的 type 从 TOML 读取；读回字典带有相同 type 可以直接再次保存，矛盾的 type 会使本次保存失败。
- save 需要对应配置可解析；缺失/无效配置的原始记录仍可通过 dispatch/CRUD 写入、通过 read 读取，再由独立检测报告。原始层新建若无法读取配置，须保留原数据已有的 type，接口不猜测。
- save/load/dispatch 接受 config_root；默认检测使用同一个目录。仅装载实际需要的 Python 类，不加载全部封装。
- 同一次调用复用配置索引和文件内容，下次调用重新读取；编辑配置后不会被长期缓存掩盖。
- 模型不持有 type 字符串、project_id/config_ref；Python 类是实例的类型，封装标识由 TOML 提供。自定义内容仍使用 information 或现有字段，不自动为新增 Python 属性创建数据库列。

派生示例为 [Title](../models/objects/title.py) 与 [标题配置](../../configs/objects/title.toml)：Python 的 Title 继承 Text，配置的 title 继承 text，并明确绑定 Title。两者都不新增限制；TextLayer 接受 Title，文本汇集也会包含它。运行 `python -X utf8 -B -m examples.title` 可查看保存、重新装载和修改的过程。

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

来源由当前保存的实体补齐；读回和保存成功后，关联条目包含 id、source_kind/source_project_id/source_id、target_kind/target_project_id/target_id、tips。已有 id 更新原关联，不能借此改写别的实体持有的关联。目标失效时引用仍保留，检测报告 warn。

指向当前实体的入向关联不混入 bind。需要时用 dispatch 查询 bind 的 target_kind/target_project_id/target_id 条件。旧的 `[编号, 说明]` 简写不用于持久化。

## JSON CLI 完整读取

原有 CRUD 请求保持兼容。read 的单条 layer/object 可加 full=true：

```json
{"action":"read","kind":"layer","project_id":1,"id":1,"full":true}
```

默认 read 仍返回单表记录；full 只用于指定 id，不用于过滤列表。实例保存与整层组合保存通过 Python API 调用，CLI 的写入仍使用已有 create/update/delete。

## 实现放置

- api.py：工具导入入口，避免工具依赖内部实现路径。
- storage/assembly.py：组合数据库记录，不依赖配置。
- storage/models.py：记录与 Python 类的适配、按需导入。
- storage/save.py：组织整层/对象写入，复用原 CRUD。
- operation.py：CRUD 与组合保存共用事务、日志编号和检测入口。
- configuration/ 与 validation/：继续负责配置与约束。

业务小工具放在 src/tools/<内容类型>/，共用工具放在 src/tools/common/，具体目录按实际工具需要创建。它们调用上述 API；核心不反向导入工具。两批内部工具与开发指南见 [工具说明](../../tools/README.md)。

# LayerWeave 读写与工具开发入口

工具统一从 `runtime.api` 导入。先初始化数据库，再打开连接；项目创建、单条删除和任意记录查询继续使用 dispatch。Python 3.11+，当前从项目 src/ 目录运行。

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

完整范围读取使用 read_project_details(connection, project_id, layer_id=None, begin=None, end=None)，可选参数用关键字传入。未指定层表示全项目，指定层包含自身与全部子孙层；时间条件共用原始数值相交筛选，不转换轴或量化查询值。返回 project/scope/layers，层内带完整 objects 与发出关联。时间筛选保留必要父路径，未命中返回空 layers；不存在项目/指定层返回 None。层级排列和文本输出见 [详细展开工具](../tools/common/project_details.py)。

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
    "type": "text", "config_ref": "layers/text.toml", "name": "新层",
    "objects": [
        {"config_ref": "objects/text.toml", "information": {"text": "开场"}},
    ],
})
```

整层保存先发放层编号，再用这个编号保存所传 objects；因此嵌套字典中的对象可以由容器补齐 layer。将已有对象显式放入另一层的保存请求，会更新其所属层。单独 save_object 则使用对象自身的 layer，数据库要求它非空且实际存在。

字典按明确提供的字段更新；Python 实例保存其基础存储字段的当前值。缺少 objects/bind、空列表或列表中未带上的已有记录均不会触发删除。删除继续用 dispatch 的 delete。save 返回的 data 是保存后的完整记录，可能包含本次未修改的既有对象或关联。

整个保存只有一个 operation_id，数据与日志在同一个事务提交，检测在提交后执行一次。返回包含 ok、applied、operation_id、kind、project_id、data、checks。成功后回填输入的 id、对象 layer 和关联 id；失败不回填回滚掉的编号。检测异常不撤销成功的数据写入。

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

位置工具在工厂内按最近声明的轴取得 precision，并对生成的坐标落点。直接 dispatch/save_layer/save_object 保存调用方原值，不自动归一坐标。配置声明字段缺失时，相关内容检测给 warn，保存仍然成功；文本汇集也会报告缺少 text 的条目。

## 配置与自定义类型

- 新 Python 实例可省略 config_ref：按实际 Python 类的模块路径查找唯一直接声明该 class 的配置。有多个或没有对应配置时，请明确传 config_ref。
- 配置继承得到同一个 class 的用途别名不参与自动猜测。例如 title 继承 text 并复用 Text，创建 title 时显式传 `config_ref="objects/title.toml"`。
- 已有对象保存默认保留数据库的原 config_ref，因此读取 title 为 Text 后再保存仍是 title。
- 整层保存可传 `object_config_refs={0: "objects/title.toml"}`，按 objects 下标指定某个对象的配置。使用字典对象时也可直接带 config_ref。
- save/load 接受 config_root；配置根目录与检测使用同一个目录。仅导入当前需要的类，不加载全部封装。
- 同一次保存的类与配置匹配使用共享索引；下一次调用重新构建，配置编辑不会被长期缓存掩盖。
- 模型仍不持有 project_id/config_ref；Python 工具保留明确的项目上下文。普通子类的数据扩展使用 information 或现有字段；本接口不会自动为新增 Python 属性创建数据库列。

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

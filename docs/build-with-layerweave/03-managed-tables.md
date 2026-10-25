# 用法三：让工具自己的表接入统一管理

工具可以声明适合自己业务的数据表，沿用 LayerWeave 的读写、事务、编号和改动日志。工具表无需继承 Layer/Object，也无需提供类绑定或 config_ref。[返回开发指导](README.md)。

## 声明一张表

先用 initialize_database 准备数据库，再用 open_database 打开连接。以下 connection 没有待提交事务：

```python
from layerweave.support.api import register_tables, table_specs

register_tables(connection, {
    "review_note": {
        "fields": {
            "object_id": {"type": "INTEGER", "nullable": False},
            "note": {"type": "TEXT", "default": ""},
            "details": {"type": "JSON", "default": {}},
        },
        "references": [{"fields": ["project_id", "object_id"], "kind": "object"}],
    },
})

spec = table_specs(connection)["review_note"]
```

review_note 是调用接口时的 kind。默认建立 tool_review_note 表；如有需要，在声明中用 table 指定其他表名。声明保存在本数据库的 _layerweave_tables 中，按需创建这张元数据表，原有五张表保持不变。

重开连接、通过 CLI 读取或卸下工具代码后，支撑仍可读取表声明与数据；历史和撤销工具也能据此工作。不会自动删除工具表或安装其他工具的表，每个数据库分别管理自己的声明。

## 声明的内容

| 项 | 含义 |
|---|---|
| fields | 可写列的名称与声明；简写 "TEXT" 等同于 {"type": "TEXT", "nullable": True} |
| 列 type | INTEGER、REAL、TEXT、JSON 或 BLOB；JSON 使用文本存储，BLOB 使用字节存储 |
| 列 nullable | 默认 true；false 交给 SQLite 保证列非空，不是 JSON 内部内容约束 |
| 列 default | 可选的固定默认值；JSON 可用字典、列表等 JSON 值 |
| scoped | 默认 true，记录使用 (project_id, id)，并引用实际存在的项目 |
| id_source | auto（默认）或 provided；provided 创建时由 data.id 提供正整数 |
| references | 显式外键：fields 按目标主键顺序列出本表列，kind 指定目标种类 |
| logical_references | 默认 []；与 references 同样的写法，只声明引用含义，不建立外键 |
| exchange | 可选的交换元信息；on_copy 为 include（默认）或 skip，详见下文 |
| table | 可选的物理表名，默认 tool_ 加上 kind |

kind、表名、字段名使用字母开头的字母、数字和下划线。id/project_id 身份列由支撑建立，不放进 fields；内置表和种类保持原定义。普通列沿用 SQLite 的存储类型行为，BLOB 写入要求字节类型，业务内容的检查由工具决定。

默认 auto 的 scoped 表加入 project_entities，与本项目的层、对象共用 projects.max_id；可将新表登记到其他发号词条。provided 的 scoped 表只按项目定位，不自动加入簇。未入簇的 auto 独立表使用本表递增 id；provided 独立表由调用方提供正整数，独立表调用时不传 project_id。这类表的历史按 kind/id 或 operation_id 查询，不自动根据其业务字段归入某个项目。

自动发放的已提交编号不因删除或撤销创建而回收；provided 表由工具保证不把历史身份分配给无关记录，恢复保留原编号；失败事务内的发号与其他变更一起回滚。JSON 字段按实际内容类型比较，修改时整体替换。新表中即使有 begin、end、axis 等列，也只按自己的字段声明处理，不自动套用对象的位置规则。

复用层编号的视图表、自定义发号簇和规则函数见[编号模块](../../src/layerweave/support/numbering/README.md)。簇成员集中登记在发号词条中，恢复据此区分同簇占用与独立工具身份。

## 二进制字段 BLOB

在 fields 中声明 `"payload": "BLOB"` 即可。Python 的 write.create/update/create_exact/restore 接收 bytes、bytearray、memoryview，保存并读取为 bytes；不把字符串隐式当作二进制。可空列允许 None，None 与空字节 b"" 不同。BLOB 作为完整字段比较、更新和恢复，平台不解释字节代表的业务内容。

默认值只允许省略或 None；空字节也是写入值，不用作默认值。nullable=False 不能配 default=None。已有表追加 BLOB 时使用可空列；新增非空列仍需遵守原来的迁移限制。

dispatch、CLI、MCP 和交换文档中的 BLOB 字段用标准 Base64 字符串，null 保持 null。例如：

```json
{"action":"create","kind":"binary_cache","project_id":1,"data":{"payload":"AAH/"}}
```

这要求 binary_cache 已登记 payload 为 BLOB，项目 1 已存在；对应的 Python 字节是 b"\x00\x01\xff"。非法 Base64 返回 blob_base64 并指出字段；低层写会话收到字符串则返回 blob_type。只转换明确声明的 BLOB 列，普通 TEXT/JSON 内的字符串和字典保持原样；information、axis 等 JSON 字段不因此允许嵌入字节。

通用 filters 暂不支持 JSON/BLOB 列（包括空值筛选），传入时返回 unknown_filter 及可用字段；可按身份或其他普通列查询。Python 查询、read_changes、历史快照和冲突详情中的二进制仍为 bytes；自行生成 JSON 时可使用公共辅助函数：

```python
import json
from layerweave.support.api import binary_json_default

text = json.dumps(record, ensure_ascii=False, default=binary_json_default)
```

CLI/MCP 已处理该转换。交换导出直接返回可 JSON 序列化的文档，基线指纹包含完整二进制内容；不以显示摘要代替字段值。

日志的前后快照以 Base64 保存 BLOB，读取时根据活动或退役声明还原；不要只复制 changes 而遗漏其声明目录。历史查看保留当时的字段集合；只有恢复到当前活动结构时才补后来新增列的默认值。完整快照会复制未修改的其他字段；例如 4096 字节经 Base64 为 5464 字节，一万条向量更新的前后值约新增 104.2 MiB 日志，尚未计入正文等字段。

## 引用与事务

目标按项目管理时，引用的两个源列依次对应目标 project_id、id，例如上例的 ["project_id", "object_id"]。也可以声明 ["other_project_id", "object_id"]，把第一列指向另一个项目。目标使用独立 id 时只需一个源列。

引用列使用 INTEGER，目标可以是现有内置业务表、已登记工具表或同批声明的工具表，也可引用自身。引用中有 NULL 时沿用 SQLite 的可空引用行为；需要必填时将相应列声明为 nullable=false。实际外键没有隐式级联删除或更新，调用方明确组合要修改的记录。

下面假定 project_id 和 object_id 来自实际存在的项目与对象：

```python
from layerweave.support.api import run_operation

def work(write):
    write.update("object", object_id, {"tips": "待复核"}, project_id=project_id)
    return write.create("review_note", {
        "object_id": object_id, "note": "检查这一段的位置", "details": {"resolved": False},
    }, project_id=project_id)

result = run_operation(connection, work)
```

对象修改和工具记录创建共用一个 operation_id。支撑从真实修改生成 before/after 日志；任何一步失败，整批数据、编号和日志一起回滚。write.read/update/delete/restore 同样接受已登记 kind；普通读取使用 read_record，现有 dispatch 和 JSON CLI 也可直接使用这个 kind。

基础支撑默认不运行内容检查；原有检测包不会凭表声明自动生成语义规则。工具可按自己的需要提供 checker。结构检查与内容检查的分工继续见[API](../../src/layerweave/support/API.md#提交后的可选检查)。

## 逻辑引用与复制策略

有些记录只是附着状态：例如一行折叠状态与一个层共用编号，但删层时允许状态暂留，撤销删层后还能重新使用它。这时用 logical_references，不要为了让交换工具识别编号而添加硬外键。

以下两张示例表分别复用层、对象的身份：

~~~python
register_tables(connection, {
    "layer_state": {
        "id_source": "provided",
        "fields": {"fold": {"type": "TEXT", "default": ""}},
        "logical_references": [{"fields": ["project_id", "id"], "kind": "layer"}],
    },
    "read_state": {
        "id_source": "provided",
        "fields": {"reads": {"type": "JSON", "default": {}}},
        "logical_references": [{"fields": ["project_id", "id"], "kind": "object"}],
        "exchange": {"on_copy": "skip"},
    },
})
~~~

声明层、对象以外的工具 kind 也一样。引用源列须为 INTEGER，数量和顺序对应目标主键；目标 kind 须已登记或在同批声明中。普通业务列同样可以声明，例如 ["project_id", "object_id"]；不要求一定复用 id。exchange 的 refs 用最后一列作为引用名，同一名称不能有互相矛盾的引用声明。

| 行为 | references | logical_references |
|---|---|---|
| 建立 SQL 外键，保证目标存在 | 是 | 否 |
| 参与删除和恢复的引用限制 | 是 | 否 |
| 交换时发现相关记录、转换已声明编号 | 是 | 是 |

逻辑引用允许目标暂时不存在，不自动清理残留状态，也不触发级联操作。scoped 表原有的 project 外键仍在；删除整个项目时，调用方仍需处理其工具记录。

交换工具复制时，层编号由 8 变为 21，引用该层的 layer_state.id 也变为 21。找不到来源目标的映射时，沿用交换的外部引用规则，默认跳过并报告；不会仅因目标库恰好有一个 8 就绑定过去。

on_copy=skip 表示这张表的已有记录不随交换复制，适合已读进度、临时选择等状态；include 表示参与正常复制，并不保证引用不成立时也强行写入。skip 不限制普通 CRUD、update/delete 或全新数据创建。交换以“op=add 且节点带正整数旧 id”识别复制；全新 provided 记录的目标编号放在 data.id，或通过 refs 取得，节点不填旧 id。

导出仍保留这些状态记录和表声明，便于原项目更新；导入复制时逐条报告 copy_policy、effect=skipped。工具不解析 JSON/TEXT 内容中的隐含编号。若 reads 内保存了旧对象编号，选择整行不复制可以让新项目重新开始记录已读状态；仅重映射主键不会转换这些内容。文件示例与反馈字段见[交换格式](../../src/layerweave/tool/builtin/usage/exchange/FORMAT.md#工具表)。

目前逻辑引用的收集、重映射和 on_copy 由交换包消费；普通 copy_subtree 等其他工具的范围没有因此扩大。需要其他复制方式时，在对应工具中显式接入这些声明。

## 历史、撤销与升级

安装 history 包后，read_history 支持工具 kind；安装 undo 包后，undo_operation 会将一个操作中的核心记录和工具记录一起恢复。更新仍按原操作改变的顶层字段比较冲突，JSON 列作为整体；创建、删除按整条记录比较。声明的硬引用参与恢复判断，后来的工具记录通过硬引用依赖某个目标时，会阻止把目标独自撤销掉；逻辑引用不产生这种限制。

register_tables 在独立的统一写会话内原子执行。重复相同声明可直接调用；升级时传入完整声明，并在 fields 中追加新列。新增非空列提供默认值，以保留现有行。已有列、表名、身份形式、id_source 和硬引用保持不变；删列、改类型、改硬引用及接管已有未登记表，需要另行明确迁移方案。

logical_references 和 exchange 可以对已有表补充或修改，只更新 _layerweave_tables 内的声明，不重建业务表。旧库缺少这两项时，读取默认是 [] 和 on_copy=include；省略它们的旧 register_tables 调用会保留已经登记的值。确需清除时，在完整声明里显式传 logical_references=[] 或 exchange={"on_copy":"include"}。

修改 Python 声明后，工具应在初始化或显式升级阶段对旧库再次调用 register_tables，完成后再导出。仅修改源代码不会改变库内声明；只读查询也不会替工具升级。交换导入准备表时可补入新逻辑引用，但会保留目标已有引用，任一方声明 skip 就保留 skip；解除元信息应由开发者明确登记，不能靠一份旧导出文件覆盖。

声明维护不写成普通 changes 日志，也不由内容撤销回退。旧日志保留原始快照；恢复时为后来新增的列补上声明默认值，并继续遵守原有冲突判断。注册失败时，新建表、新增列和声明一起回滚。

## 注销托管

```python
from layerweave.support.api import unregister_tables, retired_tables

result = unregister_tables(connection, ["binary_cache"])
archive = retired_tables(connection)
```

与 register_tables 一样，需要无待提交事务的连接。参数是工具 kind 的列表，不是 SQL 表名；不能注销 project/layer/object/bind/change。一次调用原子地将活动定义移入独立的 _layerweave_retired_tables，并从发号词条的 members 移除这些 kind。计数不回退，计数来源有效的空发号词条仍保留；声明维护不写业务 changes，也不作为普通撤销操作。

返回 retired 列表，每项含 kind、table、retired_at；already_retired 和 not_registered 分别列出已经退出、从未登记的 kind。重复注销不删除其他内容。retired_tables 返回 kind 到 {definition, retired_at} 的字典；旧库没有退役目录时返回空字典，读取不建表。table_specs 继续只返回活动声明。

**注销可以处理非空表，但不会删除或清空物理表、索引、外键及文件。** 是否清理这些内容由外部工具决定。非空 scoped 表只要仍引用某项目，该项目就不能删除；指向层/对象的硬外键同样保留。失败时会说明仍有已退出托管的物理表引用它，诊断核对当前物理外键，仅在失败时执行。

批次外仍活动的 references、logical_references 若引用本批 kind，需要先处理，或将引用表一并注销。被发号词条用作 counter 来源的表不能直接注销；先明确处理对应发号依赖。依赖失败返回 table_dependencies，本批目录与发号成员保持原状，不自动级联注销其他表。

退出后通用 CRUD、恢复和重新登记该 kind 返回 retired_kind。历史可按 kind、project_id/id 或 operation_id 查询，即使物理表后来被外部删除；read_changes 也保留历史。普通撤销涉及任一退役 kind 时，整批在写入前停止，即使该目标的中间变化已抵消；其他无关操作仍可执行。

退役 kind 在本数据库内保留历史含义，不能复用或重新接管；另一数据库不受此名称限制。原物理表被外部删除后，不同的新 kind 可以使用该物理表名；原表仍存在时，继续拒绝自动接管未登记现存表。退役定义保持冻结，不根据外部后来的 DDL 重写历史。

卸下工具代码、删除项目或清空工具表都不会自动注销。退出托管后的直接 SQL/DDL 由外部工具负责，平台不追踪其变化。BLOB/退役功能自 0.7.10b1 起提供；0.7.9b3 及更早版本不能继续写入或撤销启用了这些能力的库。

完整例子见 [binary_tool_tables.py](../../examples/binary_tool_tables.py)，演示字节写读、撤销重做、JSON 交换、注销以及物理表保留和退役历史读取：

```sh
python -X utf8 -B examples/binary_tool_tables.py
```

## 接入后的范围

工具表获得记录级读写、真实变更日志、事务和按操作恢复能力。层树查询、子树复制/搬移、实例 load/save 和 bind 的层/对象语义继续保持原有范围；工具表的内容不会自动变成层或对象。

若工具表的数据应随某层交换复制，声明硬引用或逻辑引用；其他剪切、复制或生成关联的业务，由对应工具显式组合现有原语，使用同一写会话完成。支撑不根据列名猜测业务归属。文件、KEY 配置与缓存仍可由工具单独管理，按需选择要纳入业务库的数据。

完整的临时数据库示例：

```sh
python -X utf8 -B examples/tool_tables.py
```

该[示例](../../examples/tool_tables.py)实际执行混合修改、历史查询、撤销、重做和关闭重开；不写用户项目数据库。

[逻辑引用示例](../../examples/logical_references.py)演示编号错开后状态跟随新层、已读记录不复制，以及整批撤销。运行 python -X utf8 -B examples/logical_references.py。

实际工具接入可参考[版本登记工具](../../src/layerweave/tool/builtin/developer/versions/README.md)：它声明独立的 component_version 表，通过公共 register_tables、run_operation 和 read_record 完成管理，不修改 core/support，也不依赖历史或撤销包才能运行。

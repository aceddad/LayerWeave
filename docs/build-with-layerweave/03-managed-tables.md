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
| 列 type | INTEGER、REAL、TEXT 或 JSON；JSON 使用文本存储并自动编解码 |
| 列 nullable | 默认 true；false 交给 SQLite 保证列非空，不是 JSON 内部内容约束 |
| 列 default | 可选的固定默认值；JSON 可用字典、列表等 JSON 值 |
| scoped | 默认 true，记录使用 (project_id, id)，并引用实际存在的项目 |
| id_source | auto（默认）或 provided；provided 创建时由 data.id 提供正整数 |
| references | 显式外键：fields 按目标主键顺序列出本表列，kind 指定目标种类 |
| logical_references | 默认 []；与 references 同样的写法，只声明引用含义，不建立外键 |
| exchange | 可选的交换元信息；on_copy 为 include（默认）或 skip，详见下文 |
| table | 可选的物理表名，默认 tool_ 加上 kind |

kind、表名、字段名使用字母开头的字母、数字和下划线。id/project_id 身份列由支撑建立，不放进 fields；内置表和种类保持原定义。普通列沿用 SQLite 的存储类型行为，业务内容的检查由工具决定。

默认 auto 的 scoped 表加入 project_entities，与本项目的层、对象共用 projects.max_id；可将新表登记到其他发号词条。provided 的 scoped 表只按项目定位，不自动加入簇。未入簇的 auto 独立表使用本表递增 id；provided 独立表由调用方提供正整数，独立表调用时不传 project_id。这类表的历史按 kind/id 或 operation_id 查询，不自动根据其业务字段归入某个项目。

自动发放的已提交编号不因删除或撤销创建而回收；provided 表由工具保证不把历史身份分配给无关记录，恢复保留原编号；失败事务内的发号与其他变更一起回滚。JSON 字段按实际内容类型比较，修改时整体替换。新表中即使有 begin、end、axis 等列，也只按自己的字段声明处理，不自动套用对象的位置规则。

复用层编号的视图表、自定义发号簇和规则函数见[编号模块](../../src/layerweave/support/numbering/README.md)。簇成员集中登记在发号词条中，恢复据此区分同簇占用与独立工具身份。

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

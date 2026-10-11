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
| references | 显式外键：fields 按目标主键顺序列出本表列，kind 指定目标种类 |
| table | 可选的物理表名，默认 tool_ 加上 kind |

kind、表名、字段名使用字母开头的字母、数字和下划线。id/project_id 由支撑管理，不放进 fields；内置表和种类保持原定义。普通列沿用 SQLite 的存储类型行为，业务内容的检查由工具决定。

scoped=true 的表与本项目的层、对象共用 projects.max_id；所有这些记录共同占用项目编号空间。scoped=false 使用本表独立递增的 id，调用时不传 project_id；这类表的历史按 kind/id 或 operation_id 查询，不自动根据其业务字段归入某个项目。

已提交的编号不因删除或撤销创建而回收，恢复保留原编号；失败事务内的发号与其他变更一起回滚。JSON 字段按实际内容类型比较，修改时整体替换。新表中即使有 begin、end、axis 等列，也只按自己的字段声明处理，不自动套用对象的位置规则。

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

## 历史、撤销与升级

安装 history 包后，read_history 支持工具 kind；安装 undo 包后，undo_operation 会将一个操作中的核心记录和工具记录一起恢复。更新仍按原操作改变的顶层字段比较冲突，JSON 列作为整体；创建、删除按整条记录比较。声明的引用参与恢复判断，后来的工具记录引用了某个目标时，会阻止把目标独自撤销掉。

register_tables 在独立的统一写会话内原子执行。重复相同声明可直接调用；升级时传入完整声明，并在 fields 中追加新列。新增非空列提供默认值，以保留现有行。已有列、表名、身份形式和引用保持不变；删列、改类型、改引用及接管已有未登记表，需要另行明确迁移方案。

声明维护不写成普通 changes 日志，也不由内容撤销回退。旧日志保留原始快照；恢复时为后来新增的列补上声明默认值，并继续遵守原有冲突判断。注册失败时，新建表、新增列和声明一起回滚。

## 接入后的范围

工具表获得记录级读写、真实变更日志、事务和按操作恢复能力。层树查询、子树复制/搬移、实例 load/save 和 bind 的层/对象语义继续保持原有范围；工具表的内容不会自动变成层或对象。

若工具表的数据应随某层复制、剪切或生成关联，由对应工具显式组合现有原语，使用同一写会话完成。支撑不根据列名猜测业务归属。文件、KEY 配置与缓存仍可由工具单独管理，按需选择要纳入业务库的数据。

完整的临时数据库示例：

```sh
python -X utf8 -B examples/tool_tables.py
```

该[示例](../../examples/tool_tables.py)实际执行混合修改、历史查询、撤销、重做和关闭重开；不写用户项目数据库。

实际工具接入可参考[版本登记工具](../../src/layerweave/tool/builtin/developer/versions/README.md)：它声明独立的 component_version 表，通过公共 register_tables、run_operation 和 read_record 完成管理，不修改 core/support，也不依赖历史或撤销包才能运行。

# 自定义 ID 与发号调度

本模块属于基础支撑，供开发者通过 Python 使用。工具表可以自行提供正整数 ID，也可以使用登记的发号词条。发号只更新计数并返回身份，业务记录和日志仍由统一写入口保存。恢复保留原身份，不重新发号。

## 最小用法：视图记录复用层编号

以下 connection 是已初始化的数据库连接；layer_id 和 project_id 来自已有层。登记表结构时连接没有待提交事务：

```python
from layerweave.support.api import register_tables, transaction

register_tables(connection, {
    "view_state": {
        "id_source": "provided",
        "fields": {"collapsed": {"type": "INTEGER", "default": 0}},
        "references": [{"fields": ["project_id", "id"], "kind": "layer"}],
    },
})

with transaction(connection) as write:
    view = write.create("view_state", {"id": layer_id, "collapsed": 1}, project_id=project_id)
```

scoped 默认为 true，因此身份仍为 (project_id, id)。id_source="provided" 要求创建时 data.id 是正整数，不自动发号，也不默认加入任何簇。独立身份用 scoped=false，创建时不传 project_id。其他数据字段保持原有声明方式；id/project_id 不放进 fields。

读取、更新、删除和恢复继续按原接口传 id/project_id。id 不可作为普通内容更新；业务需要换身份时明确删除/创建或迁移。write.create_exact 同样支持 provided，JSON dispatch 使用 data.id。支撑不建立永久编号占用名单；外部工具负责不把历史身份分配给不相干的新记录，恢复遇到占用或后续修改仍报告冲突。显式外键仍需满足，所以引用层的视图表会阻止单独删除被引用层，调用方在同一事务中明确处理两条记录。

id_source 默认 auto：未加入词条的独立表继续由 SQLite 自增；按项目的自动发号工具表默认加入 project_entities。scope 仅表达主键范围，自定义 ID 的 scoped 表不会因此自动加入簇。旧工具表缺少 id_source 时沿用 auto，原数据和日志不重编号。

## 只取一个编号

```python
from layerweave.support.api import allocate, transaction

with transaction(connection):
    identity = allocate("project_entities", data={"project_id": project_id})
# identity 形如 {"project_id": 1, "id": 8}，编号以实际返回值为准。
```

allocate 不要求 connection 参数；它从当前 transaction/run_operation 的写会话取得连接。没有写会话时会报错。数据库上下文只由调用方开启一次，不写入登记表，也不由调度器另开数据库。

普通 auto 表的 write.create 已在内部调用相应发号流程，不用提前领号。需要显式先领号再创建时，将目标表设为 provided，并将它加入相应词条，然后用 identity["id"] 和 identity.get("project_id") 分别传入创建接口。

allocate 本身不创建层、对象或工具记录，也不生成普通 changes 业务日志；它的计数变更跟随当前事务提交。事务失败一起回滚，成功领取但未用于记录的号码保留为空号。run_operation 的 applied/changes 描述业务记录变化，所以仅调用 allocate 时可能返回 applied=false；领取结果在 data 中，不能据此重复领取。

## 登记发号词条和簇成员

只新增一张库内元数据表 _layerweave_numbering，以 name/definition 保存词条。没有额外 JSON/JSONL 文件。numbering_entries(connection) 读取全部词条，包含成员名单；读取不建表。默认项目词条可在旧库直接读取，首次发号或登记工具表/词条时持久保存。

例如先通过 register_tables 建立 counter_state（独立身份，有 INTEGER 列 max_num）和两个按项目的工具表 job_a/job_b，再登记：

```python
from layerweave.support.api import register_numbering

register_numbering(connection, {
    "jobs": {
        "rule": "project_entity",
        "counter": {
            "kind": "counter_state",
            "field": "max_num",
            "key": {"id": "project_id"},
        },
        "members": ["job_a", "job_b"],
    },
})
```

| 项 | 含义 |
|---|---|
| jobs | 调度使用的词条名，allocate("jobs", data=...) |
| rule | 当前进程中登记的规则函数名称 |
| counter.kind / field | 实际计数表种类与 INTEGER 计数列；默认项目使用 project.max_id |
| counter.key | 计数行完整主键；字符串值是 data 参数名，正整数值是固定主键值 |
| members | 使用该词条的表种类；名单集中存此处，不在各成员表重复配置 |

上例中 data.project_id=1 会选择 counter_state.id=1。计数行须由调用方事先创建，max_num 初始为非负整数；发号不自动创建业务行。若所有调用共享固定计数行，可用 key={"id": 1}。计数表本身按项目管理时，key 同时给出 project_id 和 id。

参数定位信息在词条内只登记一次，用来定位计数行，也让恢复能在不执行规则函数的情况下找回编号范围。members 必须保存这些范围参数对应的字段，例如 project_id；其余自定义规则的临时参数由调用方自行管理。auto 创建时使用业务字段和 project_id 作为 data。

register_numbering 使用独立声明事务，不接管待提交操作。可以将没有记录或历史的新表从默认簇分配到新词条；已有成员可以幂等登记、追加其他新成员。已有记录或历史后，更换其规则、计数来源或成员归属需要另行迁移，本接口不暗中改写历史。不同数据库分别管理登记，不互相泄漏。

## 增加规则函数

规则是普通函数 function(entry, data)，返回包含正整数 id 的身份字典；当前记录入口支持 id 或 project_id/id。规则可以复用 increment，内部取得当前写连接，定位计数行并原子加一：

```python
from layerweave.support.api import increment, register_numbering_rule

def task_number(entry, data):
    number = increment(entry, data)
    return {"project_id": data["project_id"], "id": number}

register_numbering_rule("task_number", task_number)
```

随后词条的 rule 可以使用 task_number。函数映射是进程内代码登记，开发者负责加载，重开程序后重新登记自己的实现。内置 project_entity 返回 project_id/id，number_only 只返回 id。不扫描或自动执行外部模块，不新增 CLI/MCP。函数必须保持词条指定的计数含义，并使用当前事务；不自行提交、不回退计数、不生成业务日志。

规则函数缺席时，只阻止需要该规则的新发号。已有记录仍能读写，恢复和撤销根据持久声明工作，不调用规则函数。

## 簇、冲突与恢复

簇的特殊约束用于让 AI 在同一范围中通过编号区分不同表的实体，并用项目编号明确所属项目。共享同一计数表种类、计数列和计数行的成员构成同一编号范围；不同项目默认使用不同计数行，不同词条也可使用不同计数列。相同规则函数不代表相同簇；多个词条若实际共享计数位置，检查也视为同一编号范围。

创建、改变编号范围以及恢复新增记录时，支撑在事务提交前按最终状态核对同簇占用，允许批内先写回再移走旧占用。恢复工具还会提前给出冲突详情。同簇冲突会整批回滚；没有加入簇的 provided 表只受本表主键约束，可以与层、对象使用相同数字。

恢复保留原 ID。指定更高原 ID 写回簇内记录时，支撑推进对应计数上界；恢复计数行时结合当前状态、成员记录及日志中的最大编号保留上界。计数列不参与普通内容撤销比较，普通更新也不能降低它。表声明、词条登记作为结构信息，不写入普通 changes 或随内容撤销回退。

计数位置与规则格式是受支持的开发约定。手写 SQL、重置数据库计数或删除历史同时回退计数，会绕过这些保证。工具记录本身继续通过统一写会话处理。

完整临时库示例见仓库 examples/numbering.py；从源码根执行 `python -X utf8 -B examples/numbering.py`，会演示层与视图同编号、独立任务簇、显式领号和原身份恢复。

## 修改实现时从哪里看

| 文件 | 维护内容 |
|---|---|
| [registry.py](registry.py) | 库内词条登记、默认项目簇、成员与计数定位声明 |
| [service.py](service.py) | allocate 薄入口、规则函数映射和原子递增 |
| [state.py](state.py) | 同簇占用、计数列识别与恢复上界；恢复不调用发号规则 |
| [__init__.py](__init__.py) | 本模块公开导出；常用接口也由 layerweave.support.api 导出 |

只增加一种身份组合方式时，从规则函数开始；增加另一组共享计数时，从词条登记开始。业务表的创建和恢复仍通过原写会话进入存储适配器。

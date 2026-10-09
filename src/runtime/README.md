# 工具本体的执行代码

内部工具开发优先使用 [公共 API](API.md)；此文档保留底层记录请求协议。

- [storage/crud.py](storage/crud.py)：通用记录增删改查，值使用 SQL 参数，JSON 字段自动编解码。
- [storage/journal.py](storage/journal.py)：记录实际改动的前后值，与业务写入共用事务。
- [api.py](api.py)：完整记录读取、模型装载与保存的固定入口。
- [dispatch.py](dispatch.py)：记录请求分流，可选择完整读取。
- [operation.py](operation.py)：单条 CRUD 与组合保存共用事务、operation_id 和提交后检测。
- [feedback.py](feedback.py)：带修正线索的错误、明确的操作状态，以及逐条诊断文字格式。
- [console.py](../tools/usage/crud.py)：JSON 文件／标准输入入口，输出 JSON 结果。
- [validation/channel.py](validation/channel.py)：独立检测反馈；默认使用内置执行器。
- [validation/README.md](validation/README.md)：检测时点、主动复查、模块划分和新增规则示例。
- [configuration/loader.py](configuration/loader.py)：读取配置、合并继承、保留父约定。

## 请求格式

单次请求是一个字典；批量请求是这样的字典列表。列表内操作按顺序在同一事务执行，一项操作失败则整批回滚。

```json
{
  "action": "create",
  "kind": "object",
  "project_id": 7,
  "data": {
    "config_ref": "objects/text.toml",
    "name": "开场说明",
    "layer": 1,
    "information": {"text": "角色开始行动。"}
  }
}
```

| 项 | 含义 |
|---|---|
| action | create / read / update / delete |
| kind | project / layer / object / bind；另支持 read 查询 change 日志 |
| project_id | layer、object 的必需项目范围；其他种类按独立 id 定位 |
| id | read 的可选编号；update、delete 必须指定 |
| data | create、update 的字段字典 |
| filters | read 的可选普通列等值条件，None 表示 SQL NULL |
| full | read 指定单条 layer/object 时可设为 true，带回装载对象与发出的关联 |

层创建提供 config_ref，省略 type 时 dispatch 从 TOML 补齐；更新 config_ref 且省略 type 时也同步取得新配置标识。Python dispatch 可传 config_root，自动补齐与默认检测使用同一目录。底层原始请求仍可明确传 type；矛盾值会在提交后由 layer_type 报告 error。配置缺失时若提供原始 type，仍可保存并报告配置问题；缺少 type 则无法推导，操作失败。对象创建须传 config_ref 与实际存在的 layer。其他列可使用数据库默认值，见 [schema.sql](storage/schema.sql)。项目只需 name、tips 等内容；编号、项目归属键和 max_id 由入口参数及发号方法管理，不通过 data 改写。

read 提供 id 时返回单条字典或 null，否则返回列表。对象列表按 begin、end、id 排序，其余按 id 排序。full=true 的层读取还包含直属 objects，每个实体带发出的 bind。完整读取需要明确 id，不使用 filters；普通列表查询仍为单表记录。当前不包含 JSON 内部字段筛选、区间交叠查询或自动展开子树。

update 只修改传入字段，JSON 字段整体替换。delete 只删除指定记录，不级联。目标不存在时返回 data = null、applied = false；空修改、修改成相同值也不产生改动日志。改号、迁移不属于本版普通 update。

批量请求使用已知的编号，不解释临时变量或结果引用表达式。若需要把刚创建的编号立即交给下一步，可以用 Python 组合低层 CRUD，在同一个显式事务和 operation_id 下执行。

Python 的 dispatch 也接受 request_factory(read_record)，用于在写事务内读取最新状态并计算请求。工厂返回字典或列表，核心统一写入；JSON 输入协议不变。示例见 [公共 API](API.md) 的“在事务内计算写入请求”。

## Python 与命令入口

从 src 目录运行完整内存示例：

```sh
python -X utf8 -B -m examples.crud
```

Python 接口：

```python
from contextlib import closing
from runtime.dispatch import dispatch
from runtime.storage.database import open_database

with closing(open_database("../output/ai-production.sqlite3")) as connection:
    result = dispatch(connection, {
        "action": "create", "kind": "project", "data": {"name": "新项目"}
    })
```

dispatch 管理整个事务，连接中不能已有待提交操作。低层 CRUD 不提交事务，返回 `(记录, 变更描述)`，read 直接返回记录；自行组合时由调用方先开启事务，并传入同一个 operation_id。

读取项目列表的 JSON 文件入口：

```sh
python -X utf8 -B -m tools.usage.crud ../output/ai-production.sqlite3 --request examples/requests/read-projects.json
```

可加 `--text` 将输出切换为编译器式文字：先显示操作结果，再逐条列出诊断。默认仍为 JSON。

```sh
python -X utf8 -B -m tools.usage.crud ../output/ai-production.sqlite3 --text --request examples/requests/read-projects.json
```

省略 --request 时从标准输入读 JSON。操作成功返回退出码 0，操作失败返回 1。检测发现问题或执行失败不会把已成功提交的操作改成失败退出码。

## 操作与检测的反馈

单次反馈包含 operation_id、operation、ok、action、kind、project_id、id、applied、data、checks。project 和 bind 的身份不使用项目号，顶层 project_id 为 null；它们的实际项目上下文见数据或日志。

批次反馈包含 operation_id、operation、ok、applied、results、checks。失败时不返回已回滚的临时成功结果，并提供 error.request_index（从 0 开始）。operation_id 由入口用 uuid4().hex 生成，每次调用一个；同一批改动日志共用它。

operation.status 单独描述操作：committed 表示变更已提交，unchanged 表示成功但无变更，read 表示只读成功，failed 表示本次未写入。operation.changes 按顺序列出已提交的 action/target；创建后同批删除会如实列出两个动作。任何失败批次的 changes 均为空，不把已经回滚的临时编号作为创建成功返回。

常见错误附带 code/field 和修正线索：未知 action/kind 列出适用值（change 仅可读取）；未知字段列出可写字段，可附 start→begin 或近似拼写建议。建议不自动改写输入。外键失败在回滚前定位缺失的项目/层或阻止删除的引用；其他 SQL 错误仍保留实际原因，正常写入不额外查询这些引用。

缺失配置显示相对于配置根目录的路径，并附同种配置候选；最多 8 条，优先近似匹配，candidate_count 表示候选路径总数。语法错误和读取失败保留自己的具体原因，不都归类成“文件不存在”。

检测在事务成功提交之后运行，一批只调用一次。回调形式为：

```python
def checker(changes, read_record):
    # changes 包含 action、kind、project_id、id、before、after、change_id、operation_id。
    # read_record(kind, project_id=..., id=..., filters=...) 读取当前记录。
    # 只读取变更描述和查询结果，不修改它们。
    return []  # 问题字典列表；规则示例见 validation/README.md
```

默认 dispatch 与 CLI 已接入内置执行器。显式传 checker=None 可关闭自动检测；传入自定义 checker 会替换内置执行器。变更描述保留修改前后数据，内置执行器以最终数据库记录检查，选择相关旧层、新层或被删除目标的剩余关联，并对目标与规则去重。

变更描述中的 project_id 是日志查询上下文；查询 project、bind 时仍只传它们的独立 id，查询 layer、object 才传 project_id。

- checks.status = not_run：没有实际变化，或未配置检测器。
- checks.status = completed：检测已完成，issues 可能为空，也可能包含问题。
- checks.status = partial：部分检查未完成；逐条 issues 说明原因，其他检查继续。
- checks.status = failed：检测未完成，附带错误说明；已经提交的数据和日志仍然保留。

CRUD 仅存取 config_ref，不要求配置文件此时存在。提交后的检测读取配置；缺失配置不会撤销数据，会返回 partial 与具体目标、原因。内置问题包含 severity（warn/error）、rule、target、message、scope；汇报等级独立配置在 configs/logging/diagnostics.toml，none 隐藏对应条目，未配置默认 warn。相同目标的相同配置错误合并，并附 affected_checks；可附 field、related、skipped、checked_target。scope=direct 表示问题目标本次发生过修改，related 表示关联检查的目标未被本次直接修改，manual 表示主动复查。checked_target 标明与问题目标不同的实际检查目标，例如层的兼容检查发现某个对象配置缺失。这些标记不判断问题是否以前存在。completed 表示执行完成，不表示没有约定问题。

约束开关沿用原配置；汇报级别不关闭检查。静音无法执行的检查时，checks.status 仍保留 partial。文字输出只保留操作结果和逐条诊断，不用直接/关联范围推断整次操作是否通过。

主动复查使用 validation.runner.validate，不写日志。示例与自定义配置目录接入见 [检测说明](validation/README.md)。直接调用低层 CRUD 时，调用方负责提交并显式调用检测器；不会通过类构造或属性赋值暗中触发检测。

项目/多子树/对象的现成复查工具为 tools.usage.common.recheck；按操作查看历史用 tools.usage.common.history，整批撤销与重做用 tools.usage.common.undo。它们通过 runtime.api 组合现有核心，不增加 dispatch 的 action 名称。参数与迁移说明见 [复查、历史与撤销](storage/HISTORY.md)。

## 查询改动日志

```json
{
  "action": "read",
  "kind": "change",
  "filters": {"operation_id": "从操作结果取得的完整 UUID"}
}
```

还可以按 kind、project_id、target_id、action 等实际列等值查询。before_data、after_data 会还原为 JSON 值。日志没有实体外键，删除目标后仍保留；日志记录的是请求目标的变化，发号带来的 max_id 更新不另记一条日志。bind 日志的项目上下文取修改后来源项目，删除时取删除前来源项目。

撤销产生新的操作与普通前后快照，undo_of 列指向被撤销的操作编号。原日志保持不变；重做就是撤销这个新操作。关联 id 在全库递增，不复用已删除编号；旧库先运行初始化命令升级。

read 和没有实际改变数据的请求不写日志。日志表由内部记录方法写入，四种业务实体的 CRUD 不再为日志写入递归生成日志。

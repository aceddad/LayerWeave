# CRUD 请求与反馈协议

[返回使用入口](README.md)。

通过 dispatch 或 tool.builtin.usage.records.cli 读写记录。示例中的项目、层和对象编号须替换为实际值；CLI 完成可编辑安装后运行。

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

层创建提供 config_ref，省略 type 时 dispatch 从 TOML 补齐；更新 config_ref 且省略 type 时也同步取得新配置标识。Python dispatch 可传 config_root，自动补齐与默认检测使用同一目录。底层原始请求仍可明确传 type；矛盾值会在提交后由 layer_type 报告 error。配置缺失时若提供原始 type，仍可保存并报告配置问题；缺少 type 则无法推导，操作失败。对象创建须传 config_ref 与实际存在的 layer。其他列可使用数据库默认值，见 [schema.sql](../../../src/support/storage/schema.sql)。项目只需 name、tips 等内容；编号、项目归属键和 max_id 由入口参数及发号方法管理，不通过 data 改写。

read 提供 id 时返回单条字典或 null，否则返回列表。对象列表按 begin、end、id 排序，其余按 id 排序。full=true 的层读取还包含直属 objects，每个实体带发出的 bind。完整读取需要明确 id，不使用 filters；普通列表查询仍为单表记录。当前不包含 JSON 内部字段筛选、区间交叠查询或自动展开子树。

update 只修改传入字段，JSON 字段整体替换。delete 只删除指定记录，不级联。目标不存在时返回 data = null、applied = false；空修改、修改成相同值也不产生改动日志。改号、迁移不属于本版普通 update。

批量请求使用已知的编号，不解释临时变量或结果引用表达式。若需要把刚创建的编号立即交给下一步，可以用 support.api.transaction 或 run_operation 组合写会话原语，使用入口分配的 operation_id。

Python 的 dispatch 也接受 request_factory(read_record)，用于在写事务内读取最新状态并计算请求。工厂返回字典或列表，支撑统一写入；JSON 输入协议不变。新工具也可直接使用[公共 API](../../../src/support/API.md#统一写会话)的写会话，不依赖 CDUR 包。

## Python 与命令入口

从 src 目录运行完整内存示例：

```sh
python -X utf8 -B -m examples.crud
```

Python 接口：

```python
from contextlib import closing
from tool.builtin.usage.records.dispatch import dispatch
from support.api import open_database

with closing(open_database("output/ai-production.sqlite3")) as connection:
    result = dispatch(connection, {
        "action": "create", "kind": "project", "data": {"name": "新项目"}
    })
```

调用 dispatch 时，connection 不能已有待提交操作。需要开发组合工具时阅读[开发 API](../../../src/support/API.md)。

读取项目列表的 JSON 文件入口：

```sh
python -X utf8 -B -m tool.builtin.usage.records.cli output/ai-production.sqlite3 --request examples/requests/read-projects.json
```

可加 `--text` 将输出切换为编译器式文字：先显示操作结果，再逐条列出诊断。默认仍为 JSON。

```sh
python -X utf8 -B -m tool.builtin.usage.records.cli output/ai-production.sqlite3 --text --request examples/requests/read-projects.json
```

省略 --request 时从标准输入读 JSON。操作成功返回退出码 0，操作失败返回 1。检测发现问题或执行失败不会把已成功提交的操作改成失败退出码。

## 操作与检测的反馈

单次反馈包含 operation_id、operation、ok、action、kind、project_id、id、applied、data、checks。project 和 bind 的身份不使用项目号，顶层 project_id 为 null；它们的实际项目上下文见数据或日志。

批次反馈包含 operation_id、operation、ok、applied、results、checks。失败时不返回已回滚的临时成功结果，并提供 error.request_index（从 0 开始）。operation_id 由入口用 uuid4().hex 生成，每次调用一个；同一批改动日志共用它。

先用 operation.status 判断操作结果，再看 checks：

| operation.status | 含义 |
|---|---|
| committed | 变更已提交 |
| unchanged | 成功但无变更 |
| read | 只读成功 |
| failed | 本次未写入 |

operation.changes 按顺序列出已提交的 action/target；同批创建后删除会列出两项。失败批次的 changes 为空，不返回已回滚的临时成功记录。

常见错误附带 code/field 和修正线索：未知 action/kind 列出适用值（change 仅可读取）；未知字段列出可写字段，可附 start→begin 或近似拼写建议。建议不自动改写输入。外键失败在回滚前定位缺失的项目/层或阻止删除的引用；其他 SQL 错误仍保留实际原因，正常写入不额外查询这些引用。

缺失配置显示相对于配置根目录的路径，并附同种配置候选；最多 8 条，优先近似匹配，candidate_count 表示候选路径总数。语法错误和读取失败保留自己的具体原因，不都归类成“文件不存在”。

默认请求已安装的检测提供者，没有提供者时 checks.status=not_run；Python 的 checker=None 可关闭自动检查，自定义回调见[开发 API](../../../src/support/API.md#提交后的可选检查)。检测在提交后运行，不撤销已经写入的数据。

- checks.status = not_run：没有实际变化，或未配置检测器。
- checks.status = completed：检测已完成，issues 可能为空，也可能包含问题。
- checks.status = partial：部分检查未完成；逐条 issues 说明原因，其他检查继续。
- checks.status = failed：检测未完成，附带错误说明；已经提交的数据和日志仍然保留。

config_ref 原样保存，缺失配置可在提交后报告 partial 与具体原因，不撤销数据。内置 issues 的字段如下：

| 字段 | 内容 |
|---|---|
| severity、rule、target、message | 等级、规则、问题目标和原因 |
| scope | direct：目标本次被修改；related：关联检查目标；manual：主动复查 |
| field、related、skipped | 可选，问题字段、关联目标及未检查标记 |
| checked_target | 实际检查目标与问题目标不同时提供，例如检查层却发现对象配置缺失 |
| affected_checks | 同一配置失败合并后，受影响的检查项 |

scope 不推断问题新旧。汇报等级由[诊断配置](../../../src/support/DIAGNOSTICS.md)管理；completed 表示执行完成，issues 仍可能有 error。

约束开关沿用原配置；汇报级别不关闭检查。静音无法执行的检查时，checks.status 仍保留 partial。文字输出只保留操作结果和逐条诊断，不用直接/关联范围推断整次操作是否通过。

需要重新检查内容时，使用[复查工具](HISTORY.md#复查)，不会修改数据或制造日志。

项目/多子树/对象的现成复查工具为 tool.builtin.usage.validation.cli；按操作查看历史用 tool.builtin.usage.history.cli，整批撤销与重做用 tool.builtin.usage.undo.cli。它们通过 support.api 组合现有核心，不增加 dispatch 的 action 名称。参数与迁移说明见 [复查、历史与撤销](HISTORY.md)。

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

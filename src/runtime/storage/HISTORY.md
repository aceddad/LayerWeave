# 复查、历史与撤销

内部工具统一从 runtime.api 调用核心能力。复查和历史只读；撤销是一次新的业务写操作。现有实际删除方式保持，日志保存恢复所需的前后快照。

## 复查

```python
from runtime.api import recheck

whole = recheck(connection, project_id)
trees = recheck(connection, project_id, layer_ids=[4, 7])
objects = recheck(connection, project_id, object_ids=[8, 12])
```

两种编号列表互斥；均省略时检查整个项目，显式空列表为空选择。子树包含起始层、全部子孙层与直属对象，重选自动去重；缺失目标逐条报告，其余继续。检测与范围读取在同一读取快照内，复用既有 validate、规则开关、汇报等级和配置继承。

返回 scope、counts（范围内层/对象数）、status、issues、issue_counts。counts 不冒充实际规则执行次数，必要的同层检查或关联检查可能涉及范围外目标。completed 表示本次检查执行完成，仍可含 error；partial 表示有检查无法完成，即使该诊断被 none 隐藏也保持 partial。只修改 TOML 后可直接复查，不制造数据更新或历史。

```sh
# 从 src 运行；以下数据库路径与编号替换为实际值。
python -X utf8 -B -m tools.common.recheck DATABASE PROJECT_ID
python -X utf8 -B -m tools.common.recheck DATABASE PROJECT_ID --layer-ids 4 7
python -X utf8 -B -m tools.common.recheck DATABASE PROJECT_ID --object-ids 8 12 --json
```

文字输出先说明范围和执行状态，随后逐条诊断。--config-root 指定当前配置目录。

## 历史

```python
from runtime.api import read_history

page = read_history(connection, project_id, kind="object", id=object_id, limit=20)
next_page = read_history(connection, project_id, kind="object", id=object_id,
                         limit=20, before=page["next_cursor"])  # 仅在 next_cursor 非空时调用
operation = read_history(connection, operation_id=operation_id)
```

省略项目/实体范围可以查看整个库；kind 支持 project、layer、object、bind。指定层/对象 id 还需 project_id；bind.id 全库唯一。查询不要求实体仍存在。

operation_count 是匹配范围内的操作次数，change_count 是原始改动条数；同一操作对同一对象改两次，算一次操作、两条改动。列表默认最近 20 次，按日志编号倒序；before 使用 next_cursor，不用时间戳猜分页边界。分页不会切开一个操作。

范围只筛选“哪些操作相关”。每个 items 条目仍展示该操作的完整批次，含 operation_id、undo_of、时间、project_ids、change_count、matched_change_count 和 changes。跨项目批次不会被截成局部操作；关联两端及修改前后的项目都可命中历史。

更新条目的 fields 展示字段差异；information 等字典递归展开，列表整体比较。path 是键数组，准确保留含点号的键；before_present/after_present 区分缺失与 null，数值比较区分 1、1.0、true。项目 max_id 是发号状态，不作为用户内容变化展示。

detail=True 给列表附带完整前后快照；按 operation_id 查询总是附带快照。操作不存在时 items=[]。undo_of 非空表示该操作撤销了哪个原操作，原日志不会被删除或改写。

```sh
python -X utf8 -B -m tools.common.history DATABASE --project-id PROJECT_ID
python -X utf8 -B -m tools.common.history DATABASE --project-id PROJECT_ID --kind object --id OBJECT_ID
python -X utf8 -B -m tools.common.history DATABASE --operation-id OPERATION_ID
python -X utf8 -B -m tools.common.history DATABASE --project-id PROJECT_ID --limit 20 --before CURSOR --json
```

## 撤销与重做

```python
from runtime.api import undo_operation

undone = undo_operation(connection, original_operation_id)
# 确认 undone["ok"] 且发生改动后，对其新 operation_id 再撤销即可重做。
redone = undo_operation(connection, undone["operation_id"])
```

```sh
python -X utf8 -B -m tools.common.undo DATABASE OPERATION_ID
python -X utf8 -B -m tools.common.undo DATABASE UNDO_OPERATION_ID --json
```

撤销总是针对完整操作，可跨项目，不提供局部撤销或强制覆盖开关。创建的记录删除，删除的记录按原编号恢复，修改的记录恢复原值。一次操作对同一记录的多次改动合并成最初/最终状态；已完全抵消的变化不制造新恢复日志。

冲突比较和恢复共用 BEGIN IMMEDIATE 写事务。当前记录必须与原操作的最终记录一致，项目 max_id 除外；后续即便只改了备注也算冲突。不会仅因有后续历史就拒绝：后续操作已撤回、当前状态重新一致时可以继续撤销。重复撤销同一个已经撤销的有效操作通常会冲突；重做应明确传入撤销操作自己的新编号。

冲突返回 ok=false、applied=false、error.conflicts，包含目标、差异、预期/当前/拟恢复记录，或阻碍恢复的引用。任何冲突都不写数据或日志。缺少恢复所需的层/项目、原编号被另一实体占用、待删除目标被后续记录引用，均明确报告；不自动连带修改其他操作的数据。

恢复是存储层的私有入口，不把快照交给普通创建/更新重新发号或按轴取整。保留实际历史坐标、JSON 内容、配置引用和层 type；数据库外键在这次事务提交时统一检查，整批父子恢复与中途失败回滚都不会留下半份数据。

成功撤销分配新的 operation_id，以实际恢复前后值追加普通 create/update/delete 日志，changes.undo_of 指向原操作。没有可撤销的最终变化时返回 unchanged；原操作不存在或没有实际变更日志时报告 operation_not_found。

恢复后使用当前 config_root 运行现有提交后检查；配置文件及 Python 文件不属于数据库撤销范围。error 诊断不会撤销已经完成的恢复，操作结果和诊断仍分别表达。外部 checker 的约定与 dispatch 一致。

## 编号与旧库迁移

项目编号以及关联编号各自在全库递增。层与对象共用每个项目的 max_id。撤销不回退这些发号进度；恢复旧编号不会重发新编号。恢复项目时结合当前状态、行记录和历史中的最大编号保留发号上界。

binds.id 使用 SQLite AUTOINCREMENT，经现有 CRUD 入口创建，不占项目 max_id。旧库执行既有初始化命令即可升级：

```sh
python -X utf8 -B -m runtime.storage.database DATABASE
```

迁移保留关联记录、日志和附加索引/触发器，将关联发号上界至少提升到现存关联与历史关联编号的最大值，并为 changes 增加可空 undo_of 列。旧日志该列为 NULL。重复初始化不降低序列，也不改写旧历史中已经发生过的编号复用。普通打开连接及只读工具不会暗中迁移数据库；旧库写入新版前应执行初始化。

复查范围在 runtime/validation/recheck.py；历史查询与差异在 storage/history.py；恢复事务在 storage/undo.py。工具入口位于 tools/common/recheck.py、history.py、undo.py。可运行 examples.review_history 查看内存数据库示例。

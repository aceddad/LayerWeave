# 历史、复查与恢复的实现

调用方式、分页字段、撤销冲突和重做流程见[使用说明](../HISTORY.md)。[返回存储模块](../../../../support/storage/README.md)。

## 模块分工

- [validation/recheck.py](../validation/recheck.py)：在同一读取快照内选范围并复用 validate。
- [history.py](../history/service.py)：按操作选取日志、分页及生成字段差异。
- [undo.py](service.py)：_plan 合并日志，_dependencies 检查引用，再调用支撑的 restore 执行。
- [journal.py](../../../../support/storage/journal.py)：记录实际前后数据及 undo_of。

## 历史查询

筛选先确定相关 operation_id，再读取完整批次；按项目命中不会截断跨项目操作。字段差异复用 JSON 类型比较，键路径使用数组，列表作为整体；发号状态通过内容投影排除。

## 恢复流程

1. 通过 run_operation 进入支撑写会话，将同一实体的日志合并为最初与最终状态。
2. 读取当前数据；净变化为零的记录跳过，纯 update 计算实际改变的顶层字段。
3. 检查字段或记录冲突及恢复依赖，形成整批恢复计划；任意冲突阻止写入。
4. 调用 layerweave.support.records.restore 恢复原编号和历史坐标；实际 SQL 与编号上界在 layerweave.support.storage.restoration，工具不写 SQL。
5. update 的 SQL 只写恢复字段，避免无关列触发器因整行赋值而执行；外键及父链无环在最终状态验证；恢复旧环同样失败并回滚。
6. 恢复与新日志同事务提交，记录 undo_of，再调用已安装的可选检查提供者；缺席时明确未检查。

information、axis 的整体比较以及 create/delete 的记录比较，详见使用说明的冲突表；此处不另维护一份业务规则。

## 编号与旧表升级

恢复计数行时结合当前状态、簇成员及日志保留发号上界；project.max_id 和已登记工具计数列不参与内容冲突比较。编号冲突只比较同簇同范围的成员，provided 簇外表不参与跨表排斥；发号说明见[编号模块](../../../../support/numbering/README.md)。

database.upgrade_history 负责将关联表升级为 AUTOINCREMENT，并增加 changes.undo_of。迁移保留索引和触发器，发号起点覆盖现存与已删除历史编号；旧日志 undo_of 为 NULL。重复初始化不降低序列，也不改写历史中已发生的编号复用。

数据库准备的调用方式及其余持久化规则见 [SCHEMA](../../../../support/storage/SCHEMA.md)。读取工具不执行迁移。

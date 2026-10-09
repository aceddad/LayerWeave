# 历史、复查与恢复的实现

调用方式、分页字段、撤销冲突和重做流程见[使用说明](../../tools/usage/HISTORY.md)。[返回存储模块](README.md)。

## 模块分工

- [validation/recheck.py](../validation/recheck.py)：在同一读取快照内选范围并复用 validate。
- [history.py](history.py)：按操作选取日志、分页及生成字段差异。
- [undo.py](undo.py)：_plan 合并日志，_dependencies 检查引用，_restore 恢复记录，_project_high_water 保留发号上界。
- [journal.py](journal.py)：记录实际前后数据及 undo_of。

## 历史查询

筛选先确定相关 operation_id，再读取完整批次；按项目命中不会截断跨项目操作。字段差异复用 JSON 类型比较，键路径使用数组，列表作为整体；发号状态通过内容投影排除。

## 恢复流程

1. 开启 BEGIN IMMEDIATE，将同一实体的日志合并为最初与最终状态。
2. 读取当前数据；净变化为零的记录跳过，纯 update 计算实际改变的顶层字段。
3. 检查字段或记录冲突及恢复依赖，形成整批恢复计划；任意冲突阻止写入。
4. 使用私有恢复方法恢复原编号、编码内容和历史坐标，不走普通 create/update 的发号或落点流程。
5. update 的 SQL 只写恢复字段，避免无关列触发器因整行赋值而执行；外键在最终状态验证。
6. 恢复与新日志同事务提交，记录 undo_of，再按当前配置运行检查。

information、axis 的整体比较以及 create/delete 的记录比较，详见使用说明的冲突表；此处不另维护一份业务规则。

## 编号与旧表升级

恢复项目时结合当前状态、行记录和日志中的编号保留发号上界。项目 max_id 不参与内容冲突比较。

database.upgrade_history 负责将关联表升级为 AUTOINCREMENT，并增加 changes.undo_of。迁移保留索引和触发器，发号起点覆盖现存与已删除历史编号；旧日志 undo_of 为 NULL。重复初始化不降低序列，也不改写历史中已发生的编号复用。

数据库准备的调用方式及其余持久化规则见 [SCHEMA](SCHEMA.md)。读取工具不执行迁移。

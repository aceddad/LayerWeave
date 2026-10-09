# 存储模块

这里维护 SQLite、记录装配和事务内编辑实现。[返回核心模块](../README.md)。工具调用者从[使用入口](../../tools/usage/README.md)进入。

| 开发任务 | 实现说明 |
|---|---|
| 修改数据表、编号、记录映射和日志写入 | [SCHEMA](SCHEMA.md) |
| 修改历史查询或恢复计划 | [HISTORY](HISTORY.md) |
| 修改子树遍历、复制、关联映射与迁移组合 | [SUBTREES](SUBTREES.md) |
| 修改分割、插空档与坐标计算的组合流程 | [EDITING](EDITING.md) |
| 使用 Python 读写或装载模型 | [公共 API](../API.md) |

代码位置：database/schema 管理表与发号；crud/journal/errors 管理记录写入；assembly/details/queries 管理读取；models/save 管理实例装配；history/undo 管理历史恢复；subtrees/timeline 管理复合编辑。

低层 CRUD 不自行提交或运行语义检查。完整调用参数、返回和业务边界只在 usage 的对应说明维护，开发者通过上面的实现说明链接查阅。

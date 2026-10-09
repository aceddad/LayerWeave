# 存储模块

这里负责 SQLite 表结构、编号、记录读写、模型装配、事务内组合和历史恢复。[返回核心模块](../README.md)。

| 任务 | 主要说明 |
|---|---|
| 初始化/升级数据库、理解字段、编号和日志 | [数据表与持久化](SCHEMA.md) |
| 读取完整记录、装载类、保存层或对象 | [公共 API](../API.md) |
| 查询操作历史、处理撤销冲突与重做 | [历史与恢复](HISTORY.md) |
| 删除或复制子树 | [子树操作](SUBTREES.md) |
| 分割、平移、插空档及跨项目搬移 | [编辑操作](EDITING.md) |

## 代码位置

- schema.sql、database.py：建表、连接、升级和发号。
- crud.py、journal.py、errors.py：记录操作、同事务日志与 SQL 错误解释。
- assembly.py、details.py、queries.py：完整记录与范围读取。
- models.py、save.py：Python 实例装载与组合保存。
- history.py、undo.py：历史查询与恢复。
- subtrees.py、timeline.py：复用 CRUD 的批量编辑步骤。

内部工具优先从 runtime.api 调用；低层 CRUD 不自行提交或运行语义检查，组合要求见 SCHEMA 和 API。数据库初始化的 CLI 位于开发工具目录。

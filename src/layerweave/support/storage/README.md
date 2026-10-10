# SQLite 存储适配

这里负责将抽象结构保存为 SQLite 记录。工具通过[公共支撑 API](../API.md)使用它，不直接执行 SQL 写入。

| 文件 | 职责 |
|---|---|
| database.py、schema.sql | 初始化/升级、表结构、项目内发号与全库序列 |
| crud.py、journal.py、errors.py | 实际记录操作、before/after 日志和引用错误说明 |
| restoration.py | 精确恢复原身份/原值，维护编号上界 |
| log_reader.py | 按操作和目标读取原始日志页，不决定撤销或展示策略 |
| assembly.py、details.py、queries.py | 单记录、范围和关系读取 |
| models.py、save.py | 类适配、按需装载、完整层/对象保存与成功后回填 |

统一事务入口在 layerweave.support.transaction；本目录的写入适配器只在该会话内工作，不自行提交。原始读取不要求配置存在，实例装载才需要 TOML 与对应类。

表和编号规则见[SCHEMA](SCHEMA.md)。[历史展示](../../tool/builtin/usage/history/service.py)、[撤销规划](../../tool/builtin/usage/undo/IMPLEMENTATION.md)、[子树与迁移](../../tool/builtin/usage/editing/TREES.md)、[时间范围编辑](../../tool/builtin/usage/editing/IMPLEMENTATION.md)属于各自工具包。

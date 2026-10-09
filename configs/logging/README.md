# 诊断汇报配置

[diagnostics.toml](diagnostics.toml) 控制检查结果以 error、warn 或 none 汇报。[返回配置入口](../README.md)。

约束是否检查由层/对象声明决定；这里负责检查结果如何汇报。字段与覆盖优先级、默认行为、同因合并及示例统一维护在[诊断汇报说明](../../src/support/DIAGNOSTICS.md)。

操作历史数据保存在数据库 changes 表中，其格式与撤销行为见[历史与恢复](../../tool/builtin/usage/HISTORY.md)。本目录不存放操作日志文件。

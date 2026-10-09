# 检测模块

这里决定哪些约定需要检查、检查哪些目标，以及如何组织诊断。语义检测在写入提交后运行；模型构造和普通读取不自动触发检测。[返回核心模块](../README.md)。

| 任务 | 主要说明 |
|---|---|
| 查检测时点、规则范围或新增规则 | [检测执行与扩展](RULES.md) |
| 配置 error/warn/none、静音与同因合并 | [诊断汇报](DIAGNOSTICS.md) |
| 理解 committed 与 checks 的关系 | [请求与反馈协议](../PROTOCOL.md) |
| 对项目、子树或对象主动复查 | [复查工具](../storage/HISTORY.md) |

## 代码位置

- registry.py：登记规则函数、触发字段与范围。
- runner.py、recheck.py：选择目标、执行、去重与主动复查。
- rules/：字段、层、对象和关联的普通检查函数。
- diagnostics.py、channel.py：汇报配置、同因合并及检查执行状态。

约束来自层/对象配置，汇报设置来自 configs/logging；两者的具体语义分别由配置模块与诊断专题维护。

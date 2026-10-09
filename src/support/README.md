# 基础支撑

support 提供核心结构的文件和数据库适配。没有任何内置工具时，仍可读写记录、保存与装载 Python 实例、发号和记录改动。公共入口见[API](API.md)，总体边界见[架构](../../docs/architecture.md)。

| 位置 | 职责 |
|---|---|
| api.py | 常用读取、实例往返、写会话及反馈入口 |
| transaction.py、operation.py | 事务、真实变更收集、提交前父链检查与可选的提交后回调 |
| records.py | 会话中的记录原语、原值创建和原身份恢复 |
| storage/ | SQLite 表、发号、读查询、日志、精确恢复和实例适配 |
| configuration/ | TOML 读取、类定位，调用核心的继承合并语义 |
| positions.py | 轴精度与位置落点 |
| feedback.py、channel.py、diagnostics.py | 通用操作/诊断表达、汇报配置和检查回调通道 |
| cli.py、commands.py、providers.py | CLI 外壳、静态命令声明发现、可选能力发现 |
| paths.py | 与当前工作目录无关的源码资源位置 |

CDUR、编辑、帮助、历史展示、撤销规划和内容检测位于 [tool/builtin](../../tool/builtin/README.md)。支撑不导入这些具体工具；检测缺席不妨碍写入。新增内部工具见[开发指南](../../docs/developer-conventions.md)。

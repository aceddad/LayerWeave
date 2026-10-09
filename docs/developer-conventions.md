# 开发约定与文档职责

本文面向修改 LayerWeave 的开发者，包括 AI。[返回开发入口](../src/tools/developer/README.md)。

## 实现原则

1. 基础模型保存数据，维持按需导入。新约束、资源解释或媒体处理应有明确需求，不自动加入模型构造和属性赋值。
2. 内部工具从 runtime.api 获取能力；SQL、发号、事务、日志、配置继承和检测由核心维护。普通读后写用 dispatch 请求工厂，复杂操作通过 run_operation 组合低层步骤，避免嵌套完整操作入口。
3. 一次操作内需要一致的读取时使用 read_snapshot。纯查询保持原始存储数值，不写入、迁移或制造日志。生成位置使用公共位置计算；恢复与迁移的例外按对应专题执行。
4. 每个命令在自身模块声明字面量 COMMANDS；复用 shared/_cli 和既有目录发现。配置 help 使用 Loader 与 DiagnosticPolicy，不硬编码封装名单或导入类来展示说明。
5. 将“已提交什么”和“检查发现什么”分别表达，复用 runtime.feedback。具体结果字段以请求协议为准。
6. 新封装同时提供 Python 类和 TOML。修改约定时阅读主要说明与现有测试，保持原有继承、编号、关联和恢复语义。
7. 项目尚未发布，只维护当前模块路径。MCP 编排与视图实现按对应阶段推进，main 保持无 GUI 依赖。

## 文档职责

README 解释当前目录的职责、文件位置和阅读入口。短说明可以直接写入；大量字段、规则、参数和示例放专题文件。AGENTS.md 只维护 AI 的工作流程和必要要求。

工具的用途、示例、输入/返回与可观察边界集中在 tools/usage；共用 help 说明放 tools/shared。runtime 保留开发 API 和实现说明。编号、关联、失败、撤销的可观察行为属于使用说明，事务步骤和内部辅助函数属于实现说明。使用章节先给用途和例子，再用表格或独立条目解释参数与规则。

一项语义在一个主要位置详细维护，其他文档保留简短说明并链接过去：

| 主题 | 主要维护位置 |
|---|---|
| 模块边界与整体概念 | [架构说明](architecture.md) |
| Python 模型与扩充入口 | [模型说明](../src/models/README.md)，字段声明在类及对应 TOML |
| 配置继承、合并与类绑定 | [配置说明](../src/runtime/configuration/README.md) |
| Python 调用、输入与返回 | [公共 API](../src/runtime/API.md) |
| JSON CRUD 请求和操作/检查反馈 | [请求协议](../src/tools/usage/CRUD.md) |
| 数据表、编号、持久化与日志写入 | [存储专题](../src/runtime/storage/SCHEMA.md) |
| 历史与恢复、子树、范围编辑的使用行为 | usage 的 [HISTORY](../src/tools/usage/HISTORY.md)、[SUBTREES](../src/tools/usage/SUBTREES.md)、[EDITING](../src/tools/usage/EDITING.md) |
| 这些工具的实现流程 | storage 的 [HISTORY](../src/runtime/storage/HISTORY.md)、[SUBTREES](../src/runtime/storage/SUBTREES.md)、[EDITING](../src/runtime/storage/EDITING.md)；参数与业务规则链接到使用说明 |
| 检测时点、执行和新增规则 | [检测专题](../src/runtime/validation/RULES.md) |
| 汇报等级和配置覆盖 | [诊断专题](../src/runtime/validation/DIAGNOSTICS.md) |
| 通用查询与位置工具用法 | [使用手册](../src/tools/usage/GUIDE.md) |
| 命令声明、发现及 CLI 示例 | [命令专题](../src/tools/shared/COMMANDS.md) |
| 配置 help 的使用/开发模式 | [配置 help 专题](../src/tools/shared/CONFIG_HELP.md) |

修改规则时更新其主要说明；新增阅读入口时同步相邻 README。配置和命令的具体支持清单由已有 help 动态发现，文档不再维护另一套执行登记表。

## 验证

持久化、共享执行或模块路径改动需运行项目首页所列完整测试；按影响运行相关[示例](examples.md)。测试与示例只使用内存或专用临时数据库，保留 output 中的实际项目数据。

文档整理要检查本地链接和命令路径。历史交付报告保留为当时的记录，不作为现行接口说明，也不为了旧报告维护兼容入口。

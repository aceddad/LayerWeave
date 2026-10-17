# 文档约定与整理经验

先确定文档服务什么阅读目的，再决定内容和结构。本文是文档写作与维护约定的主要位置；开发流程见[开发指南](developer-conventions.md)。

## 各类文档的用途

| 文档 | 面向的阅读目的 |
|---|---|
| 项目根 README | 理解项目做什么、有什么用、如何试用；展示主要能力和最小示例，保留少量资料链接 |
| 子目录 README | 按该目录的实际用途介绍模块或作为一组说明的入口；不要求统一套导航模板 |
| 使用说明 | 学会调用工具，理解输入、返回以及内容、编号、关联、失败和撤销的行为 |
| 开发指南 | 准备开发环境、找到源码、选择扩充流程和验证方式 |
| AI 开发指导 | 用 LayerWeave 开发自己的工具，按用法分篇说明自由扩展的位置、最小接入方式与实例 |
| 架构说明 | 理解概念、模块之间的关系及设计边界 |
| 实现说明 | 理解内部流程、函数协作、存储步骤和修改注意点 |
| AGENTS.md | agent 的任务分流、必要阅读与工作要求 |

项目首页以介绍和上手为主。源码地图、修改哪个文件、测试流程放入开发指南；agent 的详细阅读顺序放在 AGENTS。子目录 README 按需保留简短解释，不为每个目录机械创建一份文件。

## 放置与主要说明

工具用法集中在 src/layerweave/tool/builtin/usage，共用 help 说明放在 src/layerweave/tool/builtin/shared；support 保存基础支撑 API 和适配实现说明，工具包保存自己的业务实现说明，docs 保存整体设计和开发约定。

一项语义只在一个主要位置详细维护。其他文档可以给必要的简述或最小例子，并链接完整说明；不复制整套参数表和边界规则。

| 主题 | 主要维护位置 |
|---|---|
| 模块边界与整体概念 | [架构说明](architecture.md) |
| 配置路径、技能路由、命令入口与登记名称的区别 | [开发指南](developer-conventions.md#入口路径与调度标识)；各机制的细节仍由对应专题维护 |
| 按需借用内核、扩展工具与配置 | [AI 开发指导](build-with-layerweave/README.md)，每种思路单独成篇；参数细节继续由 API 和专题维护 |
| 工具表声明、字段、引用与接入范围 | [工具表开发指导](build-with-layerweave/03-managed-tables.md) |
| 自定义 ID、发号词条、簇成员与计数恢复 | [编号模块](../src/layerweave/support/numbering/README.md) |
| Python 模型与扩充入口 | [模型说明](../src/layerweave/models/README.md)，字段声明在类及对应 TOML |
| 配置继承、合并与类绑定 | [配置说明](../src/layerweave/support/configuration/README.md) |
| 独立工具与事务内组合接口 | [组合开发指导](build-with-layerweave/04-composing-tools.md)；反馈字段由基础 API 维护 |
| 初始快照与增量刷新次序 | [增量接入指导](build-with-layerweave/05-incremental-reading.md)；日志字段由基础 API 维护 |
| Python 调用、输入与返回 | [公共 API](../src/layerweave/support/API.md) |
| JSON CRUD 请求和操作/检查反馈 | [请求协议](../src/layerweave/tool/builtin/usage/CRUD.md) |
| 分层 JSON 交换、文件引用与模板 | [交换格式](../src/layerweave/tool/builtin/usage/exchange/FORMAT.md)；调用入口与扩充说明在同包 |
| 数据表、编号、持久化与日志写入 | [存储专题](../src/layerweave/support/storage/SCHEMA.md) |
| 历史与恢复、子树、范围编辑的使用行为 | usage 的 [HISTORY](../src/layerweave/tool/builtin/usage/HISTORY.md)、[SUBTREES](../src/layerweave/tool/builtin/usage/SUBTREES.md)、[EDITING](../src/layerweave/tool/builtin/usage/EDITING.md) |
| 这些工具的实现流程 | 工具包的 [HISTORY](../src/layerweave/tool/builtin/usage/undo/IMPLEMENTATION.md)、[SUBTREES](../src/layerweave/tool/builtin/usage/editing/TREES.md)、[EDITING](../src/layerweave/tool/builtin/usage/editing/IMPLEMENTATION.md)；参数与业务规则链接到使用说明 |
| 检测时点、执行和新增规则 | [检测专题](../src/layerweave/tool/builtin/usage/validation/RULES.md) |
| 汇报等级和配置覆盖 | [诊断专题](../src/layerweave/support/DIAGNOSTICS.md) |
| 通用查询与位置工具用法 | [使用手册](../src/layerweave/tool/builtin/usage/GUIDE.md) |
| 命令声明、发现及 CLI 示例 | [命令专题](../src/layerweave/tool/builtin/shared/help/COMMANDS.md) |
| 组件声明、版本登记与存在状态 | [版本工具](../src/layerweave/tool/builtin/developer/versions/README.md)，当前版本号和更新摘要在各组件的 component.toml |
| 配置 help 的使用/开发模式 | [配置 help 专题](../src/layerweave/tool/builtin/shared/help/CONFIG_HELP.md) |
| 工具包登记自己的层和对象类型 | [工具包登记类型](../src/layerweave/tool/builtin/developer/TOOL_TYPES.md)，以视图工具的批注层为例；有序列表的思路见 AI 开发指导第二篇，批注层自己的约定在视图开发说明 |
| 外置技能的存放与绑定示例 | [外置工具](../src/layerweave/tool/README.md)；各技能的能力说明维护在包内 SKILL.md |
| 技能 ZIP 的安装参数与文件处理 | [安装说明](../src/layerweave/tool/builtin/developer/SKILLS.md) |
| 视图操作、数据结构、插件和语言包 | [视图首页](../src/layerweave/tool/builtin/view/README.md)按任务进入使用指南与开发专题 |
| 本地 KEY、连接说明与去除私有内容的示例 | [KEY 管理](../src/layerweave/tool/builtin/developer/keys/README.md) |

## 写法与示例

- 使用章节通常按“用途 → 最短示例 → 必要参数与返回 → 边界行为”展开；章节按实际内容选用。
- 实现说明按模块职责、执行流程、扩展位置组织，并链接对应使用说明。
- 一段集中解释一件事。独立规则用列表，参数和选项用表格，需要因果解释的内容保留短段落。
- 示例核对实际接口和返回。完整例子提供导入与初始化；依赖已有连接、配置或编号的片段明确列出前置条件。
- 示意编号要标明；可运行例子优先使用接口返回的编号。修改输出、参数或默认值时同步例子。
- 名称、用途、参数和默认值保持与源码、TOML、COMMANDS 一致。支持清单由现有 help 发现，不另建文档专用登记表。
- 软件执行接口称“内部工具”，分为使用、开发、视图三类；shared 表示共用支持。层原型 tools 所引用的能力称“外置技能”。正文使用中文解释，代码标识保持原名。
- 现行手册说明当前行为；未实现内容明确放入后续候选，历史报告保留当时语境。

## 修改与验证

1. 行为变化时更新主要说明及受影响示例；新增入口或移动文件时同步链接与章节跳转。
2. 文档修改检查相关链接、命令路径和示例。Python/JSON 语法正确不代表已运行；交付时区分语法检查和实际执行。
3. 验证范围与改动对应：纯文档修改运行文档检查和受影响示例；代码变化按开发指南执行测试。
4. 用任务查找成本、每次阅读量、准确性与重复程度评估文档。字节数作为辅助指标；比较时使用相同文件范围并考虑功能变化。

不设统一的字数或行数上限。允许简短的上下文重复，让读者理解当前任务；详细规则仍有明确的主要维护位置。

阶段计划完成后，先将仍有效的约定并入主要说明；旧交接报告先原样归档并核对，再移出现行入口。当前文档不链接旧报告作为接口依据，历史文本保留当时语境。component.toml 的 changes 只写当前版本摘要；内部实施历史保存在正式仓库之外，不在 README 或 AGENTS.md 中链接。正式发行记录与内部实施报告分开。正在协作维护的文档保留，清理范围按当前任务确认。

# LayerWeave 架构

LayerWeave 用层、对象、身份和关联组织内容。一个项目为层和对象提供身份范围；层组成树，对象归属于一个层，bind 表达可跨项目的普通引用。轴描述位置数值如何解释，基础结构不处理具体媒体。

## 三部分及依赖

| 部分 | 所在位置 | 负责什么 |
|---|---|---|
| 抽象核心 | src/layerweave/core、src/layerweave/models | Layer/Object、归属与引用字段、封装类型、类和继承约定 |
| 基础支撑 | src/layerweave/support | TOML 适配、类装配、SQLite、读取、发号、事务、日志和公共 CLI 外壳 |
| 可替换工具 | src/layerweave/tool/builtin | CDUR 协议、查询展示、编辑、内容检测、历史、撤销规划和帮助 |
| 外置技能 | src/layerweave/tool/skills | 供 AI 按需阅读和使用的独立技能包 |

依赖方向为工具 → 支撑 → 核心。模型本身可以独立使用；支撑不导入内置工具。默认工具显式请求可选检测提供者，缺席时仍可写入。完整工具包可单独增减，包内保留自己的业务辅助代码。

封装有三层含义：核心表达类、类型和继承约定；支撑从 TOML 读取并合并、定位类、还原实例；检测工具判断内容是否符合约定。没有任何工具时，Title 记录仍能往返为 Title 实例。

## 可见的扩展结构

models/layers 与 models/objects 保存 Python 类，src/layerweave/configs/layers 与 src/layerweave/configs/objects 保存对应 TOML。一份 TOML 对应一个类，派生类与派生配置同时存在。记录继续保存相对配置根目录的 config_ref，例如 objects/title.toml；固定分区用于帮助 AI 寻找与开发，不改成另一套类型编号。

## 统一写入入口

工具决定要修改什么，support 的写会话完成真实修改。编号、记录和 before/after 日志在一个事务内提交；operation_id 由入口生成，日志从实际写入收集。工具返回的业务结果不会替代这些日志。

工具也可以通过 register_tables 声明自己的业务表，接入同一个写会话。声明随数据库保存，支撑负责建表、追加字段和读写适配；工具代码缺席不影响已有数据的记录级读取与恢复。表自己的字段与引用不要求继承 Layer/Object，详细边界见[工具表开发指导](build-with-layerweave/03-managed-tables.md)。

| 规则 | 执行位置和结果 |
|---|---|
| 项目存在、所属层存在、父层存在、存储非空列 | SQLite 外键与列约束，失败回滚 |
| 托管身份、可写字段、簇内共用编号 | 支撑写入原语；默认项目簇含层、对象及 auto 的 scoped 工具表，provided 表默认不入簇；恢复保持原身份与计数上界 |
| 父链无环 | 支撑在提交前检查本批改变的父关系，以最终状态判断；成环回滚 |
| 普通位置落点 | 支撑写入时按当前轴精度处理，无精度时为 1e-6 |
| 原值迁移与恢复 | 支撑的明确入口保留位置值和必要的原身份，仍记日志并检查结构 |
| 内容类型、缺字段、重叠、接受对象类型、关联端点等 | 可替换检测工具，提交后报告；未安装则标记未检查 |

bind 是普通引用，目标失效不会使原始记录不可读。旧库中的父链环仍可查询、修复或删除；新增、复制或恢复不得重新提交环。基础类构造和属性赋值不增加自动检测。

发号在 support/numbering 中通过词条和普通规则函数调度；同一份登记保存计数位置及成员。它从当前写会话取得连接，只推进计数并返回身份；记录和日志仍由写入入口保存。外部 ID、簇范围与扩展规则见[编号说明](../src/layerweave/support/numbering/README.md)。

## 保持轻量

基础支撑当前仅使用 SQLite 和 TOML，不增加多后端、热卸载或依赖安装框架；视图工具自己的选装网页插件由其独立安装器管理。CLI 共用模块和命令静态发现位于支撑层，卸掉帮助工具不会破坏其他工具的 --help。命令按文件声明发现，外置技能 route/tier/when 仅供 AI 阅读，不自动执行或检查路由。

原始读取与区间查询保持数值，不转换轴单位。具体工具的分割内容、跨界策略和引用映射见[使用说明](../src/layerweave/tool/builtin/usage/README.md)。公共接口包括 core/models 的显式导出、support.api、发号入口、工具声明及专题明确说明的 commands/providers/feedback/paths 等开发辅助入口；__all__ 用于明确稳定入口，不是访问控制。内部实现模块保持可检查，扩展不应依赖私有辅助的路径。基础支撑的调用与扩展见[API](../src/layerweave/support/API.md)，开发准备见[开发指南](developer-conventions.md)。

## 包与安装边界

正式 Python 导入只使用 layerweave。core、models、support、tool/builtin 均位于 src/layerweave 下，目录与导入路径一致；层/对象类的 TOML class 路径同步使用 layerweave.models。数据库 config_ref 的 layers/...、objects/... 保持不变。

默认配置位于包内 configs，自带技能位于包内 tool/skills，SQL schema 跟随存储模块。它们明确作为资源分发。examples 在仓库根，不作为 Python 顶层包安装。技能正文和附件不会被内置命令发现器扫描或自动执行。

这层包名不改变依赖方向，也不要求安装所有工具。ZIP 下载目标默认是调用方工作目录的 tool/skills，可通过 skills_root 指定；不默认向普通安装的库目录追加内容。

基础部分与每个完整内部工具包分别用 component.toml 声明版本；Python 安装包版本由 layerweave.__version__ 维护，pyproject 动态读取该值。可选的[版本工具](../src/layerweave/tool/builtin/developer/versions/README.md)将扫描结果登记到自己的工具表，报告声明的存在状态，不参与工具运行许可或基础读写流程。

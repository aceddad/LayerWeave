# 用 LayerWeave 开发自己的工具（给 AI）

你可以把 LayerWeave 当作组织数据、保存关系和记录修改的底座，按需接入自己的工具。工具只处理当前任务关心的数据；它的界面、算法、参数、缓存和临时结果，由工具自己设计。

本页面向在自己工程中编写工具、封装或插件的 AI 与开发者，按接入思路分篇。安装方式见[项目首页](../../README.md)，具体参数见[基础支撑 API](../../src/layerweave/support/API.md)。仅操作已有项目时使用[使用入口](../../src/layerweave/tool/builtin/usage/README.md)；需要修改 LayerWeave 自身实现时，再进入[源码开发指南](../developer-conventions.md)。

## 选择一种思路

| 篇目 | 主要思路 | 适用例子 |
|---|---|---|
| [一：嵌套层与时序](01-timeline.md) | 用父子层组织模块，用对象位置安排内容出现的时段 | 手书、分镜、字幕、音视频编排 |
| [二：有序列表与隐藏信息管理](02-ordered-metadata.md) | 用层保存有序条目，用关联指向内容，由工具选择展示方式 | 批注、审阅、待办、制作过程信息 |
| [三：工具自己的表统一管理](03-managed-tables.md) | 声明工具表，复用记录级读写、事务、历史与撤销 | 独立的业务记录、工具任务、专用结构 |
| [四：一个事务组合多个工具](04-composing-tools.md) | 使用公开事务内入口，一次提交、反馈和检测 | 接续后平移、保存后编辑、撤销后修订 |
| [五：持续读取变化](05-incremental-reading.md) | 初始快照加日志游标，按后续业务变化刷新 | 视图刷新、索引、工具缓存 |
| [六：统一 MCP 入口适配 AI](06-mcp-components.md) | 查询目录、按需展开组件声明，再交给约定的调用方式 | AI 使用自定义组件、插件能力目录 |
| [七：声明服务](07-declaration-services.md) | 统一保存、查询声明及其关系，由消费工具解释 | 生命周期钩子、协议；含两级流程与单链转序号示例 |

这些是可以并用的方式，后面的篇目也可以继续扩充。一个项目可以有多个 root，按模块或范围读取；创建新功能时先复用已有类型，有独立的类型约定时再增加封装。

六、七说明如何用现有结构开发上层工具：目录读取、记录与关联已有接口，动态加载、钩子执行及协议处理由适配工具实现。

## 可组合的技巧

- [project 分区与定向读取](tip-project-scopes.md)：用项目划分逻辑范围，再由外置关系表选择各个消费者要读取的内容；统一存储，分别取用。可与上述任一种用法结合，不要求每个组件单独建立项目。

## 可以自由决定什么

| 你要组织的内容 | 可以怎样使用现有结构 |
|---|---|
| 业务内容与状态 | 在对象 information 中组织 JSON 内容，按需要提供自己的封装约定 |
| 工具行为偏好 | 在对应 TOML 中增加自定义段，由消费它的工具解释 |
| 画面、面板与隐藏信息 | 由工具选择展示哪些层和对象；内容仍可通过普通接口读取 |
| 缓存、导出文件、临时计算结果 | 放在工具自己的工作目录；需要进入项目的内容再通过接口保存 |
| 工具自己的业务记录、身份或计数 | 声明专属表；可以复用层编号、独立编号或登记发号簇 |

## 从最小接入开始

| 当前需要 | 入口 |
|---|---|
| 读取普通记录、筛选对象、取得直接关联 | support.api 的 read_record、query_objects、read_bindings |
| 只修改几个字段，或一次组合多个修改 | run_operation 或 transaction 中的 write 原语；高级工具见[事务内组合](04-composing-tools.md) |
| 使用 Python 派生实例，或保存整层与装载对象 | load_layer/load_object、save_layer/save_object |
| 使用现成的查询展示、编辑、历史或撤销 | 对应的[内部工具包](../../src/layerweave/tool/builtin/README.md) |
| 用 JSON 表达批量操作或复用场景模板 | [交换工具](../../src/layerweave/tool/builtin/usage/exchange/README.md)；新模板只需添加 JSON |
| 声明工具表、复用层编号或共享发号 | [工具表](03-managed-tables.md)与[编号模块](../../src/layerweave/support/numbering/README.md)；可运行示例在[示例索引](../examples.md) |
| 为已有数据提供专用页面或侧栏 | [视图插件协议](../../src/layerweave/tool/builtin/view/PLUGINS.md)，通过 host 接口接入 |
| 让 AI 发现工具用途、调用方式与版本 | [命令声明](../../src/layerweave/tool/builtin/shared/help/COMMANDS.md)负责使用说明，[组件声明](../../src/layerweave/tool/builtin/developer/versions/README.md#声明放在哪里)负责版本登记 |

可以直接在自己的 Python 工程里导入公开接口。借用写会话不要求使用 CDUR 请求格式，也不要求构造完整的 Layer/Object 实例。读取普通记录时，配置文件和类不必可用；需要还原派生实例时再用 load。

查询现有封装时，普通调用使用默认配置 help；需要查看完整定义、继承来源和 TOML 时再使用开发模式，见[两种配置 help](../../src/layerweave/tool/builtin/shared/help/CONFIG_HELP.md)。

工具提交当前需要修改的字段，支撑统一维护身份、归属和事务日志。information、axis 等 JSON 字段整体替换；修改其中一个键时在同一会话中读取并合并，示例见[局部修改](02-ordered-metadata.md#只修改自己关心的字段)。

“挂载工具”在这里指工具使用这套数据与配置能力。普通函数就能完成接入；需要进入命令 help 时，再按[命令声明](../../src/layerweave/tool/builtin/shared/help/COMMANDS.md)提供 COMMANDS。层配置里的 tools 是供 AI 阅读的技能路由，执行方式由调用方选择。

不确定一个字符串是配置路径、代码入口还是登记名称时，查[入口与标识](../developer-conventions.md#入口路径与调度标识)，再进入对应专题。

## 把工具放在哪里

- 在外部项目开发：导入 layerweave 的公开接口，代码、依赖与工作目录由你的项目管理。
- 作为 LayerWeave 内部工具提供：在 tool/builtin 对应分类放置完整包，通用入口复用 support，包内保留业务辅助实现。
- 作为 AI 按需阅读的外置技能提供：按[技能导引](../../src/layerweave/tool/README.md)组织 SKILL.md、脚本与资源。

先完成最小的读取或写入流程，再按真实需求增加封装、配置和展示方式。安装所有工具、建立完整场景模板、接入视图或 MCP，都不是使用数据底座的前置步骤。

# LayerWeave 工作导引

可独立增减的软件操作包统称为“内部工具”，放在 src/layerweave/tool/builtin；基础读写、事务和发号位于 support。供层原型 tools 引用的外置技能放在 src/layerweave/tool/skills。

- 操作项目内容：从[使用工具](src/layerweave/tool/builtin/usage/README.md)选择操作，参数和示例由各工具 help 提供。
- 用 JSON 批量操作或套用模板：读[交换工具](src/layerweave/tool/builtin/usage/exchange/README.md)，格式与引用见 FORMAT，自行扩充见 DEVELOPMENT；归属不符跳过并报告。
- 借用 LayerWeave 开发自己的工具：先读[AI 开发指导](docs/build-with-layerweave/README.md)，按篇选择嵌套时序或有序管理等接入方式。
- 修改代码或增加封装：先读[开发指南](docs/developer-conventions.md)，再读对应配置、API 和实现专题。
- 一批操作共同提交：读[事务内组合](docs/build-with-layerweave/04-composing-tools.md)，使用 *_in_session(write, ...)；独立工具入口不嵌套，检测由最外层配置。
- 持续刷新视图或缓存：读[增量接入](docs/build-with-layerweave/05-incremental-reading.md)，初始数据与日志游标共用读取快照；业务日志从 support.api.read_changes 连续读取。
- 接入工具自己的表：读[工具表开发指导](docs/build-with-layerweave/03-managed-tables.md)，字段、身份、引用和恢复的范围以此为准；随交换复制的附着状态用 logical_references 与 exchange.on_copy 声明。
- 分辨路径或调度名称：读[入口与标识](docs/developer-conventions.md#入口路径与调度标识)，区分配置、技能、命令、发号词条和组件名称。
- 维护组件版本与更新说明：读[版本登记](src/layerweave/tool/builtin/developer/versions/README.md)，更新组件自己的 component.toml；sync 自动登记并核对，read 只看上次记录。
- 开放工具自己的 ID 或扩展发号：读[编号模块](src/layerweave/support/numbering/README.md)，规则使用当前写会话；发号不创建业务行，簇成员集中登记。
- 修改文档：读取[文档约定](docs/documentation.md)，保持主题有明确的主要维护位置。
- 新增外置技能：读[工具区](src/layerweave/tool/README.md)，特殊场景另见[场景补充区](src/layerweave/tool/skills/scenarios/README.md)。技能自带 SKILL.md；实际绑定由 AI 按任务填写。
- 调用外部模型服务：读[KEY 与连接说明](src/layerweave/tool/builtin/developer/keys/README.md)，先区分已有环境变量和本地 JSON；输出目录由 AI 按项目安排。LayerWeave 自身的读写接口见[基础支撑 API](src/layerweave/support/API.md)。
- 视图工作：从[视图入口](src/layerweave/tool/builtin/view/README.md)按任务阅读；修改实现见[视图开发说明](src/layerweave/tool/builtin/view/DEVELOPMENT.md)，继续使用 visualization 分支。

## 工作要求

- 核心与模型保持简单。core 表达抽象结构与封装语义，support 提供存储和配置适配，src/layerweave/tool/builtin 提供可替换能力；依赖方向见[架构](docs/architecture.md)。
- 业务数据库的记录写入走 layerweave.support.api.transaction 或 run_operation，包括工具表和恢复。工具表结构通过 register_tables 声明，由支撑创建或追加列；工具不绕过入口执行 SQL 写入、提交或拼装日志。自动发号通过支撑 allocate；provided 表可由工具提供稳定正整数 ID，不把旧身份分配给无关记录。KEY 管理的本地 JSON 配置不进入业务库和 changes 日志。
- 一个完整工具包是增减单位；业务辅助代码留在包内。不引用另一个可卸载包的私有实现。共用 CLI 和声明发现来自 support。
- 一份封装 TOML 对应一个 Python 类，保留 layers/objects 分区及 config_ref。不要为抽象而加入其他后端或新注册框架。
- 默认工具通过可选提供者接入内容检测。未安装检测包应返回未检查；父链无环和其他结构保证不能依赖检测包。
- 保留用户数据和无关改动；测试、示例用内存或专用临时数据库，不写 output 的实际数据库。
- 查现行代码优先搜索 src/layerweave、tests、examples、docs；scratch 保留本地备份，不作为现行实现依据。不为清理搜索结果而删除或迁移它。
- 修改持久化、执行入口或模块路径后运行完整回归和隔离验收，方法见开发指南。当前未发布，不保留旧路径转接。
- MCP 编排留到对应封装阶段；main 保持无 GUI 依赖。

# LayerWeave 工作导引

软件自身的执行能力统称为“内部工具”，放在 src/layerweave/tool/builtin；供层原型 tools 引用的外置技能放在 src/layerweave/tool/skills。

- 操作项目内容：从[使用工具](src/layerweave/tool/builtin/usage/README.md)选择操作，参数和示例由各工具 help 提供。
- 借用 LayerWeave 开发自己的工具：先读[AI 开发指导](docs/build-with-layerweave/README.md)，按篇选择嵌套时序或有序管理等接入方式。
- 修改代码或增加封装：先读[开发指南](docs/developer-conventions.md)，再读对应配置、API 和实现专题。
- 维护组件版本与更新说明：读[版本登记](src/layerweave/tool/builtin/developer/versions/README.md)，更新组件自己的 component.toml；sync 自动登记并核对，read 只看上次记录。
- 修改文档：读取[文档约定](docs/documentation.md)，保持主题有明确的主要维护位置。
- 新增外置技能：读[工具区](src/layerweave/tool/README.md)，特殊场景另见[场景补充区](src/layerweave/tool/skills/scenarios/README.md)。技能自带 SKILL.md；实际绑定由 AI 按任务填写。
- 调用外部模型服务：读[KEY 与连接说明](src/layerweave/tool/builtin/developer/keys/README.md)，先区分已有环境变量和本地 JSON；输出目录由 AI 按项目安排。LayerWeave 自身的读写接口见[基础支撑 API](src/layerweave/support/API.md)。
- 视图工作：读[视图边界](src/layerweave/tool/builtin/view/README.md)，开始实现时再建独立分支。

## 工作要求

- 核心与模型保持简单。core 表达抽象结构与封装语义，support 提供存储和配置适配，src/layerweave/tool/builtin 提供可替换能力；依赖方向见[架构](docs/architecture.md)。
- 业务数据库的记录写入走 layerweave.support.api.transaction 或 run_operation，包括工具表和恢复。工具表结构通过 register_tables 声明，由支撑创建或追加列；工具不绕过入口执行 SQL 写入，不自行发号、提交或拼装日志。KEY 管理的本地 JSON 配置不进入业务库和 changes 日志。
- 一个完整工具包是增减单位；业务辅助代码留在包内。不引用另一个可卸载包的私有实现。共用 CLI 和声明发现来自 support。
- 一份封装 TOML 对应一个 Python 类，保留 layers/objects 分区及 config_ref。不要为抽象而加入其他后端或新注册框架。
- 默认工具通过可选提供者接入内容检测。未安装检测包应返回未检查；父链无环和其他结构保证不能依赖检测包。
- 保留用户数据和无关改动；测试、示例用内存或专用临时数据库，不写 output 的实际数据库。
- 查现行代码优先搜索 src/layerweave、tests、examples、docs；scratch 保留本地备份，不作为现行实现依据。不为清理搜索结果而删除或迁移它。
- 修改持久化、执行入口或模块路径后运行完整回归和隔离验收，方法见开发指南。当前未发布，不保留旧路径转接。
- MCP 编排留到对应封装阶段；main 保持无 GUI 依赖。

工具表扩展的实施与验收记录见[扩展记录](docs/tool-tables-plan.md)，现行接入方式见[工具表开发指导](docs/build-with-layerweave/03-managed-tables.md)。

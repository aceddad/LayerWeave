# 开发约定

本文件用于维护 LayerWeave 自身源码。先按任务选择入口：

- 操作项目内容：读[使用入口](src/layerweave/tool/builtin/usage/README.md)，按需查询命令与配置 help。
- 接入 MCP 或维护命令暴露：读[MCP](src/layerweave/tool/builtin/shared/mcp/README.md)，参数以工具自身 input_schema 为准，direct/routed 共用绑定。
- 在自己的工程中开发工具或插件：读[扩展指南](docs/build-with-layerweave/README.md)，复用公共接口。
- 修改本仓库的实现：遵循下列约定和[开发指南](docs/developer-conventions.md)。

使用软件或编写外部扩展时，无需执行本仓库的源码维护流程；扩展代码纳入本仓库时再遵循相应约定。

## 定位代码

- `src/layerweave/core`、`models`：抽象结构和封装类。
- `src/layerweave/support`：存储、配置、发号、事务与公共接口。
- `src/layerweave/tool/builtin`：可独立增减的内部工具；`tool/skills`：供 AI 使用的外置技能。
- `frontend/view`：网页源码；进入该目录前读其 AGENTS.md。
- `tests`、`examples`：回归测试和可运行示例。

按任务阅读[文档入口](docs/README.md)。环境与命令见[开发指南](docs/developer-conventions.md)，依赖边界见[架构](docs/architecture.md)。

## 修改原则

- 依赖方向为工具 → 支撑 → 核心。完整工具包携带自己的业务辅助代码，不引用其他可卸载包的私有实现。
- 业务数据写入经过 `transaction` / `run_operation`；组合写入使用同一写会话。表通过 `register_tables` 声明，自动发号通过支撑 `allocate`。不直接提交 SQL 或拼装修改日志。
- 一份封装 TOML 对应一个 Python 类，保留 layers/objects 分区与 config_ref。构造和赋值不自动检查内容。
- 内容检测可选；归属、父链无环等结构保证由支撑层负责，不能依赖检测工具。
- 保留无关改动、用户数据库、技能及本地配置。测试使用临时数据；密钥不进入版本控制。
- 优先搜索 src/layerweave、frontend/view、tests、examples、docs。scratch、output 是本地材料，不作为现行实现依据，不为整理目录而清空。
- 视图继续在 visualization 分支维护，main 保持无 GUI 依赖。

## 验证与文档

先运行受影响检查；持久化、执行入口或模块路径变化需完整 Python 回归，打包资源变化需普通安装验收。具体命令见开发指南。

README 介绍项目和上手方式；AGENTS.md 维护工作约定；详细接口说明留在对应模块。公开文档描述当前行为，不加入本次会话、实施过程、测试汇报或内部交接链接。文档调整核对链接与示例，按[文档约定](docs/documentation.md)维护。

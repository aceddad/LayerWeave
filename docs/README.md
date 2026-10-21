# LayerWeave 文档

按当前任务选择路径；AI 与人使用同一份工具说明，不需要先通读源码。

## 使用 LayerWeave 操作项目

- [使用入口](../src/layerweave/tool/builtin/usage/README.md)：从任务选择工具，按需查询命令与配置 help。
- [MCP 接入](../src/layerweave/tool/builtin/shared/mcp/README.md)：stdio 启动、直接 JSON、常用独立入口与技能材料。
- [JSON 导入导出](../src/layerweave/tool/builtin/usage/exchange/README.md)：批量写回、复制和场景模板。
- [视图](../src/layerweave/tool/builtin/view/README.md)：画布、批注、截图与选装插件。
- [技能与外部服务](../src/layerweave/tool/README.md)：查找技能、连接信息与输出目录。
- [Python 示例](examples.md)：可运行的接口调用示例。
- [场景演示](../examples/showcases/README.md)：已收录十二个场景案例，附可导入数据与使用说明，推荐从文章解析开始。
- [手书制作流程](workflows/hand-drawn-video.md)：从主旨、故事到 Remotion 合成的制作步骤，以及每一步放在哪一层、可用哪些技能。

## 开发自己的扩展

- [扩展指南](build-with-layerweave/README.md)：在自己的工程中接入时序、有序列表、自有表和组合操作。
- [基础 API](../src/layerweave/support/API.md)：读取、写入、事务和实例装配。
- [内部工具开发](../src/layerweave/tool/builtin/developer/README.md)：新增工具、封装与配置。
- [视图插件](../src/layerweave/tool/builtin/view/PLUGINS.md)：独立页面、侧栏与发布协议。
- [配置 help](../src/layerweave/tool/builtin/shared/help/CONFIG_HELP.md)：开发模式可查询完整定义与继承关系。

## 维护 LayerWeave 源码

- [AGENTS.md](../AGENTS.md)：本仓库的工作约定和任务分流。
- [开发指南](developer-conventions.md)：准备环境、定位源码、运行检查。
- [测试导引](../tests/README.md)：按功能选择回归范围和共享夹具。
- [发布验收](releasing.md)：wheel、源码包、许可与隔离重建。
- [架构](architecture.md)：核心、支撑、工具的职责和依赖。
- [文档约定](documentation.md)：说明的放置位置、示例与维护方式。

具体参数以工具的 --help 或 command_help 为准。尚未提供的能力集中在[后续方向](FUTURE.md)，不作为当前接口使用。

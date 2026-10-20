# LayerWeave 文档

本页是 main 无视图开发分支的导引。视图、MCP 服务和发行说明见[完整版本](https://gitee.com/emotion1354414/layer-weave/tree/visualization)。按当前任务选择路径；AI 与人使用同一份工具说明，不需要先通读源码。

## 使用 LayerWeave 操作项目

- [使用入口](../src/layerweave/tool/builtin/usage/README.md)：从任务选择工具，按需查询命令与配置 help。
- [JSON 导入导出](../src/layerweave/tool/builtin/usage/exchange/README.md)：批量写回、复制和场景模板。
- [技能与外部服务](../src/layerweave/tool/README.md)：查找技能、连接信息与输出目录。
- [Python 示例](examples.md)：可运行的接口调用示例。
- [场景演示](../examples/showcases/README.md)：完整使用案例的存放位置与组织方式，目前尚未收录完成的案例。

## 开发自己的扩展

- [扩展指南](build-with-layerweave/README.md)：在自己的工程中接入时序、有序列表、自有表和组合操作。
- [基础 API](../src/layerweave/support/API.md)：读取、写入、事务和实例装配。
- [内部工具开发](../src/layerweave/tool/builtin/developer/README.md)：新增工具、封装与配置。
- [配置 help](../src/layerweave/tool/builtin/shared/help/CONFIG_HELP.md)：开发模式可查询完整定义与继承关系。

## 维护 LayerWeave 源码

- [AGENTS.md](../AGENTS.md)：本仓库的工作约定和任务分流。
- [开发指南](developer-conventions.md)：准备环境、定位源码、运行检查。
- [测试导引](../tests/README.md)：按功能选择回归范围和共享夹具。
- [架构](architecture.md)：核心、支撑、工具的职责和依赖。
- [文档约定](documentation.md)：说明的放置位置、示例与维护方式。

具体参数以工具的 --help 或 command_help 为准。尚未提供的能力集中在[后续方向](FUTURE.md)，不作为当前接口使用。

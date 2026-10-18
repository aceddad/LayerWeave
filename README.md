# LayerWeave 开发源码

用层、对象和关联组织内容，为自己的 AI 工具提供可复用的 Python 内核与内部工具。

main 是无视图开发分支，包含核心、模型、基础支撑、非视图内部工具、配置、模板和技能材料。与 visualization 分支共用的实现和组件版本保持一致；开发者直接调用 Python 或 CLI，并按完整工具包增减能力。视图与面向使用者的 MCP 服务封装位于[完整版本](https://gitee.com/emotion1354414/layer-weave/tree/visualization)，不随本分支安装。

## 开始开发

需要 Python 3.11+ 和 SQLite 3.35+。在自己的虚拟环境中，从源码根运行：

```sh
python -X utf8 -m pip install -e ".[dev]"
python -X utf8 -B examples/read_write.py
python -X utf8 -m layerweave.tool.builtin.shared.help.command_help
```

可编辑安装让其他工作目录也能导入 layerweave，源码修改直接生效。pyproject.toml 仅提供这一本地开发入口和依赖声明；本分支不单独制作面向使用者的发行包。核心与普通内部工具运行只需标准库，dev 依赖用于开发验证。

命令显式使用 -X utf8，便于中文 Windows 的管道调用；也可设置 PYTHONUTF8=1，见[编码说明](src/layerweave/tool/builtin/usage/README.md#命令行编码)。

## 从任务选择入口

- [使用现成内部工具](src/layerweave/tool/builtin/usage/README.md)：读写项目、查询层树、编辑时序、历史与撤销、JSON 交换和场景模板。
- [开发自己的扩展](docs/build-with-layerweave/README.md)：接入工具自有表、组合写会话、增量读取与编号规则。
- [基础 API](src/layerweave/support/API.md)：读取、写入、模型装配与事务。
- [维护本分支](docs/developer-conventions.md)：源码位置、依赖边界及测试。
- [完整示例](docs/examples.md)、[文档目录](docs/README.md)：按需要深入，不必先通读源码。

不知道支持哪些操作或封装时，使用 command_help / config_help；它们从当前安装的声明生成说明。命令里的 mcp 元信息可供外部适配器读取，不会自行启动 MCP 服务。技能是供 AI 按需阅读的材料，使用前确认其依赖、KEY 与输出目录。

## 许可证

LayerWeave 源码采用 [MIT](LICENSE)。独立技能、外部库和服务遵循其自身说明。视图构建与第三方网页组件的分发说明见完整版本。

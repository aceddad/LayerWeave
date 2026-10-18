# LayerWeave 开发源码

**简体中文** | [English](README.en.md)

用层、对象和关联组织内容，为自己的 AI 工具提供可复用的 Python 内核与内部工具。

main 是无视图开发分支，包含核心、模型、基础支撑、非视图内部工具、配置、模板和技能材料。开发者直接调用 Python 或 CLI，并按完整工具包增减能力。共用实现与 visualization 保持一致；视图、MCP 服务和面向使用者的发行封装在完整分支维护，不随 main 安装。

## 开始开发

首发以 Windows 为支持平台；代码要求 Python 3.11+ 和 SQLite 3.35+。取得本分支源码后，可以让 [uv](https://docs.astral.sh/uv/getting-started/installation/) 自动准备 Python。在源码根的 PowerShell 中运行：

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
.venv/Scripts/python.exe -X utf8 -B examples/read_write.py
```

uv 默认会下载缺少的 Python；首次准备环境和依赖需要联网。无需激活环境，直接使用其中的解释器。已有 Python、希望使用 pip 时：

```powershell
python -X utf8 -m venv .venv
.venv/Scripts/python.exe -X utf8 -m pip install -e ".[dev]"
.venv/Scripts/python.exe -X utf8 -B examples/read_write.py
```

可编辑安装让其他工作目录也能导入 layerweave，源码修改直接生效。pyproject.toml 提供本地开发入口；本分支不单独制作面向使用者的发行包。核心和普通工具运行只需标准库，dev 依赖用于开发验证。示例使用临时数据，不修改实际项目。

## 按需查看接口

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

command_help 展示当前安装的工具与调用示例，config_help 展示层和对象的用途、字段和封装关系。命令中的 mcp 元信息供外部适配器读取，不会自行启动服务。

- [使用现成工具](src/layerweave/tool/builtin/usage/README.md)：读写项目、查询、时序编辑、历史与撤销、JSON 交换和场景模板。
- [基础 API](src/layerweave/support/API.md)：原始读取、写入、模型装配和事务。
- [扩展指南](docs/build-with-layerweave/README.md)：工具自有表、组合写会话、增量读取与编号规则。
- [维护源码](docs/developer-conventions.md)、[完整示例](docs/examples.md)、[文档目录](docs/README.md)。

业务记录写入复用统一入口；新增封装同时提供 Python 类与 TOML。完整工具包可替换或移除。技能是供 AI 按需阅读的材料，使用前确认其依赖、KEY 与输出目录。

## 验证改动

```powershell
.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s tests -t . -v
```

测试按 architecture、foundation、tools 分类，使用临时数据，详见[测试导引](tests/README.md)。Windows 管道命令显式使用 -X utf8；也可设置 PYTHONUTF8=1，见[编码说明](src/layerweave/tool/builtin/usage/README.md#命令行编码)。

## 许可证

LayerWeave 源码采用 [MIT](LICENSE)。独立技能、外部库和服务遵循其自身说明。视图构建与第三方网页组件的分发说明见 visualization 分支。

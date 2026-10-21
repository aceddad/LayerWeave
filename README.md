# LayerWeave 开发源码

**简体中文** | [English](README.en.md)

**把工作内容组织成 Agent 能操作、工具能复用的项目。**

LayerWeave 把内容、它们之间的联系和反馈保存在同一份项目里，让人、Agent 和不同工具接着处理这些内容。图片、音视频通过文件路径或链接引用。

这里是 main 开发分支，可直接使用 Python 和 CLI。网页视图、批注工具、MCP 服务与发行封装在 visualization 完整分支；共用的核心、基础支撑与非视图工具保持一致。

## 从具体工作开始

**读文章，沿着论点找依据。** 查询一个论点关联的正文、解读、证据和配图，只展开当前需要的部分。修改解读时保留它与正文的联系。[文章解析案例](examples/showcases/article-reading/README.md)提供五条可运行的阅读路线，基础 Python/CLI 即可完成。

**做分镜，把镜头与素材、做法连起来。** 将镜头关联到故事段落、图片和实现说明，按对象或区间查询、修改，查看历史或撤销操作。[动态分镜与 H3 案例](examples/showcases/donut-hole-h3/README.md)以静帧展示 60 个镜头，无需下载视频。

**通过批注接续协作。** 完整版本支持在具体内容旁留言、回复和标记处理，让其他人或 Agent 稍后接着工作。[晚开的花](examples/showcases/late-bloom-scroll/README.md)展示四个 Agent 核对画面接缝的过程；这个案例使用完整版本的批注类型。

内容可以按段落、页码、顺序或时间组织，再通过关联连接。[查看全部十二个案例](examples/showcases/README.md)。

## 开发自己的工具

例如，给角色和镜头建立关联后，可以编写一个“按人物汇总镜头”的工具，查询已有项目，并复用项目的读写、编号和改动记录来保存结果。

开发者和 Agent 可以使用现有内容结构，也可以增加自己的类型或数据表。工具包可按需增减，底层读写可以直接嵌入自己的 Python 工程；需要专用界面时，再接入完整版本的视图插件。

从[扩展指南](docs/build-with-layerweave/README.md)选择最小接入方式；[工具自有表的可运行示例](examples/tool_tables.py)展示如何让新工具沿用记录、历史与撤销。具体调用见[公共 API](src/layerweave/support/API.md)。

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

源码安装还需要 setuptools>=77.0.3 和 wheel。pip 默认在临时构建环境中准备它们，即使当前环境已有 setuptools，也可能联网下载。若卡在 Installing build dependencies，先看[源码安装排查](docs/developer-conventions.md#可编辑安装与构建依赖)；只有提前装好构建依赖后，才适合关闭构建隔离。

体验案例时，在同一个 PowerShell 中设置 `$casePython = (Resolve-Path .venv/Scripts/python.exe).Path`，再按所选案例的说明导入和查询。

## 按需查看接口

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

command_help 展示当前安装的工具与调用示例，config_help 展示层和对象的用途、字段和封装关系。命令中的 mcp 元信息供外部适配器读取，不会自行启动服务。

- [使用现成工具](src/layerweave/tool/builtin/usage/README.md)：读写项目、查询、时序编辑、历史与撤销、JSON 交换和场景模板。
- [维护源码](docs/developer-conventions.md)、[完整示例](docs/examples.md)、[文档目录](docs/README.md)。

业务记录写入复用统一入口；新增封装同时提供 Python 类与 TOML。完整工具包可替换或移除。技能是供 AI 按需阅读的材料，使用前确认其依赖、KEY 与输出目录。

## 验证改动

```powershell
.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s tests -t . -v
```

测试按 architecture、foundation、tools 分类，使用临时数据，详见[测试导引](tests/README.md)。Windows 管道命令显式使用 -X utf8；也可设置 PYTHONUTF8=1，见[编码说明](src/layerweave/tool/builtin/usage/README.md#命令行编码)。

## 许可证

LayerWeave 源码采用 [MIT](LICENSE)。独立技能、外部库和服务遵循其自身说明。视图构建与第三方网页组件的分发说明见 visualization 分支。

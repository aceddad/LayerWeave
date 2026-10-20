# LayerWeave

**简体中文** | [English](README.en.md)

用层、对象和关联组织内容，让 AI 与程序按需读取、编辑和扩充项目。

LayerWeave 提供 Python API、命令行工具、MCP 接入和本机网页视图，适合字幕、分镜、手书、素材清单及有序信息管理。对象保存内容与起止位置，层组织结构，关联连接条目，轴说明位置数值的含义。

## 能做什么

- 查询层树，按子树、对象或时间区间读取；按名字或稳定键更新，保留身份与关联。
- 接续、排列、分割、平移、复制与搬移对象，通过 JSON 批量导入导出。
- 用 SQLite 保存数据和修改历史，按操作撤销与重做。
- 用 Python 类、TOML 和工具自有表扩展，按完整工具包增减能力。
- 在画布上查看项目、添加批注并与 AI 协作；一览、接缝和预览插件独立选装。

界面支持中文与英文，用户内容保持原文。媒体对象保存资源引用，生成和处理媒体由技能或调用方完成。

## Windows 快速开始

首发支持 Windows。代码要求 Python 3.11+、SQLite 3.35+；以下使用 Python 3.11。可以让 [uv](https://docs.astral.sh/uv/getting-started/installation/) 自动准备 Python 和环境，也可以使用已有 Python。使用网页不需要 Node。

### 安装完整包

先取得本版本的 `layerweave-0.7.6-py3-none-any.whl`，放在选定的工作目录。安装 uv 后，在该目录的 PowerShell 中执行：

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe "./layerweave-0.7.6-py3-none-any.whl[mcp]"
```

缺少合适的 Python 时，uv 默认会自动下载。首次准备环境和依赖需要联网；无需激活虚拟环境，后续直接使用其中的解释器。[uv 的 Python 管理说明](https://docs.astral.sh/uv/concepts/python-versions/)

已有 Python、希望使用 pip 时，对应步骤是：

```powershell
python -X utf8 -m venv .venv
.venv/Scripts/python.exe -X utf8 -m pip install "./layerweave-0.7.6-py3-none-any.whl[mcp]"
```

`[mcp]` 安装 AI 接入需要的可选依赖；只用 Python/CLI 时可以去掉。安装不会自动装入官方视图插件。这里使用本地 wheel，不假定同名版本已经发布到 PyPI。

wheel 已构建好，安装 LayerWeave 本身不需要 setuptools；`[mcp]` 的依赖仍可能需要联网下载，wheel 不是完整离线环境。维护源码才需要可编辑安装；若卡在准备构建依赖，见[源码安装排查](docs/developer-conventions.md#可编辑安装与构建依赖)。

### 创建项目并打开视图

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.developer.database.cli project.sqlite3
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli templates
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply project.sqlite3 --template subtitles --new-project
```

模板可选字幕、分镜或手书，结构可自由增减。导入输出会给出项目编号，将下方 `PROJECT_ID` 换成实际编号：

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.query.project_overview project.sqlite3 PROJECT_ID
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.view.server project.sqlite3 --project PROJECT_ID
```

打开服务输出的本机地址。FFmpeg 是用户选装的外部程序，不随 wheel、`[mcp]` 或 uv 自动安装；普通数据管理与文字视图不需要它。服务端抽帧需要 FFmpeg，缩略图和波形也会使用它；缺少时部分浏览功能回退，可能增加媒体加载量。安装后将其 bin 目录加入 PATH，或用 `FFMPEG` 指向 ffmpeg.exe 的完整路径（如 `D:/tools/ffmpeg/bin/ffmpeg.exe`），见[安装与功能影响](src/layerweave/tool/builtin/view/GUIDE.md#选装-ffmpeg)。AI 截图另外需要 Chrome、Edge 或 Chromium。媒体输出目录由 AI 或使用者选择。

## 连接 AI / MCP

在项目工作目录保存 `mcp.json`，workspace 使用实际绝对路径：

```json
{"workspace": "D:/my-project"}
```

在支持 stdio MCP 的客户端中配置，例如：

```json
{
  "mcpServers": {
    "layerweave": {
      "command": "D:/my-project/.venv/Scripts/python.exe",
      "args": ["-X", "utf8", "-m", "layerweave.tool.builtin.shared.mcp", "--config", "D:/my-project/mcp.json"]
    }
  }
}
```

将解释器和配置文件路径换成实际位置；具体配置入口由客户端决定。AI 可先调用 `layerweave_help` 查支持能力，再定向操作，无需每次读取整个项目。数据库与项目编号可按调用传入，也可设置默认值，见[MCP 说明](src/layerweave/tool/builtin/shared/mcp/README.md)。

只接 MCP 时，也可让 uvx 一条命令准备环境并启动服务：

```powershell
uvx --python 3.11 --from "./layerweave-0.7.6-py3-none-any.whl[mcp]" layerweave-mcp --config ./mcp.json
```

这条命令会持续运行 stdio 服务，通常由 MCP 客户端托管；它不是启动网页的命令。客户端中的 uvx 配置使用绝对路径，完整例子见 MCP 说明。安装包放到正式下载地址后，也可通过 URL 指定来源，无需另写一套业务接口。

## 按需查帮助与扩展

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

- [使用入口](src/layerweave/tool/builtin/usage/README.md)：从任务选择工具，读取输入、输出和示例。
- [JSON 交换与模板](src/layerweave/tool/builtin/usage/exchange/README.md)：批量操作与场景起点。
- [视图与插件](src/layerweave/tool/builtin/view/README.md)：界面操作；[官方插件仓库](https://gitee.com/emotion1354414/layerweave-plugins)独立选装，零插件可用。
- [扩展指南](docs/build-with-layerweave/README.md)：编写自己的工具、封装和工具表。
- [源码开发](docs/developer-conventions.md)、[完整示例](docs/examples.md)、[文档目录](docs/README.md)。

`visualization` 是完整版本；`main` 是无视图开发源码，保留直接 Python/CLI 入口，共用核心、支撑和非视图工具。视图、MCP 服务及发行封装在完整分支维护。命令中的 `-X utf8` 用于中文 Windows 的管道输出，详见[编码说明](src/layerweave/tool/builtin/usage/README.md#命令行编码)。

## 许可证

LayerWeave 自身采用 [MIT](LICENSE)。网页中的第三方组件保留各自许可，见[第三方声明](THIRD_PARTY_NOTICES.md)。独立插件、技能和外部服务遵循其自身说明。

# LayerWeave

**简体中文** | [English](README.en.md)

**0.7.8 公开预览版 · Windows**

**把工作内容组织成 Agent 能操作、工具能复用的项目。**

LayerWeave 把内容、它们之间的联系和反馈保存在同一份项目里。人可以查看具体内容、留下意见；Agent 可以找到相关部分，读取、修改并继续工作。图片、音视频通过文件路径或链接引用。

## 可以怎样用

**读文章，沿着论点找依据。** 把正文、解读、证据和配图联系起来。选一个论点，就能找到对应的材料；让 Agent 只展开这一部分，修订解读时保留它与正文的联系。[文章解析案例](examples/showcases/article-reading/README.md)提供五条可以实际运行的阅读路线，适合第一次体验。

**做分镜，把镜头与素材、做法连起来。** 一个镜头可以关联故事段落、图片和实现说明。调整镜头位置、替换素材或成批修改内容时，可以沿用已有对象，查看改动历史，必要时撤销。[动态分镜与 H3 案例](examples/showcases/donut-hole-h3/README.md)用静帧展示 60 个镜头的组织方式，无需下载视频。

**留下批注，让协作接着进行。** 在具体对象或时间区间旁留下意见，其他人或 Agent 稍后读取、回复、标记处理。参与者各自记录已读，再按需查看待处理讨论。[晚开的花](examples/showcases/late-bloom-scroll/README.md)记录了四个 Agent 怎样通过批注核对画面接缝，共同完成一幅动态长卷。

这些内容可以按段落、页码、顺序或时间组织，再通过关联连接。使用现成工具时，可通过 MCP、命令行或 Python 操作；网页视图按需使用，支持中文和英文。[查看全部十二个案例](examples/showcases/README.md)。

## 为自己的任务添工具

例如，给角色和镜头建立关联后，可以开发一个“按人物汇总镜头”的小工具，直接查询已有项目。保存结果时，复用项目的读写、编号和改动记录。

Python 接口允许开发者和 Agent 使用现有内容结构，也可以增加自己的类型或数据表。需要专用界面时，可以编写视图插件；工具包可按需增减，底层读写也可直接嵌入自己的 Python 工程。

从[扩展指南](docs/build-with-layerweave/README.md)选择最小接入方式；[工具自有表的可运行示例](examples/tool_tables.py)展示如何让新工具沿用记录、历史与撤销。具体调用见[公共 API](src/layerweave/support/API.md)。

## Windows 快速开始

首发支持 Windows。代码要求 Python 3.11+、SQLite 3.35+；以下使用 Python 3.11。可以让 [uv](https://docs.astral.sh/uv/getting-started/installation/) 自动准备 Python 和环境，也可以使用已有 Python。使用网页不需要 Node。

### 用 uv 安装完整包

先取得本版本的 `layerweave-0.7.8-py3-none-any.whl`，放在选定的工作目录。安装 uv 后，在该目录的 PowerShell 中执行：

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe "./layerweave-0.7.8-py3-none-any.whl[mcp]"
```

缺少合适的 Python 时，uv 默认会自动下载。首次准备环境和依赖需要联网；无需激活虚拟环境，后续直接使用其中的解释器。[uv 的 Python 管理说明](https://docs.astral.sh/uv/concepts/python-versions/)

已有 Python、希望使用 pip 时，对应步骤是：

```powershell
python -X utf8 -m venv .venv
.venv/Scripts/python.exe -X utf8 -m pip install "./layerweave-0.7.8-py3-none-any.whl[mcp]"
```

`[mcp]` 安装 AI 接入需要的可选依赖；只用 Python/CLI 时可以去掉。安装不会自动装入官方视图插件。这里使用本地 wheel，不假定同名版本已经发布到 PyPI。

wheel 已构建好，安装 LayerWeave 本身不需要 setuptools；`[mcp]` 的依赖仍可能需要联网下载，wheel 不是完整离线环境。维护源码才需要可编辑安装；若卡在准备构建依赖，见[源码安装排查](docs/developer-conventions.md#可编辑安装与构建依赖)。

### 先试文章解析

取得同版本源码包中的 `examples/showcases`，或把案例 ZIP 解压到工作目录的 `examples` 中。最终应有 `examples/showcases/article-reading/project.json`。安装包与案例分开，先试文章解析即可；[十二个案例的目录与准备说明](examples/showcases/README.md)集中说明其他场景。

在刚才安装 wheel 的工作目录执行：

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.developer.database.cli examples/showcases/article-reading/reading.sqlite3
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply examples/showcases/article-reading/reading.sqlite3 --data-file examples/showcases/article-reading/project.json --new-project --result-file import-result.json
$caseImport = Get-Content -Raw -Encoding utf8 import-result.json | ConvertFrom-Json
if (-not $caseImport.ok) { throw '导入失败，请检查 import-result.json' }
$caseProjectId = $caseImport.data.project_id
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.query.project_overview examples/showcases/article-reading/reading.sqlite3 $caseProjectId
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.view.server examples/showcases/article-reading/reading.sqlite3 --project $caseProjectId
```

打开服务打印的本机地址，先读“正文”和“解读”，再从一个论点沿关联找到证据与配图。[文章解析说明](examples/showcases/article-reading/README.md)还提供五条局部阅读路线。数据库放在案例目录，让相对图片路径直接可用；项目编号来自导入结果，重复导入会创建新副本。

这个入门案例不需要 Key、FFmpeg、Node 或视图插件；查阅外部原文时才需联网。手书和 H3 提供无视频阅读版，使用静帧展示制作过程；完整音视频不随案例包分发。

### 创建自己的项目

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.developer.database.cli project.sqlite3
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli templates
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply project.sqlite3 --template subtitles --new-project
```

模板可选字幕、分镜或手书，结构可自由增减。随后把导入返回的项目编号传给视图或查询工具，完整参数按需查 help。

FFmpeg 是用户选装的外部程序，不随 wheel、`[mcp]` 或 uv 自动安装；普通数据管理与文字视图不需要它。服务端抽帧需要 FFmpeg，缩略图和波形也会使用它；缺少时部分浏览功能回退。安装后将其 bin 目录加入 PATH，或用 `FFMPEG` 指向 ffmpeg.exe 的完整路径，见[安装与功能影响](src/layerweave/tool/builtin/view/GUIDE.md#选装-ffmpeg)。AI 截图另外需要 Chrome、Edge 或 Chromium。媒体输出目录由 AI 或使用者选择。

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
uvx --python 3.11 --from "./layerweave-0.7.8-py3-none-any.whl[mcp]" layerweave-mcp --config ./mcp.json
```

这条命令会持续运行 stdio 服务，通常由 MCP 客户端托管；它不是启动网页的命令。客户端中的 uvx 配置使用绝对路径，完整例子见 MCP 说明。安装包放到正式下载地址后，也可通过 URL 指定来源，无需另写一套业务接口。

## 查找工具与文档

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

- [使用入口](src/layerweave/tool/builtin/usage/README.md)：从任务选择工具，读取输入、输出和示例。
- [JSON 交换与模板](src/layerweave/tool/builtin/usage/exchange/README.md)：批量操作与场景起点。
- [视图与插件](src/layerweave/tool/builtin/view/README.md)：界面操作；[官方插件仓库](https://gitee.com/emotion1354414/layerweave-plugins)独立选装，零插件可用。
- [源码开发](docs/developer-conventions.md)、[完整示例](docs/examples.md)、[文档目录](docs/README.md)。

`visualization` 是完整版本；`main` 是无视图开发源码，保留直接 Python/CLI 入口，共用核心、支撑和非视图工具。视图、MCP 服务及发行封装在完整分支维护。命令中的 `-X utf8` 用于中文 Windows 的管道输出，详见[编码说明](src/layerweave/tool/builtin/usage/README.md#命令行编码)。

## 许可证

LayerWeave 自身采用 [MIT](LICENSE)。网页中的第三方组件保留各自许可，见[第三方声明](THIRD_PARTY_NOTICES.md)。独立插件、技能和外部服务遵循其自身说明。

# LayerWeave

**简体中文** | [English](README.en.md)

[GitHub](https://github.com/aceddad/LayerWeave/tree/visualization) · [Gitee](https://gitee.com/emotion1354414/layer-weave/tree/visualization) · [快速开始](#快速开始) · [接入 AI](#接入-ai) · [开发与扩展](#按需组合开发自己的工具)

**少分心：只看相关的那一段，只做眼前的那一件事。**

LayerWeave 把正文、素材引用、证据和批注放在同一份项目里，按时间、段落或阅读顺序排列，再用层级和关联连接起来。人可以在画布上查看、定位和留言，AI 可以查询同一段内容、截图核对，并沿关联追溯依据。

![真实手书项目的完整工作视图：左侧层级目录，中间音频、分轨、故事、分镜与原画的时间轴，右侧查看此刻的内容和关联](docs/images/handdraw-workspace.png)

*真实手书制作项目：音频、分轨、故事、分镜与原画按时间组织，右侧“此刻”查看选中对象及当前位置的内容和关联。完整制作素材不随安装包提供。[查看原图](docs/images/handdraw-workspace.png)。*

## 快速开始

当前为 **0.7.9b1 Windows 预览版**。在自己的工作目录打开 PowerShell，任选一种入口：

已有 [uv](https://docs.astral.sh/uv/getting-started/installation/)：

```powershell
uvx layerweave@0.7.9b1 demo
```

已有 Node.js 20+ / npm（Windows x64）：

```powershell
npx --yes layerweave@0.7.9-beta.1 demo
```

命令会准备环境并在浏览器中打开文章解析案例。uv 管理 Python；npm 入口会在需要时自动准备 uv 和独立 Python 3.11。首次运行需要联网。

项目保存在 `./layerweave-demo/article-reading`。**再次运行同一条命令会保留修改**，包括对象、批注、布局和素材。使用时保持终端运行，按 Ctrl+C 停止服务；加 `--no-browser` 可只打印访问地址。

将命令末尾的 `demo` 换成以下参数，还可以：

| 参数 | 用途 |
|---|---|
| `demo --list` | 查看十二个案例 |
| `demo comic-creation --dir ./my-comic` | 下载漫画案例到指定目录并打开 |
| `view ./project.sqlite3` | 打开已有数据库 |
| `new ./my-project --template subtitles` | 从字幕模板创建自己的项目 |
| `help project_overview` | 查看项目概览工具的帮助 |

文章解析随包提供，其他案例按需下载。项目数据与下载缓存分开保存。更多参数见[统一入口说明](src/layerweave/tool/builtin/shared/launcher/README.md)；离线安装文件在 [GitHub Releases](https://github.com/aceddad/LayerWeave/releases/tag/v0.7.9b1)。

## 接入 AI

LayerWeave 提供 stdio MCP 服务，可由支持 MCP 的客户端自动启动。**视图与 MCP 可以分别使用，也可以同时访问同一个项目。**

以下以 `D:/my-layerweave` 为工作目录，请换成你运行案例时的实际目录。在其中保存 `mcp.json`：

```json
{"workspace": "D:/my-layerweave"}
```

已有 uv 时，在客户端的 MCP 配置中加入：

```json
{
  "mcpServers": {
    "layerweave": {
      "command": "uvx",
      "args": ["--python", "3.11", "--from", "layerweave[mcp]==0.7.9b1", "layerweave", "mcp", "--config", "D:/my-layerweave/mcp.json"]
    }
  }
}
```

<details>
<summary>使用 npm 接入（Windows）</summary>

用下面的服务项替换上面的 `layerweave` 服务项；npm 会自动准备 Python 和 MCP 依赖：

```json
{
  "command": "cmd",
  "args": ["/c", "npx", "--yes", "layerweave@0.7.9-beta.1", "mcp", "--config", "D:/my-layerweave/mcp.json"]
}
```

</details>

配置文件的位置取决于客户端，示例中的路径需要替换；若客户端找不到 uvx，可用 `(Get-Command uvx).Source` 查到完整路径。接入后，可以让 AI：

> 先用 layerweave_help 查看可用工具，再查看 layerweave-demo/article-reading/project.sqlite3 的结构，找出第一段正文对应的解读和证据。

客户端会管理服务进程；MCP 启动本身不打开画布。默认数据库、项目、工具暴露和自管 Python 环境的接法见 [MCP 说明](src/layerweave/tool/builtin/shared/mcp/README.md)。

## 把注意力留给当前这一段

你说“30–35 秒这里不太连贯”时，可以把批注挂在那一段，或把视图链接交给 AI。AI 读取该范围各层的内容，按同一范围截图，沿关联查故事、素材和已有讨论，再定向修改并复查。暂时没处理完的意见留在原处，之后接着做。

| 想做的事 | LayerWeave 提供的能力 |
|---|---|
| 找到“这里”相关的信息 | 按时刻、区间、层或子树读取内容，沿关联追溯依据 |
| 让 AI 对照画面与数据 | 查询对象身份、正文和关联，同时截取对应视图或范围 |
| 留意见，又不打断当前工作 | 批注、回复、待处理状态；人和 AI 都能沿讨论追查 |
| 看 AI 改到哪里了 | 画布每两秒同步项目变化，按位置查看新增或修改的内容 |
| 改错后找回内容 | 改动记录、历史与撤销；覆盖冲突会明确报告 |

视频和歌曲可以按秒，文章按段落，漫画按页和格。轴的单位由项目解释，段落、页码与秒不会自动换算。图片和音视频通过路径或链接引用；生成、处理媒体由技能或外部工具完成。

截图理解需要有视觉能力的 AI；何时读取批注、由哪个 AI 处理，由调用方安排。具体工具与调用方式可以从 help 按需查询，或阅读[视图使用说明](src/layerweave/tool/builtin/view/GUIDE.md#给-ai-用)。

## 换一个场景试试

| 案例 | 可以怎样用 |
|---|---|
| [文章解析](examples/showcases/article-reading/README.md) · 推荐入门 · [截图](docs/images/article-reading.png) | 将正文与逐段解读对照，从论点追溯证据、配图和讨论 |
| [动态分镜与 H3](examples/showcases/donut-hole-h3/README.md) | 对照镜头、故事段落与实现方式，追溯共用的素材 |
| [手书制作](examples/showcases/donut-hole-tegaki/README.md) | 将听感、故事、画面设计、角色设定与实现记录放在一起 |
| [晚开的花](examples/showcases/late-bloom-scroll/README.md) | 四个 AI 通过批注核对接缝和配色，共同完成一幅动态 SVG 长卷 |

十二个案例还覆盖小说、漫画、课程、调查、互动故事、需求设计、翻译审校和代码梳理，见[完整案例目录](examples/showcases/README.md)。文章解析使用原创短论；手书与 H3 为不附歌曲和视频的静帧阅读版，完整影片需要另备素材。

## 按需组合，开发自己的工具

LayerWeave 的核心理念是**降低注意力的分散**。找东西、对位置、记改动这些事交给工具；开发一个新功能时，也应能专注它自身的逻辑。

做法是**按需组合**：对象放进层，层组成树，通过 `bind` 关联彼此；内核提供基本结构，基础支撑负责保存、编号、事务和改动记录，工具、技能与插件按用途接入。核心和基础支撑只依赖 Python 标准库。

比如，要汇总“每个角色出现在哪些镜头”，可以写一个工具查询现有关系；保存结果时复用已有的读写和记录能力，配合撤销工具恢复改动。工具也可以声明自己的表，不必把所有数据都塞进层和对象。

**欢迎你和 AI 基于这个内核开发自己的应用。** 本分支是一个可直接使用的上层应用示例，视图本身也是工具包。内置工具展示如何复用内核，独立视图插件进一步展示如何扩展应用。批注就是其中一个例子：`Note` 继承文字对象，回复通过关联表达，已读状态与布局保存在视图自己的表里。

- [main 开发分支](https://github.com/aceddad/LayerWeave/tree/main)：无视图的内核、基础支撑与非视图工具，带最小 Python 示例。
- [扩展指南](docs/build-with-layerweave/README.md)：新增类型、自己的表、组合工具或接入增量变化。
- [公共 API](src/layerweave/support/API.md)与[工具表例子](examples/tool_tables.py)：复用已有能力开发功能。
- [官方视图插件](https://github.com/aceddad/layerweave-plugins)：一览、接缝、预览和网页插件独立选装。

## 文档与可选组件

[使用工具](src/layerweave/tool/builtin/usage/README.md) · [JSON 交换与模板](src/layerweave/tool/builtin/usage/exchange/README.md) · [视图与插件](src/layerweave/tool/builtin/view/README.md) · [维护源码](docs/developer-conventions.md) · [文档目录](docs/README.md)

普通数据管理和文章案例不需要 API KEY、FFmpeg 或官方视图插件。服务端抽帧、视频缩略图和波形需要[选装 FFmpeg](src/layerweave/tool/builtin/view/GUIDE.md#选装-ffmpeg)；AI 截图需要 Chrome、Edge 或 Chromium。网页支持中英文，当前发行包的视图组件为 0.31.1。

## AI 协作开发

项目由维护者主导设计与维护，Astra（Codex）与 Claude 协助本分支的开发、测试和文档整理。

## 许可证

LayerWeave 自身采用 [MIT](LICENSE)。随包网页组件保留各自许可，见[第三方声明](THIRD_PARTY_NOTICES.md)；独立插件、技能和外部服务遵循各自的说明。

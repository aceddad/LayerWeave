# LayerWeave

**简体中文** | [English](README.en.md)

**0.7.8 公开预览版 · Windows**

**少分心：只看相关的那一段，只做眼前的那一件事。**

LayerWeave 是一个面向人和 AI 的信息管理工具。它把文字、素材引用和批注放在按时间或顺序排列的轴上，用层级和关联组织起来，让参与者随时能找到"此刻、这里"相关的全部内容。

本分支展示基于 LayerWeave 内核开发的上层应用，视图本身也是一个内置工具包。内置工具展示如何复用内核，独立视图插件展示如何在应用之上继续扩展；这些实现均可直接使用，也欢迎作为你和 AI 开发新工具、新应用的参考。

它的设计理念只有一条：**降低注意力的分散。** 一个任务里，真正需要思考的往往只是其中一小块，而大量注意力被花在找东西、对位置、记改动、解释"我说的是哪里"上。LayerWeave 把这些事交给工具：

- AI 只读取这一段时间里的相关内容，不必每次读完整个项目；
- 人在画面上指一下，不必反复描述是哪一段、哪个镜头；
- 修改意见留在具体内容旁边，等对方有空再处理，不打断正在做的事；
- 开发新功能时，可以复用存储、编号、改动记录和撤销，把精力放在这个功能本身。

做法是**组合**与**信息管理**。组合让每一部分都小而单一：对象放进层，层组成树，彼此用关联连接；核心只管最基本的结构，查询、编辑、视图、技能、插件都是可以加上、拿掉或替换的部件。拆得越细，信息也越分散，信息管理就把这些零散的块按时间、顺序和关联重新串起来，需要哪一块都能直接找到。于是不论处理信息还是开发功能，每次都可以优先处理当前这一小块。

下面分四部分说明它怎样做到这些。

## 一、信息管理：把同一时刻的事放在一起看

内容放在一条条轴上：视频和歌曲按秒，文章按段落，漫画按页和格，课程按学习步骤。轴上的每一项都是一个有身份的对象；对象分属不同的层，层又组成树，共用同一时间尺度的"镜头说明""素材""台词"可以在同一时刻对照。段落、页码与秒不会自动换算；批注自身按条目顺序保存，通过关联和区间指向被评论的内容。对象之间用关联连接：这一镜依据哪段故事，这句结论引用了哪条证据，这条意见针对的是哪一秒。

这样一来，检查某一刻就不必到处翻找。问一句"30–35 秒这里有什么"，就能一次拿到这段时间里每一层的内容、它们之间的关联、已有的批注，以及哪些轨道在这里是空着的。要追问原因，就沿关联往下查；要改，就按对象身份定向修改，而不是整段重写。改动都有记录，可以查历史，也可以撤销。

时间不是唯一的排法。按段落、页码或阅读顺序排列时，同样可以选中一段，沿关联找到对应的证据、配图和讨论。[十二个案例](examples/showcases/README.md)用这套结构分别处理了分镜、手书、文章精读、小说、漫画、课程、调查、互动故事、需求、翻译审校和代码梳理。

## 二、AI 友好：查得到、看得见、听得懂反馈

LayerWeave 从一开始就是为 AI 使用而设计的。所有能力都可以通过 Python、CLI 或 MCP 调用；AI 先用 `layerweave_help` 查有哪些工具、参数怎么填，再针对具体目标操作，不必一次读完整个项目。每次操作都会返回结构化的结果：写入了什么、有没有问题、编号是多少。

一次实际的工作大概是这样的。你说："30–35 秒这里不太连贯，看一下。"

1. 你在画布上圈出 30–35 秒，或者把当前视图的链接发给 AI。
2. AI 读取这段时间里各层的内容、关联和批注。
3. AI 按同一范围截一张图，对照画面和数据，判断问题出在哪个对象。
4. AI 沿关联往回查：这一镜依据哪段故事，用了哪个素材，之前有没有人讨论过。
5. 找到要改的对象后定向修改，再读取或截图复查。
6. 没处理完的地方写成批注留下，下次接着做。

支撑这些步骤的工具：

| 工具 | 做什么 |
|---|---|
| `view_state` | 读取视图当前的状态：在看哪个项目和画板、选中了什么、播放头在哪 |
| `view_at` | 读取某一刻或某一段里各层的内容、关联和批注；不指定范围时，读用户正在看的位置 |
| `view_screenshot` | 截取画布、指定范围、某条批注指向的位置，或已安装插件的页面；可以直接按视图链接定位 |
| `view_walk` | 从一个对象、层或批注出发，沿关联逐步展开，可限制方向、深度和数量 |
| `view_note` | 留言、回复、改指向，标记已读和已处理；查询还有哪些在等自己处理 |
| `view_layout` | 查询和调整画板的位置、尺寸和拼接 |

截图给的是画面，查询给的是对象身份、正文和关联；两者通过同一个项目、同一组选中对象和同一段范围对应起来。

人给 AI 的反馈也因此更准确。与其在对话里描述"大概在中间偏后、那个转场的地方"，不如直接把批注挂在那个对象或那几秒上；AI 读到批注时就知道它指的是什么，还能顺着之前的批注和回复，追溯这个问题的来龙去脉。

几点说明：看懂画面靠的是有视觉能力的 AI，LayerWeave 本身不做以图搜图或图像识别；截图工具会另开一个只读页面来拍，不会改动你正在看的视图，拍的也只是 LayerWeave 自己的页面；什么时候去读批注、由哪个 AI 处理，由调用方决定，LayerWeave 不自带多 Agent 调度或定时唤醒。详见[给 AI 用的视图工具](src/layerweave/tool/builtin/view/GUIDE.md#给-ai-用)。

## 三、开发友好：让 AI 专心做一件事

方便开发是 LayerWeave 最初的设计目的之一。需要一个新功能时，AI 或开发者可以把精力放在功能本身，直接复用保存、编号、事务、改动记录、历史和撤销等通用能力。

比如你已经给角色和镜头建了关联，想要一份"每个角色出现在哪些镜头"的汇总。写一个小工具直接查询现有项目就行；保存结果时，它沿用项目已有的读写和改动记录，写错了也能撤销。

常见的扩展方式：

- **用现有结构：** 通过 Python 接口读写层、对象和关联，按位置、区间或子树查询。
- **加自己的类型：** 新增层或对象类型，同时提供 Python 类和 TOML 声明。
- **加自己的数据表：** 工具自己的表不必套用层和对象的结构，声明之后同样进入改动记录，可以查历史、可以撤销。
- **组合已有工具：** 在同一个事务里调用多个工具，任何一步失败都整体回滚。
- **做专用界面：** 编写视图插件，在画布之外提供自己的页面。

批注就是这样做出来的：`Note` 继承了普通的文字对象，回复用关联表达，已读状态和共享排版放在视图工具自己的表里。不用改动原有结构，就长出了一套协作功能。

这就是组合的好处：新功能可以复用已有的部件，把精力放在相关接口和自身逻辑上。

整体很轻。核心和基础支撑仅依赖 Python 标准库，约三千行 Python；MCP 和部分技能另有可选依赖。具体操作都放在可以替换的工具包里，不需要的可以不装，底层读写也可以直接嵌进你自己的 Python 工程。

从[扩展指南](docs/build-with-layerweave/README.md)选一种最小接入方式开始；[工具自有表的可运行示例](examples/tool_tables.py)演示了新工具怎样共用记录、历史与撤销；逐个接口见[公共 API](src/layerweave/support/API.md)，整体设计见[架构说明](docs/architecture.md)。

## 四、视觉层：人和 AI 共用的窗口

前三部分不必打开画布也能用。视觉层是在同一份数据上加的一扇窗：人在这里看、指、留言，AI 在这里截图、读取人正在看的位置。

- **随时看 AI 干到哪了。** 画布每两秒同步一次项目的变化，AI 写入的内容很快就会出现在对应的时间位置上，可以边看边指出问题。
- **异步留言，不打断 AI。** 看到问题就把批注挂在那里，AI 手上的工作可以先做完，之后再按批注逐条处理、回复、标记完成。
- **顺着线索追查。** 从一个对象出发，沿关系线看到它的依据、素材和讨论；也可以找对象、看改动、一览全部素材。
- **检查结果。** AI 做完后，在画布上对照时间轴看整体效果，和 AI 看到的是同一份内容。

[晚开的花](examples/showcases/late-bloom-scroll/README.md)展示了这种协作：四个 AI 各画一幕动态 SVG，通过 32 条批注互相核对接缝、配色和改动，最后拼成一幅 9600×1400 的长卷。

网页支持中文和英文。官方插件（一览、接缝、预览、网页）独立选装，不装插件也能用。

## 从案例开始看

| 案例 | 规模 | 可以看到什么 |
|---|---|---|
| [文章解析](examples/showcases/article-reading/README.md) · **推荐入门** | 8 个根层、32 个对象、68 条关联 | 一篇约 1,350 字的原创中文短论与逐段解读并排；从一个论点出发，沿关联找到证据、配图和讨论；附五条可直接运行的阅读路线 |
| [动态分镜与 H3](examples/showcases/donut-hole-h3/README.md) | 30 层、228 个对象、210 条关联 | 一首歌的 60 个镜头，连到段落和实现方式；使用生成素材的镜头还可追溯片段静帧与所用模型，也能看到多个镜头怎样共用同一段素材 |
| [手书制作](examples/showcases/donut-hole-tegaki/README.md) | 29 层、101 个对象、43 条关联 | 同一首歌的另一种做法：听感与故事、14 段画面设计、对应的实现方式和角色设定，附 32 个时刻的总览图 |
| [晚开的花](examples/showcases/late-bloom-scroll/README.md) | 4 层、37 个对象，其中 32 条批注 | 四个 AI 通过批注协作完成长卷；附可直接用浏览器打开的动态预览 |

文章解析的正文是案例作者原创的中文短论，不是外部文章的全文或译文；查看引用的外部原文时需要联网。手书和 H3 是"无视频阅读版"：公开包用静帧展示结构和画面，不附歌曲和视频，所以不能下载后直接重新生成整部影片。

另外八个案例覆盖小说创作、漫画创作、课程学习、信息调查、互动故事、需求设计、翻译审校和代码梳理。十二个案例合计 125 层、691 个对象、927 条关联，完整清单和准备方法见[案例目录](examples/showcases/README.md)。

## 现在有什么

| 部分 | 0.7.8 的内容 |
|---|---|
| 内部命令 | 46 个，分布在 15 个工具包：查询、按区间编辑、复制与迁移、JSON 交换、复查、历史与撤销、视图等 |
| 技能材料 | 12 份，供 AI 按需阅读（分轨卡点、出图、网点、视频生成与核验、动作参考、字形变形等）；它们是说明和脚本，不会自动执行 |
| 视图 | 0.31.0，网页支持中文和英文；四个官方插件独立选装 |
| 接入方式 | Python、CLI 和可选的 MCP；MCP 默认提供 4 个通用入口，另加 inbox、reply、screenshot 三个快捷入口 |
| 起始模板 | 字幕、分镜、手书三种，结构可以自由增减 |

图片、音频和视频通过文件路径或链接引用，不会搬进项目数据库；生成和处理这些媒体，由调用方、技能或外部工具完成。

## Windows 快速开始

首发支持 Windows。代码要求 Python 3.11+ 和 SQLite 3.35+，下面的例子使用 Python 3.11。可以让 [uv](https://docs.astral.sh/uv/getting-started/installation/) 自动准备 Python 和环境，也可以用已有的 Python。使用网页不需要 Node。

### 用 uv 安装完整包

先取得本版本的 `layerweave-0.7.8-py3-none-any.whl`，放进你选定的工作目录。装好 uv 后，在这个目录的 PowerShell 中执行：

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe "./layerweave-0.7.8-py3-none-any.whl[mcp]"
```

如果没有合适的 Python，uv 默认会自动下载。第一次准备环境和依赖需要联网。不需要激活虚拟环境，后面直接用其中的解释器即可。[uv 的 Python 管理说明](https://docs.astral.sh/uv/concepts/python-versions/)

已经有 Python、想用 pip 的话：

```powershell
python -X utf8 -m venv .venv
.venv/Scripts/python.exe -X utf8 -m pip install "./layerweave-0.7.8-py3-none-any.whl[mcp]"
```

`[mcp]` 会装上接入 AI 所需的可选依赖；只用 Python 或 CLI 时可以去掉。安装不会自动装官方视图插件。这里用的是本地 wheel，不假定 PyPI 上已经有同名版本。

wheel 已经构建好，安装 LayerWeave 本身不需要 setuptools；但 `[mcp]` 的依赖仍可能要联网下载，所以 wheel 不等于完整的离线环境。只有维护源码才需要可编辑安装；如果卡在准备构建依赖，见[源码安装排查](docs/developer-conventions.md#可编辑安装与构建依赖)。

### 先试文章解析

从同版本的源码包取得 `examples/showcases`，或者把案例 ZIP 解压到工作目录的 `examples` 里，确认有 `examples/showcases/article-reading/project.json`。软件和案例是分开发放的，先试这一个就够了；其他场景见[十二个案例的目录与准备说明](examples/showcases/README.md)。

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

打开服务打印出的本机地址，先读"正文"和"解读"两层，再挑一个论点，沿关联找到它的证据和配图。[文章解析说明](examples/showcases/article-reading/README.md)里还有五条局部阅读路线。数据库要放在案例目录里，图片的相对路径才能直接找到；项目编号以导入结果为准，再导入一次会多出一份副本。

这个入门案例不需要 Key、FFmpeg、Node 或视图插件，只有查看外部原文时才要联网。

### 创建自己的项目

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.developer.database.cli project.sqlite3
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli templates
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply project.sqlite3 --template subtitles --new-project
```

模板有字幕、分镜和手书三种，导入后结构可以随意增减。把导入返回的项目编号传给视图或查询工具即可，完整参数按需查 help。

FFmpeg 是可选的外部程序，wheel、`[mcp]` 和 uv 都不会自动安装它；普通的数据管理和文字视图用不到。服务端抽帧需要 FFmpeg，缩略图和波形也会用到，缺少时这些浏览功能会改用替代方式或不显示。安装后把它的 bin 目录加入 PATH，或用 `FFMPEG` 环境变量指向 ffmpeg.exe 的完整路径，见[安装与功能影响](src/layerweave/tool/builtin/view/GUIDE.md#选装-ffmpeg)。AI 截图另外需要 Chrome、Edge 或 Chromium。媒体的输出目录由 AI 或使用者自己选择。

## 连接 AI / MCP

在项目工作目录保存一份 `mcp.json`，workspace 写实际的绝对路径：

```json
{"workspace": "D:/my-project"}
```

在支持 stdio MCP 的客户端里这样配置：

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

把解释器和配置文件的路径换成实际位置；配置写在哪里由各客户端决定。AI 可以先调用 `layerweave_help` 查有哪些能力，再针对具体目标操作，不必每次读完整个项目。数据库和项目编号可以每次调用时传入，也可以设默认值，见[MCP 说明](src/layerweave/tool/builtin/shared/mcp/README.md)。

只需要 MCP 的话，也可以让 uvx 一条命令准备好环境并启动服务：

```powershell
uvx --python 3.11 --from "./layerweave-0.7.8-py3-none-any.whl[mcp]" layerweave-mcp --config ./mcp.json
```

这条命令会持续运行一个 stdio 服务，通常交给 MCP 客户端托管；它不会打开网页。客户端里的 uvx 配置请用绝对路径，完整例子见 MCP 说明。安装包放到正式下载地址后，也可以直接用 URL 指定来源。

## 查找工具与文档

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

`command_help` 列出当前安装的命令和调用示例，`config_help` 说明各种层和对象的用途、字段与封装关系。

- [使用入口](src/layerweave/tool/builtin/usage/README.md)：从任务出发选工具，查看输入、输出和示例。
- [JSON 交换与模板](src/layerweave/tool/builtin/usage/exchange/README.md)：批量操作和场景起点。
- [视图与插件](src/layerweave/tool/builtin/view/README.md)：界面操作；[官方插件仓库](https://gitee.com/emotion1354414/layerweave-plugins)独立选装，不装插件也能用。
- [源码开发](docs/developer-conventions.md)、[完整示例](docs/examples.md)、[文档目录](docs/README.md)。

`visualization` 是完整版本；`main` 是不含视图的开发源码，保留直接的 Python/CLI 入口，与完整版共用核心、支撑和非视图工具。视图、MCP 服务和发行封装在完整分支维护。命令里的 `-X utf8` 是为了让中文 Windows 的管道输出不乱码，详见[编码说明](src/layerweave/tool/builtin/usage/README.md#命令行编码)。

## 许可证

LayerWeave 本身采用 [MIT](LICENSE)。网页里的第三方组件保留各自的许可，见[第三方声明](THIRD_PARTY_NOTICES.md)。独立插件、技能和外部服务遵循各自的说明。

# LayerWeave 开发源码

**简体中文** | [English](README.en.md)

**少分心：只看相关的那一段，只做眼前的那一件事。**

LayerWeave 是一个面向人和 AI 的信息管理工具。它把文字、素材引用和批注放在按时间或顺序排列的轴上，用层级和关联组织起来，让参与者随时能找到"此刻、这里"相关的全部内容。图片和音视频通过文件路径或链接引用。

它的设计理念是**降低注意力的分散**：找东西、对位置、记改动、解释"我说的是哪里"这些事交给工具，人和 AI 把注意力留给真正需要思考的那一小块。

做法是**组合**与**信息管理**。组合让每一部分都小而单一：对象放进层，层组成树，彼此用关联连接；核心只管最基本的结构，查询、编辑、视图、技能、插件都是可以加上、拿掉或替换的部件。拆得越细，信息也越分散，信息管理就把这些零散的块按时间、顺序和关联重新串起来，需要哪一块都能直接找到。于是不论处理信息还是开发功能，每次都可以优先处理当前这一小块。

这里是 **main 开发分支**：不含网页视图，直接用 Python 和 CLI 读写、查询和编辑项目，也是开发新工具的起点。画布、批注、AI 截图、MCP 服务和发行封装在 **visualization 完整分支**，两边共用同一套核心、基础支撑和非视图工具。

**欢迎基于 LayerWeave 内核开发和扩展。** 你和 AI 可以复用这里的基础能力，增加或替换工具，构建自己的应用。内置工具既提供现成的功能，也展示怎样使用内核；视图是其中一个上层应用示例，独立视图插件则进一步展示如何扩展这个应用。

## 一、信息管理：把同一时刻的事放在一起看

内容放在一条条轴上：视频和歌曲按秒，文章按段落，漫画按页和格，课程按学习步骤。每一项都是有身份的对象；对象分属不同的层，层组成树，共用同一时间尺度的轨道可以在同一时刻对照，对象之间再用关联连起来。段落、页码与秒不会自动换算；完整版本的批注按条目保存，通过关联和区间指向内容。

查询 30–35 秒这一段，就能一次拿到各层的镜头、素材引用、关联，以及哪些轨道在这里是空着的；沿关联查到这一镜依据的故事和素材，再按对象身份定向修改，改完可以查历史、可以撤销。按段落或阅读顺序排列的内容也一样，选中一段，就能沿关联找到证据、配图和讨论。

## 二、AI 友好：查得到、看得见、听得懂反馈

所有能力都可以从 Python 和 CLI 调用，每次操作返回结构化的结果：写入了什么、有没有问题、编号是多少。AI 先用 `command_help` 查有哪些工具、参数怎么填，再针对具体目标操作，不必一次读完整个项目。

完整版本在此之上提供 MCP 服务，以及读取当前视图、按时刻读取、沿关联展开、批注和截图的工具：人把视图链接或一条挂在具体内容上的批注交给 AI，AI 就知道"这里"指的是什么，还能顺着之前的批注追溯来龙去脉。

## 三、开发友好：让 AI 专心做一件事

方便开发是 LayerWeave 最初的设计目的之一，也是这个分支的主要用途。需要一个新功能时，可以把精力放在功能本身，直接复用保存、编号、事务、改动记录、历史和撤销等通用能力。

比如你已经给角色和镜头建了关联，想要一份"每个角色出现在哪些镜头"的汇总：写一个小工具直接查询现有项目，保存结果时沿用项目已有的读写和改动记录，写错了也能撤销。

常见的扩展方式：

- **用现有结构：** 通过 Python 接口读写层、对象和关联，按位置、区间或子树查询。
- **加自己的类型：** 新增层或对象类型，同时提供 Python 类和 TOML 声明。
- **加自己的数据表：** 工具自己的表不必套用层和对象的结构，声明之后同样进入改动记录，可以查历史、可以撤销。
- **组合已有工具：** 在同一个事务里调用多个工具，任何一步失败都整体回滚。
- **需要专用界面时：** 接入完整版本的视图插件。

完整版本的批注就是这样做出来的：`Note` 继承了普通的文字对象，回复用关联表达，已读状态和共享排版放在视图工具自己的表里，不用改动原有结构。

这就是组合的好处：新功能可以复用已有的部件，把精力放在相关接口和自身逻辑上。

整体很轻。核心和基础支撑仅依赖 Python 标准库，约三千行 Python；完整版本的 MCP 和部分技能另有可选依赖。具体操作放在可以替换的工具包里，不需要的可以移除，底层读写也可以直接嵌进你自己的 Python 工程。本分支现有 33 个内部命令，分布在 13 个工具包；另有 12 份技能材料供 AI 按需阅读，它们不会自动执行。

从[扩展指南](docs/build-with-layerweave/README.md)选一种最小接入方式开始；[工具自有表的可运行示例](examples/tool_tables.py)演示了新工具怎样共用记录、历史与撤销；逐个接口见[公共 API](src/layerweave/support/API.md)，整体设计见[架构说明](docs/architecture.md)。

## 四、视觉层：在完整版本里

画布是人和 AI 共用的一扇窗：人在上面看、指、留言，AI 在上面截图、读取人正在看的位置。画布每两秒同步一次项目的变化，可以随时看 AI 改到了哪里；看到问题就把批注挂在那里，AI 先做完手上的事，再按批注逐条处理。这部分在 visualization 分支维护，与本分支共用同一套数据格式和非视图工具。

## 案例

| 案例 | 规模 | 可以看到什么 |
|---|---|---|
| [文章解析](examples/showcases/article-reading/README.md) · **推荐入门** | 8 个根层、32 个对象、68 条关联 | 原创中文短论与逐段解读并排，从论点追溯证据、配图和讨论；五条阅读路线只用基础的 Python/CLI 就能完成 |
| [动态分镜与 H3](examples/showcases/donut-hole-h3/README.md) | 30 层、228 个对象、210 条关联 | 一首歌的 60 个镜头，连到段落和实现方式；使用生成素材的镜头还可追溯片段静帧与模型；用静帧阅读，不需要下载视频 |
| [手书制作](examples/showcases/donut-hole-tegaki/README.md) | 29 层、101 个对象、43 条关联 | 同一首歌的另一种做法：故事、14 段画面设计、实现方式和角色设定 |
| [晚开的花](examples/showcases/late-bloom-scroll/README.md) | 4 层、37 个对象，其中 32 条批注 | 四个 AI 用批注核对画面接缝、拼成一幅长卷；使用完整版本的批注类型 |

十二个案例合计 125 层、691 个对象、927 条关联，另外八个覆盖小说、漫画、课程、调查、互动故事、需求、翻译审校和代码梳理，见[案例目录](examples/showcases/README.md)。

## 开始开发

首发以 Windows 为支持平台；代码要求 Python 3.11+ 和 SQLite 3.35+。取得本分支源码后，可以让 [uv](https://docs.astral.sh/uv/getting-started/installation/) 自动准备 Python。在源码根目录的 PowerShell 中运行：

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
.venv/Scripts/python.exe -X utf8 -B examples/read_write.py
```

uv 默认会下载缺少的 Python；第一次准备环境和依赖需要联网。不需要激活环境，直接用其中的解释器即可。已经有 Python、想用 pip 的话：

```powershell
python -X utf8 -m venv .venv
.venv/Scripts/python.exe -X utf8 -m pip install -e ".[dev]"
.venv/Scripts/python.exe -X utf8 -B examples/read_write.py
```

可编辑安装让其他工作目录也能导入 layerweave，修改源码立即生效。pyproject.toml 提供本地开发入口；本分支不单独制作面向使用者的发行包。核心和普通工具运行时只需要标准库，dev 依赖用于开发验证。示例使用临时数据，不会改动实际项目。

源码安装还需要 setuptools>=77.0.3 和 wheel。pip 默认在临时构建环境里准备它们，所以即使当前环境已有 setuptools，也可能联网下载。如果卡在 Installing build dependencies，先看[源码安装排查](docs/developer-conventions.md#可编辑安装与构建依赖)；只有提前装好构建依赖，才适合关闭构建隔离。

想体验案例时，在同一个 PowerShell 中设置 `$casePython = (Resolve-Path .venv/Scripts/python.exe).Path`，再按所选案例的说明导入和查询。

## 按需查看接口

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

`command_help` 列出当前安装的工具和调用示例，`config_help` 说明各种层和对象的用途、字段与封装关系。命令里的 mcp 元信息供外部适配器读取，不会自行启动服务。

- [使用现成工具](src/layerweave/tool/builtin/usage/README.md)：读写项目、查询、按时序编辑、历史与撤销、JSON 交换和场景模板。
- [维护源码](docs/developer-conventions.md)、[完整示例](docs/examples.md)、[文档目录](docs/README.md)。

业务记录的写入统一走同一个入口；新增封装时同时提供 Python 类和 TOML。完整的工具包可以替换或移除。技能是供 AI 按需阅读的材料，使用前请确认它的依赖、KEY 和输出目录。

## 验证改动

```powershell
.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s tests -t . -v
```

测试按 architecture、foundation、tools 分类，使用临时数据，详见[测试导引](tests/README.md)。Windows 下的管道命令显式使用 -X utf8；也可以设置 PYTHONUTF8=1，见[编码说明](src/layerweave/tool/builtin/usage/README.md#命令行编码)。

## AI 协作开发

项目由维护者主导设计与维护，Astra（Codex）协助本分支的开发、测试与文档整理。

## 许可证

LayerWeave 源码采用 [MIT](LICENSE)。独立技能、外部库和服务遵循各自的说明。视图构建与第三方网页组件的分发说明见 visualization 分支。

# LayerWeave 内核与开发源码

**简体中文** | [English](README.en.md)

[GitHub](https://github.com/aceddad/LayerWeave/tree/main) · [Gitee](https://gitee.com/emotion1354414/layer-weave/tree/main) · [完整应用与 MCP](https://github.com/aceddad/LayerWeave/tree/visualization)

**少分心：复用已有能力，专注你要开发的那一件事。**

LayerWeave 用层、对象和关联组织按时间或顺序排列的信息，为工具提供统一的存储、编号、事务和改动记录。你和 AI 可以在这个基础上开发查询、编辑、协作或专用界面，按需组合已有部件。

这里是 **main 开发分支**，包含内核、基础支撑和非视图工具。可直接使用的画布应用、MCP 服务与发行包在 [visualization](https://github.com/aceddad/LayerWeave/tree/visualization)，也是基于内核开发的上层应用示例。

## 跑通第一个例子

当前以 Windows 为支持平台，需要 Python 3.11+ 和 SQLite 3.35+。已有 [uv](https://docs.astral.sh/uv/getting-started/installation/) 时，在 PowerShell 中取得本分支源码并准备环境：

```powershell
git clone --branch main https://github.com/aceddad/LayerWeave.git layerweave-core
cd layerweave-core
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -e .
```

已有源码时从 `uv venv` 开始。uv 会下载缺少的 Python；首次安装可能需要联网。可编辑安装使源码修改立即生效。自管 Python 环境、构建依赖和测试准备见[开发指南](docs/developer-conventions.md)。

将下面代码保存为 `example.py`。它创建临时项目、保存一个文字层和对象，再从数据库还原成 Python 实例：

```python
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.models import Text, TextLayer
from layerweave.support.api import (
    initialize_database, open_database, transaction,
    save_layer, save_object, load_layer,
)

with TemporaryDirectory() as folder:
    database = initialize_database(Path(folder) / "example.sqlite3")
    with closing(open_database(database)) as connection:
        with transaction(connection) as write:
            project = write.create("project", {"name": "Reading notes"})

        layer = TextLayer(name="Paragraphs")
        save_layer(connection, project["id"], layer)
        note = Text(layer=layer.id, begin=0, end=1,
                    information={"text": "This claim needs a source."})
        save_object(connection, project["id"], note)

        loaded = load_layer(connection, project["id"], layer.id)
        print(loaded.objects[0].information["text"])
```

```powershell
.venv/Scripts/python.exe -X utf8 example.py
```

输出 `This claim needs a source.`。示例数据随临时目录清理；用于实际项目时，将数据库路径换成自己的持久目录。编号由接口返回，实例的保存和读取不需要手写 SQL。[完整读写示例](examples/read_write.py)继续演示关闭重开、修改和查询历史。

## 可以复用什么

| 需求 | 现成能力 |
|---|---|
| 组织信息 | 对象装入层，层组成树；`bind` 连接对象、层以及跨项目的目标 |
| 找到需要的部分 | 按层、子树、位置或区间查询，读取关联与项目概览 |
| 保存一个功能的结果 | 统一写会话处理编号、事务和改动记录 |
| 修正已经写入的内容 | 编辑、历史、撤销和检查工具；事务内可组合多个操作 |
| 接入自己的数据 | 声明工具自有表，共用读写、改动记录和恢复能力 |
| 适配新的内容类型 | Python 类与 TOML 声明一一对应，沿已有封装扩展 |

轴可以表示秒、段落或页码，由项目解释，单位不自动换算。图片和音视频保存路径或链接引用。核心和基础支撑只依赖 Python 标准库；具体操作放在可替换的工具包里。

## 按需组合，专注自己的功能

LayerWeave 的理念是**降低注意力的分散**：处理内容时，只读取当前相关的部分；开发功能时，复用已有能力，把精力放在功能自身。

比如，角色与镜头之间已经建好了关联，要汇总“每个角色出现在哪些镜头”，就可以直接查询现有项目。需要保存结果时，沿用已有的读写和改动记录，再配合撤销工具恢复改动。自己的数据不必全部套用层与对象的形式，也可以登记独立的工具表。

**欢迎你和 AI 基于这个内核开发和扩展。** 层与对象可以组合，`bind` 将它们连接；工具和外置技能按任务选择。内置工具同时提供现成功能与开发参考。完整版本的视图本身也是工具包，独立视图插件进一步展示如何扩展上层应用。

批注是一个例子：完整版本用 `Note` 继承文字对象，用关联表达回复，已读状态和布局则放在视图自己的表里。它复用了既有结构与存储能力。

| 想开发什么 | 从这里开始 |
|---|---|
| 新的层或对象类型 | [模型与封装](src/layerweave/models/README.md)、[Title 示例](examples/title.py) |
| 有自己数据的工具 | [工具表接入](docs/build-with-layerweave/03-managed-tables.md)、[可运行例子](examples/tool_tables.py) |
| 组合多个操作 | [事务内组合](docs/build-with-layerweave/04-composing-tools.md) |
| 跟随项目变化的界面或缓存 | [增量读取](docs/build-with-layerweave/05-incremental-reading.md) |
| 为 AI 提供外置技能 | [技能与工具区](src/layerweave/tool/README.md) |

更多思路见[扩展指南](docs/build-with-layerweave/README.md)，接口参数见[公共 API](src/layerweave/support/API.md)，模块职责见[架构说明](docs/architecture.md)。

## 查找工具与案例

通过现有 help 查看当前工具及示例，或查看层与对象的字段、用途和封装关系：

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

- [文章解析案例](examples/showcases/article-reading/README.md)：用基础 Python/CLI 查询正文、解读和证据。
- [十二个场景案例](examples/showcases/README.md)：创作、阅读、调查、协作和代码梳理；需要视图或批注的案例在完整分支体验。
- [使用现成工具](src/layerweave/tool/builtin/usage/README.md)：读写、查询、编辑、历史与撤销、JSON 交换和模板。
- [维护源码](docs/developer-conventions.md) · [测试导引](tests/README.md) · [文档目录](docs/README.md)。

技能是供 AI 按需阅读的说明和脚本，不会自行执行。本分支保留直接 Python/CLI 调用，不包含网页视图和 MCP 服务封装。

## AI 协作开发

项目由维护者主导设计与维护，Astra（Codex）协助本分支的开发、测试与文档整理。

## 许可证

LayerWeave 源码采用 [MIT](LICENSE)。独立技能、外部库和服务遵循各自的说明；视图构建与第三方网页组件的分发说明见 visualization 分支。

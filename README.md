# LayerWeave

LayerWeave 是一个用层、对象、关联和轴位置组织内容的 Python 工具。AI 或其他程序可以通过 Python 和命令行读写项目，编辑内容的位置，并查看历史、撤销修改。

例如，一个短片项目可以用不同层组织段落说明、字幕、图片和音频引用。每个对象保存自己的内容与起止位置；工具负责查询、编辑和持久化，后续工具可以按需要解释具体媒体。

## 主要能力

- **组织内容**：层级结构、对象和跨项目关联；已有文字、图片、音频、视频、模型和动作封装。
- **查询与编辑**：项目概览、子树与区间展开、对象查找、空档查询，以及接续、排列、平移、分割、复制和搬移。
- **保存与恢复**：SQLite 保存项目，修改记录历史，支持按操作整批撤销与重做。
- **检查与扩充**：按配置检查约定，分别返回写入结果和诊断；通过 Python 类与 TOML 扩充封装。
- **工具自有数据**：声明工具自己的表，选择外部 ID 或共享发号，复用统一读写、事务日志、历史和撤销；已有声明随数据库保存。
- **两种调用方式**：Python API 和 CLI；命令 help 与配置 help 可以查询支持能力和调用示例。

## 开始使用

当前通过源码的本地可编辑安装使用。需要 Python 3.11+、SQLite 3.35+；核心与内部工具运行时只使用标准库，外置技能的媒体依赖按需安装。建议先启用自己的 Python 虚拟环境，具体准备见[开发指南](docs/developer-conventions.md#准备环境)。

取得源码后，在项目目录执行：

```sh
python -m pip install -e .
python -X utf8 -B examples/read_write.py
```

该示例使用临时数据库，演示写入、关闭重开、装载 Python 对象和再次保存。

已有数据库时，先看项目结构：

```sh
python -m layerweave.tool.builtin.usage.query.project_overview DATABASE PROJECT_ID
```

DATABASE 换成数据库路径，PROJECT_ID 换成项目编号。它展示层树和各层直属对象数；需要正文再用 project_details，定位特定对象用 find_objects。反复从文档同步内容时，可用 upsert_objects 按名字或稳定键更新原对象，保留身份与引用；见[使用手册](src/layerweave/tool/builtin/usage/GUIDE.md)。

也可以直接查询命令和可用封装，这两个入口无需数据库：

```sh
python -X utf8 -B -m layerweave.tool.builtin.shared.help.command_help
python -X utf8 -B -m layerweave.tool.builtin.shared.help.config_help combined text
```

## 示例：连续追加两句字幕

在已安装本项目的 Python 环境中运行下面的 Python 代码。它创建一个临时项目，每句占 2 个位置单位，第二句自动接在第一句后面。

```python
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.models import TextLayer
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.support.api import initialize_database, open_database, read_layer
from layerweave.tool.builtin.usage.records.save import save_layer_with_checks
from layerweave.tool.builtin.usage.editing.objects import append_object

with TemporaryDirectory() as directory:
    database = initialize_database(Path(directory) / "demo.sqlite3")
    with closing(open_database(database)) as connection:
        project = dispatch(connection, {
            "action": "create", "kind": "project", "data": {"name": "字幕示例"}
        })
        project_id = project["id"]
        layer = TextLayer(name="字幕")
        save_layer_with_checks(connection, project_id, layer)

        for text in ("你好", "世界"):
            append_object(connection, project_id, layer.id, {
                "config_ref": "objects/text.toml", "information": {"text": text}
            }, duration=2)

        for obj in read_layer(connection, project_id, layer.id)["objects"]:
            print(f"[{obj['begin']:g}, {obj['end']:g}) {obj['information']['text']}")
```

输出：

```text
[0, 2) 你好
[2, 4) 世界
```

编号由接口返回，追加工具计算位置。示例结束后临时数据会清理；实际项目使用自己的数据库路径。更多调用见[使用说明](src/layerweave/tool/builtin/usage/README.md)。

## 当前状态

当前无视图版本已完成核心、内部工具和技能接入的收尾，MCP 封装与 LayerWeave 界面尚未实现。图片、音视频等封装保存资源引用；自带 skills 提供部分媒体生成、处理和检查能力，由调用方按需使用。

非可视化核心会继续独立维护；可视化实现将在单独分支推进。

## 更多资料

- [使用说明](src/layerweave/tool/builtin/usage/README.md)：各类操作、参数与返回。
- [开发指南](docs/developer-conventions.md)：开发准备、源码位置、扩充与验证。
- [架构说明](docs/architecture.md)：概念、模块关系与设计边界。
- [示例索引](docs/examples.md)：可运行的完整场景。
- [技能与外部服务](src/layerweave/tool/README.md)：查找技能、层原型绑定、KEY 接入和输出目录。

安装后只使用 `layerweave` 顶层导入。自带配置与技能材料随包提供；示例在仓库 `examples/` 中以脚本运行。

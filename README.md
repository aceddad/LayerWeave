# LayerWeave

用层、对象、关联及轴位置组织内容的非可视化 Python 核心，供 AI 和其他程序读取、编辑与扩充。已有六类封装、SQLite 存储、配置与检测，以及 25 个内部工具命令。工具范围包括内容查询、位置编辑、跨项目搬移、历史和撤销；视图与 MCP 尚未实现。

## 从这里开始

所有软件自带工具统称为**内部工具**，按用途分为使用工具、开发工具和视图工具。

| 你的任务 | 入口 |
|---|---|
| 使用软件，读取或编辑项目 | [内部工具总导航](src/tools/README.md) → [使用工具](src/tools/usage/README.md) |
| 新增层、对象类或工具，维护核心 | [开发工具与流程](src/tools/developer/README.md) → [公共 API](src/runtime/API.md) |
| 开发或控制将来的界面 | [视图工具边界](src/tools/view/README.md)，当前仅有分类说明 |
| 理解结构、编号、约束和数据语义 | [核心与数据约定](docs/architecture.md) |
| 跑完整示例 | [示例索引](docs/examples.md) |

AI 操作项目时从使用工具进入；准备修改代码时再读取开发工具和开发约定。

## 快速开始

只使用 Python 标准库，需要 Python 3.11+、SQLite 3.35+。从项目目录进入 src：

```sh
cd src
python -X utf8 -B -m tools.shared.command_help
python -X utf8 -B -m tools.shared.config_help combined text
python -X utf8 -B -m examples.read_write
```

前两项无需数据库；示例使用专用临时数据库，演示写入、关闭重开、装载 Python 对象及再次保存。

初始化或升级自己的数据库，再读取项目列表：

```sh
python -X utf8 -B -m tools.developer.database ../output/ai-production.sqlite3
python -X utf8 -B -m tools.usage.crud ../output/ai-production.sqlite3 --request examples/requests/read-projects.json
```

初始化由开发工具调用既有存储实现；普通读取不自动升级数据库。实际数据库不随 Git 提交。JSON 请求格式见[运行协议](src/runtime/README.md)。

## 项目结构

```text
configs/                  层、对象封装和日志汇报配置
src/
  models/                 简单的 Python 层类、对象类
  runtime/                配置读取、存储、事务、日志、检测与公共 API
  tools/                  内部工具统一入口
    usage/                使用工具：CRUD、通用编辑、文字工具
    developer/            开发工具：初始化入口及扩展指南
    view/                 视图工具：仅分类说明
    shared/               共用 help、命令目录和 CLI 辅助代码
  examples/               可运行示例
docs/                     核心约定、开发约定、示例索引、后续候选
tests/                    自动化测试
output/                   本地数据库及已有交付物
scratch/                  不纳入 Git 的临时材料
```

`shared` 是三类工具共用的实现，不是第四类受众。`runtime.api` 保持稳定；旧 `tools.common`、`tools.text`、`runtime.console` 等调用路径保留薄转接，新增代码使用新目录。迁移对照见[内部工具导航](src/tools/README.md)。

## 主要约定

- 模型只保存数据并返回自身，配置、存储和检测由外部代码承担。
- 一份封装 TOML 对应一个 Python 类，type 来自配置；Title/Text 是派生示例。
- 项目内层和对象共用递增编号；关联独立发号，删除与撤销不回收已提交编号。
- 操作结果与检测反馈分别表示；提交后的 error 不意味着写入失败。
- 位置不做轴单位换算；普通写入按精度落点，跨项目迁移与撤销保留原数值。
- 工具复用现有事务、日志和检测，不增加额外权限层或自动媒体处理。

具体规则与例外保留在[核心与数据约定](docs/architecture.md)和[公共 API](src/runtime/API.md)，首页只负责导引。

## 验证与后续

从 src 运行完整测试，使用内存或临时数据库：

```sh
python -X utf8 -B -m unittest discover -s ../tests -v
```

当前 343 项测试全部通过，包含新旧入口、命令发现及文档链接的迁移检查；15 个可运行示例也已通过。

非可视化 main 长期独立可用；早期源码基线标签为 core-v0.1.0。开始界面开发时再建立 visualization 分支，通用功能继续维护在主线。

MCP 的入口数量、编排和展示留到封装阶段讨论。本次仅整理工具归属、代码位置和文档；help 的查询方式与参数保持原有行为。[后续候选](docs/FUTURE.md)保留数据库兼容接入方向。

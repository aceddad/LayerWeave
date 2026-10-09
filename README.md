# LayerWeave

用层、对象、关联及轴位置组织内容的非可视化 Python 核心，供 AI 和其他程序读取、编辑与扩充。当前包含六类封装、SQLite 存储、配置与检测，以及查询、编辑、历史和撤销等内部工具。视图与 MCP 尚未实现。

## 按任务进入

| 你要做什么 | 从哪里开始 |
|---|---|
| 操作已有项目、查找或修改内容 | [内部工具](src/tools/README.md) → [使用工具](src/tools/usage/README.md) |
| 新增层、对象类或内部工具 | [开发工具](src/tools/developer/README.md) |
| 阅读或修改 TOML 配置 | [配置入口](configs/README.md) |
| 理解或扩充 Python 模型 | [模型入口](src/models/README.md) |
| 修改存储、检查或公共接口 | [核心模块](src/runtime/README.md) |
| 了解整体设计 | [架构说明](docs/architecture.md) |
| 跑通示例 | [示例索引](docs/examples.md) |
| 准备做可视化 | [视图工具边界](src/tools/view/README.md) |

AI 修改代码前读取 [AGENTS.md](AGENTS.md)。README 负责导航，详细约定在所链接的专题中维护。

## 快速开始

只使用 Python 标准库，需要 Python 3.11+、SQLite 3.35+。从项目目录进入 src：

```sh
cd src
python -X utf8 -B -m tools.shared.command_help
python -X utf8 -B -m tools.shared.config_help combined text
python -X utf8 -B -m examples.read_write
```

两个 help 无需数据库；示例使用自己的临时数据库。需要实际项目数据库时，运行[开发工具中的初始化命令](src/tools/developer/README.md)，然后使用[CRUD 请求协议](src/runtime/PROTOCOL.md)读写。

## 目录职责

| 目录 | 内容 |
|---|---|
| configs/ | 层、对象及诊断汇报配置 |
| src/models/ | Python 层类和对象类 |
| src/runtime/ | 公共接口、存储、事务、日志、配置读取与检测 |
| src/tools/ | 内部工具：usage、developer、view，以及共用支持 shared |
| src/examples/ | 可运行示例与请求样例 |
| docs/ | 架构、开发约定、示例索引和后续候选 |
| tests/ | 自动化测试 |
| output/ | 本地数据库及已有交付物 |
| scratch/ | 不纳入 Git 的临时材料 |

## 验证与后续

从 src 运行完整测试：

```sh
python -X utf8 -B -m unittest discover -s ../tests -v
```

测试使用内存或专用临时数据库。Git 保存源码、配置与文档，实际项目数据库单独保存。

非可视化 main 长期独立可用；开始界面实现时再建立 visualization 分支。MCP 的入口数量、编排和 help 展示留到封装阶段讨论。[后续候选](docs/FUTURE.md)保存尚未实施的方向。

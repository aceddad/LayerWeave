# LayerWeave 内部工具

这是软件自带工具的统一入口。先按当前任务选择类别，再查看该类用法。目录分类用于组织与导引，不是权限检查；对外 MCP 的注册、编排和展示尚未设计。

| 类别 | 用途 | 文档与代码 |
|---|---|---|
| 使用工具 usage | 读取、创建和编辑项目内容，供 AI 或其他程序调用 | [使用说明](usage/README.md)、[通用工具](usage/common/)、[文字工具](usage/text/)、[CRUD](usage/crud.py) |
| 开发工具 developer | 准备运行环境、开发封装与工具、维护核心 | [开发指南](developer/README.md)、[数据库初始化](developer/database.py) |
| 视图工具 view | 将来的显示、选择、定位和视口操作 | [分类边界](view/README.md)，当前无可执行工具 |

## 共用入口

[shared](shared/README.md) 保存命令 help、配置 help、命令目录和 CLI 辅助实现。两种 help 同时服务使用与开发，不复制两份源码。配置 help 继续保留既有使用版和 --dev 开发版。

从项目 src 运行：

```sh
python -X utf8 -B -m tools.shared.command_help
python -X utf8 -B -m tools.shared.config_help combined text
python -X utf8 -B -m tools.shared.config_help objects model --dev
```

help 暂时保持全部命令总览或指定名称详情，不增加类别筛选或多级菜单。现有 25 个命令中：22 个业务命令位于 usage，2 个共用 help 位于 shared，1 个数据库准备命令位于 developer。日常使用能力共 24 项，视图类没有假命令占位。

## 边界

- 项目概览、详细展开、文本汇集输出项目数据，属于使用工具，不属于视图。
- 基础 CRUD、复查、历史与撤销也是使用工具；Python 请求工厂、连接、load/save、位置计算等扩展接口由开发文档说明。
- 业务工具调用 runtime.api；事务、日志、数据库结构及检测实现继续留在 runtime。
- source 资源引用原样保留。图片、音视频等类型工具按实际需求加到 usage 对应目录。
- 每个新增命令仍在自身模块声明 COMMANDS，由既有目录发现；见[命令声明](shared/COMMANDS.md)。

## 目录迁移与兼容

| 原路径 | 新实现位置 |
|---|---|
| tools.common（除两项 help） | tools.usage.common |
| tools.text | tools.usage.text |
| tools.common.command_help / config_help | tools.shared.command_help / config_help |
| tools.catalog / tools._cli | tools.shared.catalog / tools.shared._cli |
| runtime.console | tools.usage.crud |
| runtime.storage.database 的 CLI | tools.developer.database；数据库函数仍在原存储模块 |

旧 Python 导入和 CLI 保留转接，新示例与文档使用新路径。兼容文件不重复声明命令；旧的工具完整名称仍可查询到同一份命令说明。开发时修改新实现，不复制业务逻辑到旧路径。

原仓库顶层 tools/README.md 的用法迁至[使用说明](usage/README.md)，开发部分迁至[开发指南](developer/README.md)。原 src/tools/COMMANDS.md 迁至 shared/COMMANDS.md。根 README 的详细规则和示例分别迁至[核心与数据约定](../../docs/architecture.md)和[示例索引](../../docs/examples.md)。

# 内部工具

内部工具是 LayerWeave 自身的软件能力；外置技能在同一工具区的 [skills](../README.md) 中。内部工具依赖基础支撑，一个完整包携带自己的业务辅助代码，可按包增减。

| 任务 | 分类 |
|---|---|
| 创建、查询、编辑项目内容，复查、历史和撤销 | [usage](usage/README.md) |
| 初始化数据库、安装技能 ZIP、开发新工具 | [developer](developer/README.md) |
| 查询命令或封装支持 | [shared/help](shared/help/README.md) |
| 未来可视化 | [view](view/README.md)，当前只有边界说明 |

完整包包括 usage 下的 records、query、editing、history、undo、validation、text，以及 shared/help、developer/database、developer/skills。删除某个包后，其他包仍能独立工作；命令发现只展示仍存在的声明。不要只删包中的某个私有辅助文件。

默认写工具可选接入 validation 包；没有它时写入照常完成、checks.status 为 not_run。共用 CLI、help 示例排版和静态发现位于 support，卸掉帮助包不会破坏其他工具的 --help。

完成[本地安装](../../../../docs/developer-conventions.md#准备环境)后，从任意工作目录执行 python -m layerweave.tool.builtin.shared.help.command_help 可查询已安装命令。此轮不新增 MCP 分组或执行接口。

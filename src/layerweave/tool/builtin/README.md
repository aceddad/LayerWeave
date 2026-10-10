# 内部工具

内部工具是 LayerWeave 自身的软件能力；外置技能在同一工具区的 [skills](../README.md) 中。内部工具依赖基础支撑，一个完整包携带自己的业务辅助代码，可按包增减。

| 任务 | 分类 |
|---|---|
| 创建、查询、编辑项目内容，复查、历史和撤销 | [usage](usage/README.md) |
| 初始化数据库、安装技能 ZIP、管理本地 KEY、开发新工具 | [developer](developer/README.md) |
| 查询命令或封装支持 | [shared/help](shared/help/README.md) |
| 只读查看项目：画布上的时间轴画板、最近改动、素材预览；给 AI 的截图、取帧、画板排版、"用户正在看哪儿" | [view](view/README.md) |

完整包包括 usage 下的 records、query、editing、history、undo、validation、text，以及 shared/help、developer/database、developer/skills、developer/keys、view。删除某个包后，其他包仍能独立工作；命令发现只展示仍存在的声明。不要只删包中的某个私有辅助文件。

默认写工具可选接入 validation 包；没有它时写入照常完成、checks.status 为 not_run。共用 CLI、help 示例排版和静态发现位于 support，卸掉帮助包不会破坏其他工具的 --help。

完成[本地安装](../../../../docs/developer-conventions.md#准备环境)后，从任意工作目录执行 python -m layerweave.tool.builtin.shared.help.command_help 可查询已安装命令。MCP 分组与适配留到对应封装阶段。

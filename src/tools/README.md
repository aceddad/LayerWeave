# LayerWeave 内部工具

软件自身的读写、编辑等执行工具从这里进入。按用途分为三类；shared 为它们提供共用实现。[返回项目首页](../../README.md)。层原型 tools 所引用的技能包另见[外置工具](../../tool/README.md)。

| 场景 | 入口 | 实现位置 |
|---|---|---|
| 读取、创建、编辑项目内容 | [使用工具](usage/README.md) | usage/crud.py、usage/common/、usage/text/ |
| 准备运行环境、开发封装和工具 | [开发工具](developer/README.md) | developer/ |
| 控制将来的显示、选择和视口 | [视图工具](view/README.md) | view/ 当前仅有分类说明 |
| 查找命令或配置支持 | [共用帮助](shared/README.md) | shared/ |

现有 25 个命令中，22 个业务命令位于 usage，2 个共用 help 位于 shared，1 个数据库准备命令位于 developer。项目概览、详细展开、复查和撤销均属于使用工具。

工具调用 runtime.api；存储、事务、日志与检测由[核心模块](../runtime/README.md)提供。新增工具按[开发流程](developer/README.md)放置与声明。

分类只负责代码组织和导引。help 继续提供现有总览及指定名称详情；MCP 的注册、入口数量与编排留到封装阶段讨论。

# LayerWeave 工作导引

所有软件自带工具统称为“内部工具”。先按任务选择阅读范围：

- 操作项目内容：从[内部工具](src/tools/README.md)进入[使用工具](src/tools/usage/README.md)。
- 修改代码或增加封装：先读[开发入口](src/tools/developer/README.md)与[开发约定](docs/developer-conventions.md)，再读对应专题和配置。
- 视图工作：先读[视图边界](src/tools/view/README.md)。当前 main 保持不依赖 GUI。

## 工作要求

- 保持基础模型简单，工具复用 runtime.api；存储、发号、事务、日志与检测留在 runtime，不在工具中复制实现。
- 使用工具放 src/tools/usage，开发入口放 developer，共用支持放 shared；view 当前仅有说明。项目尚未发布，只维护当前路径，不新增旧路径转接层。
- 一份封装 TOML 对应一个 Python 类。更改内容约定、位置、编号或撤销行为前，阅读对应主要说明；文档职责表见开发约定。
- README 说明目录职责与阅读入口；长参数、规则和示例放专题文件。修改一项语义时更新其主要说明，其他文档用链接引用。
- 工具用法集中在 usage，共用 help 说明在 shared；runtime 文档面向实现。使用章节先给用途和示例，保留调用方需要的编号、关联和失败行为。
- help 的进一步编排留到 MCP 阶段，不借文档整理增加分组参数、权限限制或注册框架。
- 保留用户数据和无关改动；测试、示例使用内存或专用临时数据库，不写 output 中的真实项目数据。
- 修改持久化、共享执行或模块路径后，从 src 运行 `python -X utf8 -B -m unittest discover -s ../tests -v`，并核对受影响示例和文档链接。
- 非可视化核心留在 main；用户要求开始可视化时再建立独立分支。

# LayerWeave 工作导引

LayerWeave 是非可视化核心。所有软件自带工具统称为“内部工具”。

## 先选择入口

- 操作项目内容：从 [内部工具导航](src/tools/README.md) 进入 [使用工具](src/tools/usage/README.md)。
- 修改代码、增加封装或工具：先读 [开发工具](src/tools/developer/README.md)、[开发约定](docs/developer-conventions.md)，再读相关 API 和 TOML。
- 视图相关工作：先读 [视图工具边界](src/tools/view/README.md)。尚未实现界面，main 保持不依赖 GUI。

## 放置与复用

- 使用工具放 src/tools/usage/common 或对应内容类型目录；开发工具放 developer；共用 help、目录和 CLI 支持放 shared。view 当前只保留分类说明。
- 存储、事务、日志、发号、配置继承和检测留在 src/runtime；工具从 runtime.api 导入能力，不重复实现 SQL 或事务。
- 新封装同时提供 Python 类与 TOML。原始 Layer/Object 保持简单，不塞入功能组件或额外运行时防御。
- 文档入口是 src/tools/README.md。README 保持简短，技术细节放相应模块或 docs。新代码不再写入 tools.common、tools.text 等旧路径；这些文件只兼容已有调用。
- 用户已确定 help 的进一步编排留到 MCP 阶段。本次目录分类不增加 help 分组、权限限制、MCP 注册或自动执行框架。

## 验证与数据

- 保留用户数据和无关改动；示例、测试使用自己的内存或临时数据库，不写 output 中的实际项目数据库。
- 修改持久化、共享执行或模块路径后，从 src 运行 `python -X utf8 -B -m unittest discover -s ../tests -v`。
- 操作结果与检测反馈分开；提交后诊断不表示写入回滚。保持原有编号、关联、位置、继承和撤销语义，详细规则见开发约定。
- 非可视化核心留在 main；用户要求开始可视化时再建立独立分支。

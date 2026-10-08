# LayerWeave 内部工具开发

这里保存项目内部工具的说明。当前先完成核心双向读写，尚未增加业务小工具。

AI 开发工具时按这个顺序阅读：

1. [公共读写 API](../src/runtime/API.md)：完整层/对象的读取、装载和保存。
2. 对应的 [层配置](../configs/layers/README.md) 与 [对象配置](../configs/objects/README.md)：理解内容结构和约定。
3. [完整往返示例](../src/examples/read_write.py)：关闭数据库后重开、修改、再保存。
4. 仅在新增约束时阅读 [规则扩充说明](../src/runtime/validation/README.md)。

Python 工具实现放在 src/tools/<内容类型>/，通用功能放在 src/tools/common/；第一个工具开始实现时再创建目录。这里的 tools/README.md 作为说明入口，不提前增加工具注册框架。

工具使用 `from runtime.api import ...`，只处理自己的业务内容。读取时可选择完整字典或 Python 实例；修改后调用 save_layer/save_object。ID、事务、日志、配置继承、检测由核心处理。

小工具采用普通函数，参数显式带 connection、project_id 和目标编号。需要哪些输入、会修改哪些内容、返回什么，写在函数说明和一个可运行示例中。新工具无需进入核心的 __init__ 批量导入，也不要求 MCP、Skill 或可视化依赖。

涉及删除的工具应明确调用 delete；不要用省略对象或清空局部列表来表达删除。纯查询工具不写数据。模型的 config_ref 留在数据库记录中，自定义用途创建时可明确指定。

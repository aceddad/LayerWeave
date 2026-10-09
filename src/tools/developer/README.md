# 内部工具 · 开发工具

用于准备运行环境、开发封装和内部工具、维护核心实现。[返回内部工具导航](../README.md)。只操作项目内容时，从[使用工具](../usage/README.md)开始。

## 初始化与升级数据库

从项目 src 目录运行：

```sh
python -X utf8 -B -m tools.developer.database ../output/ai-production.sqlite3
```

命令入口在 [database.py](database.py)，复用 runtime 的 initialize_database。建表、已有版本升级、发号仍由存储层实现，日常读取不自动升级数据库。参见[存储说明](../../runtime/storage/README.md)。

## 开发阅读顺序

| 要做什么 | 先读哪里 |
|---|---|
| 查看封装完整定义、继承和字段来源 | [共用配置 help](../shared/README.md)，使用既有 --dev 模式 |
| 新增层或对象封装 | [公共 API](../../runtime/API.md)、[配置继承](../../runtime/configuration/README.md)、[Title 示例](../../examples/title.py) |
| 新增或修改内部工具 | 本页下方的开发流程、[命令声明约定](../shared/COMMANDS.md) |
| 修改事务、关联或撤销 | [核心与数据约定](../../../docs/architecture.md)、[存储说明](../../runtime/storage/README.md) |
| 新增检测约定 | [检测扩展](../../runtime/validation/README.md)、[诊断配置](../../runtime/validation/DIAGNOSTICS.md) |

开始改代码前，读取[开发约定](../../../docs/developer-conventions.md)。load/save、读取快照、位置运算和检查器属于 runtime.api 的开发接口，不逐个包装成新命令。

## 开发内部工具


AI 开发工具时按这个顺序阅读：

1. [公共读写 API](../../runtime/API.md)：完整层/对象的读取、装载和保存。
2. 对应的 [层配置](../../../configs/layers/README.md) 与 [对象配置](../../../configs/objects/README.md)：理解内容结构和约定。
3. [第一批工具示例](../../examples/first_batch.py)、[第二批工具示例](../../examples/second_batch.py)与[完整往返示例](../../examples/read_write.py)：查询组合、位置编辑，以及关闭数据库后重开再保存。
4. 仅在新增约束时阅读 [规则扩充说明](../../runtime/validation/README.md)。

项目使用工具放在 src/tools/usage/<内容类型>/ 或 src/tools/usage/common/；开发工具放 developer，共用基础支持放 shared。src/tools/README.md 作为统一说明入口。目录按实际需要创建，视图目录当前仅保存分类说明；不增加注册框架或 help 编排。

工具使用 `from runtime.api import ...`，只处理自己的业务内容。读取时可选择完整字典或 Python 实例；修改后调用 save_layer/save_object。ID、事务、日志、配置继承、检测由核心处理。

小工具采用普通函数，参数显式带 connection、project_id 和目标编号。需要哪些输入、会修改哪些内容、返回什么，写在函数说明和一个可运行示例中。新工具无需进入核心的 __init__ 批量导入，也不要求 MCP、Skill 或可视化依赖。

命令行的打开数据库、JSON 输出和错误反馈由 [shared/_cli.py](../shared/_cli.py) 复用；它不注册或扫描工具。范围与关联 SQL 放在核心 [storage/queries.py](../../runtime/storage/queries.py)，工具通过 runtime.api 调用。需要连续几次一致的读取，可使用 read_snapshot 复用现有读取事务。

需要先读取再计算写入的工具，使用 `dispatch(connection, request_factory)`：工厂接收 read_record 查询函数，在写事务内返回一个请求字典或请求列表。不要在事务外先计算层尾再单独保存，也不要在工厂中自行写 SQL 或调用另一个完整事务入口。现有位置工具可作为例子。

生成新坐标时复用 [PositionMath/decimal_value](../../runtime/positions.py)，从 runtime.api 导入，共享十进制运算、轴来源查找与精度落点；原 tools/common/_precision.py 仅保留导入兼容。纯读取工具继续使用原始存储数值，不调用取整逻辑。

涉及删除的工具应明确调用 delete；不要用省略对象或清空局部列表来表达删除。纯查询工具不写数据。模型的 config_ref 留在数据库记录中；实例保存按实际 Python 类取得唯一配置。新增封装同时提供自己的类与 TOML，字典保存明确指定 config_ref。Title/Text 的继承与往返示例见 `src/examples/title.py`。

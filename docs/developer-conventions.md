# LayerWeave 开发指南

开发者和修改代码的 AI 从这里了解开发准备、源码位置与实现要求。项目用途及使用示例见[README](../README.md)，设计关系见[架构说明](architecture.md)。

## 开发准备

取得源码后，使用 Python 3.11+、SQLite 3.35+；当前只依赖标准库。从项目 src 目录运行命令和示例：

```sh
cd src
python -X utf8 -B -m examples.read_write
```

该例子使用临时数据库，适合验证本地环境。需要持久数据库时，使用[开发工具中的初始化入口](../src/tools/developer/README.md)。

## 选择任务

| 要做什么 | 阅读入口 |
|---|---|
| 新增层或对象封装 | [模型](../src/models/README.md)、[配置](../configs/README.md)，参考 [Title 示例](../src/examples/title.py) |
| 新增或维护内部工具 | [内部工具开发流程](../src/tools/developer/README.md)、[公共 API](../src/runtime/API.md) |
| 修改存储、检测或配置读取 | [核心模块](../src/runtime/README.md)，再读对应实现专题 |
| 开发视图 | [视图边界](../src/tools/view/README.md)，开始实现时再建立独立分支 |
| 修改说明、示例或文档布局 | [文档约定](documentation.md) |

## 源码与材料位置

| 目录 | 职责 |
|---|---|
| configs/ | 层、对象与诊断汇报配置 |
| src/models/ | Python 基础类和派生类 |
| src/runtime/ | 公共接口、配置读取、存储、事务、日志及检测 |
| src/tools/ | usage 使用工具、developer 开发入口、view 视图分类、shared 共用支持 |
| src/examples/ | 可运行示例与请求样例 |
| tests/ | 自动化测试 |
| docs/ | 架构、开发指南、文档约定、示例索引及后续候选 |
| output/ | 本地数据库与已有交付物 |
| scratch/ | 不纳入 Git 的临时材料 |

## 实现原则

1. 基础模型保存数据，维持按需导入。新约束、资源解释或媒体处理应有明确需求，不自动加入模型构造和属性赋值。
2. 内部工具从 runtime.api 获取能力；SQL、发号、事务、日志、配置继承和检测由核心维护。普通读后写用 dispatch 请求工厂，复杂操作通过 run_operation 组合低层步骤，避免嵌套完整操作入口。
3. 一次操作内需要一致的读取时使用 read_snapshot。纯查询保持原始存储数值，不写入、迁移或制造日志。生成位置使用公共位置计算；恢复与迁移的例外按对应专题执行。
4. 每个命令在自身模块声明字面量 COMMANDS；复用 shared/_cli 和既有目录发现。配置 help 使用 Loader 与 DiagnosticPolicy，不硬编码封装名单或导入类来展示说明。
5. 将“已提交什么”和“检查发现什么”分别表达，复用 runtime.feedback。具体结果字段以请求协议为准。
6. 新封装同时提供 Python 类和 TOML。修改约定时阅读主要说明与现有测试，保持原有继承、编号、关联和恢复语义。
7. 项目尚未发布，只维护当前模块路径。MCP 编排与视图实现按对应阶段推进，main 保持无 GUI 依赖。

## 验证与交付

修改持久化、共享执行或模块路径后，从 src 运行完整测试：

```sh
python -X utf8 -B -m unittest discover -s ../tests -v
```

按影响运行相关[示例](examples.md)。测试和示例使用内存或专用临时数据库，保留 output 中的实际项目数据；源码版本不代表用户数据快照。

行为变化同步其主要说明与例子。文档的受众划分、主要维护位置、写作方式和检查要求统一见[文档约定](documentation.md)，不在本页重复维护。

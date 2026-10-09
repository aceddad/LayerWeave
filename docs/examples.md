# 可运行示例

从项目 src 目录运行。示例使用内存或专用临时数据库，不修改 output 中的实际项目数据。[返回项目首页](../README.md)。

| 想了解什么 | 示例模块 |
|---|---|
| 写入、关闭重开、装载 Python 类、再次保存 | [examples.read_write](../src/examples/read_write.py) |
| 基础 CRUD 与事务日志 | [examples.crud](../src/examples/crud.py) |
| 操作结果与诊断文字 | [examples.feedback](../src/examples/feedback.py) |
| 汇报配置与精度处理 | [examples.diagnostics](../src/examples/diagnostics.py) |
| Python 与 TOML 的派生关系 | [examples.title](../src/examples/title.py) |
| 文字层和对象的内存结构 | [examples.text](../src/examples/text.py) |
| 六类模型组合 | [examples.all_layers](../src/examples/all_layers.py) |
| 查询配置支持 | [examples.config_help](../src/examples/config_help.py) |
| 概览、对象检索、关联查询、文本汇集 | [examples.first_batch](../src/examples/first_batch.py) |
| 只查看层树与数量 | [examples.project_overview](../src/examples/project_overview.py) |
| 多子树、时间范围与精简展开 | [examples.project_details](../src/examples/project_details.py) |
| 接续、排列、平移、对齐、时长和对象复制 | [examples.second_batch](../src/examples/second_batch.py) |
| 复查、历史、撤销与重做 | [examples.review_history](../src/examples/review_history.py) |
| 删除与复制子树 | [examples.subtrees](../src/examples/subtrees.py) |
| 分割、插空档、空档查询与跨项目操作 | [examples.editing](../src/examples/editing.py) |

例如：

```sh
python -X utf8 -B -m examples.read_write
python -X utf8 -B -m examples.editing
```

示例中的编号来自该次运行或内存演示上下文。操作实际数据库时使用工具返回的编号；请求格式见 [CRUD 协议](../src/tools/usage/CRUD.md)。

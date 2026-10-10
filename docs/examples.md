# 可运行示例

完成安装后，从项目根运行示例脚本；examples 不安装为全局 Python 包。示例使用内存或专用临时数据库，不修改 output 中的实际项目数据。[返回项目首页](../README.md)。

| 想了解什么 | 示例脚本 |
|---|---|
| 写入、关闭重开、装载 Python 类、再次保存 | [examples.read_write](../examples/read_write.py) |
| 基础 CRUD 与事务日志 | [examples.crud](../examples/crud.py) |
| 操作结果与诊断文字 | [examples.feedback](../examples/feedback.py) |
| 汇报配置与精度处理 | [examples.diagnostics](../examples/diagnostics.py) |
| Python 与 TOML 的派生关系 | [examples.title](../examples/title.py) |
| 文字层和对象的内存结构 | [examples.text](../examples/text.py) |
| 六类模型组合 | [examples.all_layers](../examples/all_layers.py) |
| 查询配置支持 | [examples.config_help](../examples/config_help.py) |
| 概览、对象检索、关联查询、文本汇集 | [examples.first_batch](../examples/first_batch.py) |
| 只查看层树与数量 | [examples.project_overview](../examples/project_overview.py) |
| 多子树、时间范围与精简展开 | [examples.project_details](../examples/project_details.py) |
| 接续、排列、平移、对齐、时长和对象复制 | [examples.second_batch](../examples/second_batch.py) |
| 复查、历史、撤销与重做 | [examples.review_history](../examples/review_history.py) |
| 删除与复制子树 | [examples.subtrees](../examples/subtrees.py) |
| 分割、插空档、空档查询与跨项目操作 | [examples.editing](../examples/editing.py) |

例如：

```sh
python -X utf8 -B examples/read_write.py
python -X utf8 -B examples/editing.py
```

示例中的编号来自该次运行或内存演示上下文。操作实际数据库时使用工具返回的编号；请求格式见 [CRUD 协议](../src/layerweave/tool/builtin/usage/CRUD.md)。

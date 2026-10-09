# 内部工具 · 使用工具

使用工具处理项目内容，支持 Python 和 CLI 调用。[返回内部工具](../README.md)。

## 按操作查说明

| 要做什么 | 详细说明 |
|---|---|
| 创建、读取、修改、删除，或发送一批请求 | [CRUD 请求与反馈协议](CRUD.md) |
| 看项目、查对象、查关联、汇集文字 | [使用手册](GUIDE.md) |
| 接续新增、排列、对齐、修改时长、复制对象 | [使用手册](GUIDE.md) |
| 查找空档 | [使用手册](GUIDE.md#空档查询) |
| 平移、分割、插空档、跨项目复制或剪切 | [编辑说明](EDITING.md) |
| 复制或删除整棵子树 | [子树说明](SUBTREES.md) |
| 复查、历史、撤销或重做 | [历史与恢复](HISTORY.md) |
| 查询工具和可用封装 | [共用 help](../shared/README.md) |

## 调用起点

从项目 src 运行命令 help，或查看某个命令的 --help。输入、输出和完整示例由工具自己的说明提供：

```sh
python -m tools.shared.command_help
python -m tools.shared.command_help project_details append_object --json
```

Python 公共读写接口见 [API](../../runtime/API.md)。实际执行例子见[示例索引](../../../docs/examples.md)。写入结果与检测反馈需要分别阅读，格式由 CRUD 协议统一说明。

## 代码位置

- [crud.py](crud.py)：基础读写入口。
- [common/](common)：与内容类型无关的查询、编辑和恢复工具。
- [text/](text)：文字内容工具，当前为文本汇集。

本页负责选择入口；详细参数、返回与边界放在相应手册中。

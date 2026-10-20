# 可运行示例

面向使用者的完整场景案例存放在[场景演示目录](../examples/showcases/README.md)；本页介绍 Python 接口示例。

完成安装后，从项目根运行示例脚本；examples 不安装为全局 Python 包。示例使用内存或专用临时数据库，不修改 output 中的实际项目数据。[返回项目首页](../README.md)。

| 想了解什么 | 示例脚本 |
|---|---|
| 写入、关闭重开、装载 Python 类、再次保存 | [read_write.py](../examples/read_write.py) |
| 视图复用层编号、自定义发号簇和原身份恢复 | [numbering.py](../examples/numbering.py) |
| 多个工具一次提交、失败回滚与领号反馈 | [composition.py](../examples/composition.py) |
| 稳定键同步、增量刷新和关联阅读 | [sync_and_refresh.py](../examples/sync_and_refresh.py) |
| JSON 模板、导出编辑、复制与撤销 | [exchange.py](../examples/exchange.py) |
| 逻辑引用、状态随复制换号与已读进度跳过 | [logical_references.py](../examples/logical_references.py) |
| 基础 CRUD 与事务日志 | [crud.py](../examples/crud.py) |
| 工具表与核心记录共用历史、撤销和恢复 | [tool_tables.py](../examples/tool_tables.py) |
| 自动登记基础部分、全部内部工具与版本工具自身 | [versions.py](../examples/versions.py) |
| 操作结果与诊断文字 | [feedback.py](../examples/feedback.py) |
| 汇报配置与精度处理 | [diagnostics.py](../examples/diagnostics.py) |
| Python 与 TOML 的派生关系 | [title.py](../examples/title.py) |
| 文字层和对象的内存结构 | [text.py](../examples/text.py) |
| 六类模型组合 | [all_layers.py](../examples/all_layers.py) |
| 查询配置支持 | [config_help.py](../examples/config_help.py) |
| 概览、对象检索、关联查询、文本汇集 | [first_batch.py](../examples/first_batch.py) |
| 只查看层树与数量 | [project_overview.py](../examples/project_overview.py) |
| 多子树、时间范围与精简展开 | [project_details.py](../examples/project_details.py) |
| 接续、排列、平移、对齐、时长和对象复制 | [second_batch.py](../examples/second_batch.py) |
| 复查、历史、撤销与重做 | [review_history.py](../examples/review_history.py) |
| 删除与复制子树 | [subtrees.py](../examples/subtrees.py) |
| 分割、插空档、空档查询与跨项目操作 | [editing.py](../examples/editing.py) |

例如：

完整版本另有 [mcp_extension](https://gitee.com/emotion1354414/layer-weave/blob/visualization/examples/mcp_extension/README.md)，演示 entry points、开发目录与 direct/routed；它需要完整版本的 MCP 服务，不随 main 安装。

```sh
python -X utf8 -B examples/read_write.py
python -X utf8 -B examples/editing.py
```

示例中的编号来自该次运行或内存演示上下文。操作实际数据库时使用工具返回的编号；请求格式见 [CRUD 协议](../src/layerweave/tool/builtin/usage/CRUD.md)。

## 连续追加两句字幕

在已安装本项目的 Python 环境中运行下面的 Python 代码。它创建一个临时项目，每句占 2 个位置单位，第二句自动接在第一句后面。

```python
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.models import TextLayer
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.support.api import initialize_database, open_database, read_layer
from layerweave.tool.builtin.usage.records.save import save_layer_with_checks
from layerweave.tool.builtin.usage.editing.objects import append_object

with TemporaryDirectory() as directory:
    database = initialize_database(Path(directory) / "demo.sqlite3")
    with closing(open_database(database)) as connection:
        project = dispatch(connection, {
            "action": "create", "kind": "project", "data": {"name": "字幕示例"}
        })
        project_id = project["id"]
        layer = TextLayer(name="字幕")
        save_layer_with_checks(connection, project_id, layer)

        for text in ("你好", "世界"):
            append_object(connection, project_id, layer.id, {
                "config_ref": "objects/text.toml", "information": {"text": text}
            }, duration=2)

        for obj in read_layer(connection, project_id, layer.id)["objects"]:
            print(f"[{obj['begin']:g}, {obj['end']:g}) {obj['information']['text']}")
```

输出：

```text
[0, 2) 你好
[2, 4) 世界
```

编号由接口返回，追加工具计算位置。示例结束后临时数据会清理；实际项目使用自己的数据库路径。更多调用见[使用说明](../src/layerweave/tool/builtin/usage/README.md)。

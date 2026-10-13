# 用法四：在一个事务里组合工具

需要把接续、平移、保存、撤销等操作作为一批完成时，使用公开的 *_in_session 函数。它们接受同一个 write，复用独立工具的业务实现，返回数据而不提交事务。[返回开发指导](README.md)。

## 从一次组合开始

以下 connection 是已初始化的连接，project_id/layer_id 来自实际存在的项目和层：

```python
from layerweave.support.api import run_operation
from layerweave.support.providers import optional_checker
from layerweave.tool.builtin.usage.editing.objects import append_object_in_session
from layerweave.tool.builtin.usage.editing.timeline import shift_objects_in_session

def work(write):
    first = append_object_in_session(
        write, project_id, layer_id,
        {"config_ref": "objects/text.toml", "information": {"text": "第一句"}},
        duration=2,
    )
    second = append_object_in_session(
        write, project_id, layer_id,
        {"config_ref": "objects/text.toml", "information": {"text": "第二句"}},
        duration=3,
    )
    return shift_objects_in_session(
        write, project_id, [first["id"], second["id"]], offset=1,
    )

result = run_operation(connection, work, checker=optional_checker())
```

两次新增和一次平移共用一个 operation_id。写入失败会抛出异常，由最外层回滚本批数据、编号和日志；内容检测只在提交后执行一次，检测问题不撤销已经提交的数据。省略 checker 则按基础支撑约定不检测。

也可以在 with transaction(connection) as write 内调用这些函数，由调用方直接处理异常。不要吞掉失败异常后把它当成普通返回数据，除非有意接受自己选择的部分操作；字典里的 ok 字段仍可以是业务数据，支撑不会猜测其含义。

## 选择独立入口还是事务内入口

| 场景 | 使用方式 | 返回及失败行为 |
|---|---|---|
| 只执行一个完整工具 | 原来的 append_object(connection, ...) 等入口 | 开启事务，返回 operation/ok/data 或 results/checks |
| 多个操作一起提交 | *_in_session(write, ...) | 返回记录、记录列表或业务摘要；失败抛出异常，外层统一提交与反馈 |
| 直接读写几个字段 | write.read/create/update/delete/restore | 使用同一会话里的记录原语 |

已有 LayerWeave 会话内误调独立操作入口，会直接抛出包含 *_in_session 提示的 ValueError。它不会再被包装为内层失败字典、被外层当成普通数据提交。外部手动开启的待提交 SQLite 事务仍由调用方处理，独立操作不会接管它。

事务内函数不接受 checker，由最外层决定检测方式。只用于检测的 config_root 也不再出现在事务内编辑接口中；需要实际解析配置的 dispatch/save 仍接受 config_root。参数以对应函数签名为准。

## 公开入口与返回

下表模块名均以 layerweave 开头，列出的函数已经存在。命令 help 详情也提供 session_entrypoint；这是 Python 组合入口，不是新 CLI 命令。

| 模块 | 事务内函数 | 返回 |
|---|---|---|
| tool.builtin.usage.editing.objects | append_object_in_session、copy_object_in_session | 对象记录 |
| tool.builtin.usage.editing.upsert | upsert_objects_in_session | scope、counts、items（匹配值、动作与对象记录） |
| tool.builtin.usage.editing.positions | arrange_objects_in_session、align_objects_in_session | 对象记录列表 |
| tool.builtin.usage.editing.positions | set_duration_in_session | 对象记录 |
| tool.builtin.usage.editing.timeline | shift_objects_in_session | 对象记录列表 |
| tool.builtin.usage.editing.timeline | split_object_in_session、insert_gap_in_session | 原独立结果 data 中的业务摘要 |
| tool.builtin.usage.editing.tree_service | copy_subtree_in_session、delete_subtree_in_session、transfer_subtree_in_session、transfer_objects_in_session | 原独立结果 data 中的业务摘要 |
| tool.builtin.usage.records.dispatch | dispatch_in_session | 单条请求的数据，或与请求顺序一致的数据列表 |
| tool.builtin.usage.undo.service | undo_operation_in_session | undone_operation_id、restored_records |
| support.api | save_layer_in_session、save_object_in_session | 保存后的完整层/对象记录 |

保存的事务内接口不回填输入 Python 实例或字典的 id/layer/bind；使用返回的记录继续组合，提交后可按返回编号重新 load。独立 save 接口仍在成功提交后回填输入。事务内返回的编号在外层提交前属于临时结果，失败后不得继续引用。

撤销也可以与其他业务操作组合。日志的每条改动保留自己的 undo_of；历史列表只有整批改动来自同一撤销目标时才设置顶层 undo_of，混合操作用 undo_of_operations 列出来源，并在各条改动上说明。

数据库初始化、结构登记、文件工具及版本扫描仍使用各自的开发入口，不作为这批事务内项目内容接口。不同工具包继续独立安装，组合时由调用方导入需要的包。

## 领号反馈

单独调用 allocate 或 increment 推进计数后，run_operation 返回 applied=true、operation.status=committed。operation.changes 继续保存业务记录修改；非空 operation.numbering 单独保存领号信息。它不是数据库 changes 日志，不创建可撤销的业务记录，也不回收已提交编号。

例如，只领号的成功反馈中，changes 可以为空；判断整个操作是否发生变化时使用 applied/status，不要用 len(changes) 代替。失败结果不包含回滚掉的领号信息。完整字段见[公共 API](../../src/layerweave/support/API.md#统一写会话)和[编号模块](../../src/layerweave/support/numbering/README.md)。

从源码根运行 examples/composition.py，可以实际验证组合提交、失败回滚和单独领号，示例只使用临时数据库。

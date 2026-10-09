# 范围编辑的实现

调用参数、返回和边界行为统一维护在[使用说明](../EDITING.md)。本文只说明核心组合方式。[返回存储模块](../../../../src/support/storage/README.md)。

## 模块分工

| 模块 | 实现职责 |
|---|---|
| [timeline.py](timeline.py) | 对象选择、切点和分段规划、插空档的组合写入 |
| [positions.py](../../../../src/support/positions.py) | PositionMath、decimal_value 和 shifted_positions |
| [subtrees.py](tree_service.py) | 子树与对象跨项目迁移，共用创建、改指和删除步骤 |
| [crud.py](../../../../src/support/storage/crud.py) | 实际发号、记录写入与日志；工具通过 support.records 使用 |
| [operation.py](../../../../src/support/operation.py) | 事务边界、操作编号、结果与提交后检查 |

CLI 与格式化在本包的 split、gaps、positions、transfer、transfer_objects 模块。入口调用本包业务函数和支撑，不在 CLI 中实现存储步骤。

## 组合方式

1. 在写事务内读取选择范围和当前位置，避免读取后到写入前使用过期数据。
2. 分割与插空档先规划整批变化，再复用同一套分段和位置计算函数执行。
3. 普通平移在本包 _plan 中生成并执行 update 步骤，不依赖 records 工具包；复合动作使用 run_operation，共享一个操作编号，不嵌套完整操作入口。
4. 跨项目操作复用 subtrees 的 _transfer_records，先取得选中范围的记录和关联，再创建目标、调整外部入向引用并按模式删除源。
5. 检查器只在最终状态提交后执行一次，数据和日志失败均交由共享事务回滚。

## 坐标写入的实现选择

- 普通位置工具使用 PositionMath 和 CRUD 的常规落点流程。
- stretch 只提交 end 字段，避免把旧 begin 重新写入或量化。
- 跨项目复制通过 support.records.create_exact 写入原值，沿用发号和日志，但不经过普通位置量化。
- 撤销包规划恢复后调用支撑的 restore，不重新发号；见[恢复实现](../undo/IMPLEMENTATION.md)。

维护时先核对使用说明中的可观察行为，再调整内部步骤；无需在这里重写参数表或调用示例。

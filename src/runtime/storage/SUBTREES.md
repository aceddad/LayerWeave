# 子树删除与整层复制

两项操作都包含指定起始层、全部子孙层和它们直接装载的对象。范围读取、写入及日志共用一个写事务和 operation_id；任意失败整批回滚，成功后沿用提交后检查。操作可用 undo_operation 整批撤销和重做。

删除子树时，一起删除树内实体发出的 bind，包括内部关联和出向外部的关联。外部实体指向树内的入向关联保留，由现有检测报告失效引用。普通单条 delete 的行为不变。

复制在同项目、同父层下创建副本，可另指定副本根层名字。所有层、对象和被复制的关联获得新编号。树内 father、对象 layer 和 bind 内部端点改用新编号；出向外部的目标保持完整原引用；不复制外部实体发出的入向关联。自关联和相互关联同样按编号映射处理。

information 自由内容、配置引用、轴说明、备注和资源路径按源记录复制，不猜测内容中的数字是否为编号，不复制媒体文件或新建 Python/TOML 封装。对象位置沿用普通写入的轴精度落点规则，无单位换算或自动平移。默认保留名字；同名记录允许存在。

返回标准 operation/operation_id/ok/applied/checks；data 提供范围、层/对象/关联数量。复制另外返回新根层 layer_id 和 id_map，按 layer/object/bind 分组列出 old_id/new_id，编号为数值。不存在的起始层明确报告失败，不修改其他内容。

核心编排位于 storage/subtrees.py，经 runtime.api 提供；工具与 CLI 位于 tools/common/subtrees.py。新编号使用现有 CRUD 发放，日志复用既有通道，不新增表或模型字段。

## Python

```python
from runtime.api import copy_subtree, delete_subtree, undo_operation

# connection 是已打开且无待提交事务的连接，编号来自实际项目。
copied = copy_subtree(connection, project_id, layer_id, name="歌词修改版")
if copied["ok"]:
    new_root = copied["data"]["layer_id"]
    # 每种编号分别提供映射；不会把关联 id 当作对象 id。
    object_map = {item["old_id"]: item["new_id"] for item in copied["data"]["id_map"]["object"]}

deleted = delete_subtree(connection, project_id, layer_id)
if deleted["ok"]:
    restored = undo_operation(connection, deleted["operation_id"])
```

两项工具都接受 config_root 和 checker，语义与 dispatch 一致：默认检查，显式 checker=None 关闭检查。配置损坏不阻止复制原始记录，提交后逐条报告；复制不导入配置绑定的 Python 类。config_root 只决定检查采用的配置目录，不复制或修改配置文件。

复制先按树序创建层，再创建对象，最后创建发出关联。记录使用核心实际发放的新编号，工具不预测 max_id。father 的内部引用在对象写入前全部完成，位置解释使用副本的最终轴环境。已有父链环不会无限展开；内部环按映射保留，并由现有检查报告。删除在事务最终状态验证外键，允许一次清除整个已成环范围。

成功返回例子中的 id_map 结构如下（数字仅示意）：

```json
{
  "project_id": 1,
  "source_layer_id": 4,
  "layer_id": 10,
  "counts": {"layers": 1, "objects": 1, "binds": 1},
  "id_map": {
    "layer": [{"old_id": 4, "new_id": 10}],
    "object": [{"old_id": 5, "new_id": 11}],
    "bind": [{"old_id": 2, "new_id": 7}]
  }
}
```

删除的 data 不包含 id_map；layer_id 表示已删除的起始层。两个工具的 operation.changes 提供完整已提交目标，operation_id 可交给历史与撤销工具。恢复时若父层已删除或副本被后续修改，仍依照现有撤销冲突规则整批拒绝，不覆盖后续操作。

## CLI 与示例

从 src 运行，数据库路径及编号替换为实际值：

```sh
python -X utf8 -B -m tools.common.subtrees DATABASE PROJECT_ID copy LAYER_ID --name "歌词修改版"
python -X utf8 -B -m tools.common.subtrees DATABASE PROJECT_ID delete LAYER_ID --json
python -X utf8 -B -m tools.common.subtrees DATABASE PROJECT_ID copy LAYER_ID --config-root CONFIG_DIRECTORY --json
python -X utf8 -B -m tools.common.undo DATABASE OPERATION_ID
```

默认文字输出显示数量、复制编号映射、操作结果和逐条诊断；--json 返回完整结构。失败退出码 1，已提交但存在诊断仍为 0。--name 仅用于 copy。

运行 `python -X utf8 -B -m examples.subtrees` 查看歌词、段落标记与外部伴奏之间的内部/外部引用示例；它使用自己的内存数据库，不修改真实项目。跨项目复制/剪切由同模块的 transfer_subtree 提供，复用创建与删除逻辑，见 [编辑工具](EDITING.md)。另选父层和资源文件复制不属于当前入口；位置调整使用独立平移工具。

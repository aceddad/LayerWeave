# 子树复制与删除

一次处理起始层、全部子孙层和它们装载的对象。[返回使用入口](README.md)。

Python 使用已打开且没有待提交操作的 connection。示例编号来自实际项目；CLI 从 src 运行。

## 复制子树

在同一项目、同一父层下创建一个副本，可指定副本根层名称。

```python
from runtime.api import copy_subtree

copied = copy_subtree(connection, project_id, layer_id, name="歌词修改版")
if copied["ok"]:
    new_root = copied["data"]["layer_id"]
```

**输入：**project_id、起始 layer_id，以及可选的 name。

**返回：**标准操作结果；data 含 project_id、source_layer_id、layer_id（新根）、counts 和 id_map。例如：

```json
{
  "project_id":1,"source_layer_id":4,"layer_id":10,
  "counts":{"layers":1,"objects":1,"binds":1},
  "id_map":{
    "layer":[{"old_id":4,"new_id":10}],
    "object":[{"old_id":5,"new_id":11}],
    "bind":[{"old_id":2,"new_id":7}]
  }
}
```

**边界行为：**

- 层、对象和复制出的关联都取得新编号；同名记录可以存在。
- 内部父子关系、对象归属和关联端点换成新编号，包括自关联与相互关联。
- 出向外部的关联保留完整目标地址；外部实体发出的入向关联不复制。
- 内容、配置引用、轴说明、备注和资源路径按源记录复制。自由内容中的数字不自动当作编号改写。
- 对象位置按副本的轴精度落点；不换算单位、自动平移或复制媒体文件。
- 不存在的起始层报告失败。已有父链环只处理一次，复制后仍由检查报告相关问题。

```sh
python -m tools.usage.common.subtrees DATABASE PROJECT_ID copy LAYER_ID --name "歌词修改版" --json
```

跨项目操作见[搬移子树](EDITING.md#跨项目复制或剪切子树)；当前同项目复制入口不能另选父层。

## 删除子树

删除选中的完整子树和树内实体发出的关联。

```python
from runtime.api import delete_subtree

deleted = delete_subtree(connection, project_id, layer_id)
```

**返回：**data 含 project_id、layer_id（已删除的起始层）和 counts，没有 id_map。

**边界行为：**

- 出向关联随所属实体删除，包括指向范围外的关联。
- 外部实体指向范围内的入向关联保留，检查会报告失效引用。
- 普通 CRUD 的单条 delete 仍只删除指定记录。
- 不存在的起始层报告失败，不扩大删除范围；已有环可以作为整批范围删除。

```sh
python -m tools.usage.common.subtrees DATABASE PROJECT_ID delete LAYER_ID --json
```

## 结果、撤销与选项

```python
from runtime.api import undo_operation

if deleted["ok"] and deleted["applied"]:
    restored = undo_operation(connection, deleted["operation_id"])
```

- 一次复制或删除共用一个 operation_id，操作失败整批不写，成功后可整批撤销/重做。
- 后续修改可能阻止恢复，例如副本被改过或恢复所需父层被删除。完整冲突规则见[历史与恢复](HISTORY.md#撤销与重做)。
- Python 可传 config_root、checker；默认检查，checker=None 关闭自动检查。CLI 可用 --config-root。
- 配置损坏不阻止复制原始记录，提交后报告问题；config_root 只选择检查配置，不复制配置文件。
- 默认文字输出列出数量、编号映射与逐条诊断；--json 返回完整结果。操作失败退出码为 1，已提交但有诊断仍为 0。--name 仅用于 copy。

完整内存示例：`python -m examples.subtrees`。操作反馈字段见 [CRUD 协议](CRUD.md)。

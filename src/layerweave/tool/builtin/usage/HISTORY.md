# 复查、历史与撤销

复查和历史只读取数据；撤销会写入一次新的操作。[返回使用入口](README.md)。

Python 示例使用已有 connection 和实际编号。CLI 完成可编辑安装后运行，DATABASE 替换为已有数据库路径。

## 复查

按当前配置重新检查项目、子树或对象。

```python
from layerweave.tool.builtin.usage.validation.recheck import recheck

whole = recheck(connection, project_id)
trees = recheck(connection, project_id, layer_ids=[4, 7])
objects = recheck(connection, project_id, object_ids=[8, 12])
```

| 输入 | 含义 |
|---|---|
| project_id | 要检查的项目 |
| layer_ids | 多棵子树，包含起始层、后代和直属对象 |
| object_ids | 指定对象 |
| config_root | 可选，当前检查使用的配置目录 |

**返回：**scope、counts（所选层/对象数量）、status、issues、issue_counts。

**边界行为：**

- layer_ids 与 object_ids 互斥。均省略时检查全项目，显式空列表是空选择。
- 重复范围去重；缺失目标逐条报告，其余继续。
- 必要的同层或关联检查可能涉及所选范围外的目标；counts 不是执行规则的次数。
- completed 表示检查执行完成，仍可包含 error；partial 表示部分检查无法完成，静音也不会隐藏这一状态。
- 修改 TOML 后可直接复查；不修改业务数据、不制造操作历史。

```sh
python -m layerweave.tool.builtin.usage.validation.cli DATABASE PROJECT_ID --layer-ids 4 7 --json
python -m layerweave.tool.builtin.usage.validation.cli DATABASE PROJECT_ID --object-ids 8 12 --json
```

## 历史

MCP 通用 query 的外层 limit 只控制回复每页展示几次操作；查询最近三次操作使用 arguments.limit=3。历史结果按 items 分页，一次操作内部的 changes 保持完整，过大时明确给出文本片段。先以 more.cursor 续取本次回复；读完后再把业务 next_cursor 作为 arguments.before 查询下一批。回复尚未读完时 next_cursor 暂置 null，more.business_cursor_pending=true 表示它尚未交付，而不是历史已到末尾。Python/CLI 的 limit 和 before 仍按下文表示业务分页。

查看相关操作、每次改动的字段及前后数据，已删除的实体也可以查询。

```python
from layerweave.tool.builtin.usage.history.service import read_history

page = read_history(connection, project_id, kind="object", id=object_id, limit=20)
if page["next_cursor"] is not None:
    next_page = read_history(connection, project_id, kind="object", id=object_id,
                             limit=20, before=page["next_cursor"])
operation = read_history(connection, operation_id=operation_id)
```

| 输入 | 含义 |
|---|---|
| project_id、kind、id | 按项目或记录筛选；kind 支持 project/layer/object/bind 及本库已登记的工具 kind |
| operation_id | 查询一个完整操作，与项目/实体筛选互斥 |
| limit、before | 每页操作数（默认 20）和上一页的 next_cursor |
| detail | True 时给列表附带完整前后快照；默认 False |

**返回：**operation_count（匹配的操作次数）、change_count（原始改动条数）、items 和 next_cursor。

- 每项含 operation_id、undo_of、时间、project_ids、change_count、matched_change_count 和 changes。
- 更新记录的 fields 表示字段差异；path 是键数组，before_present/after_present 区分缺失与 null。
- 字典差异递归展开，列表整体比较；1、1.0、true 分开表示。发号状态 max_id 及登记的其他计数列不作为内容差异展示。

**边界行为：**

- 省略范围可查全库。层、对象及 scoped 工具表的 id 还需 project_id；独立表按本表 id 定位。
- 按日志编号倒序分页，不切开一个操作。只在 next_cursor 非空时请求下一页。
- 范围决定哪些操作相关，items 仍展开完整批次；跨项目操作不会被截断。
- 关联两端以及修改前后的项目都可命中历史。
- 按 operation_id 查询总是带快照；不存在时 items=[]。
- undo_of 记录该操作撤销了哪次操作，原历史保持不变。

```sh
python -m layerweave.tool.builtin.usage.history.cli DATABASE --project-id PROJECT_ID --kind object --id OBJECT_ID
python -m layerweave.tool.builtin.usage.history.cli DATABASE --project-id PROJECT_ID --limit 20 --before CURSOR --json
python -m layerweave.tool.builtin.usage.history.cli DATABASE --operation-id OPERATION_ID --json
```

历史中只有整批改动属于同一撤销来源时，顶层 undo_of 才是该操作编号。混合撤销与其他修改时，undo_of 为 None，undo_of_operations 列出涉及来源，各条撤销改动保留自己的 undo_of。

## 撤销与重做

按操作编号撤回整批改动；撤销新的撤销操作即可重做。与其他操作组合时使用 undo_operation_in_session(write, operation_id)，返回业务摘要，外层统一提交；见[组合开发指导](../../../../../docs/build-with-layerweave/04-composing-tools.md)。

同一操作中的工具表与核心记录一起处理。表声明由支撑从数据库读取，显式引用参与恢复依赖判断；结构维护不属于内容撤销。完整的接入与升级行为见[工具表开发指导](../../../../../docs/build-with-layerweave/03-managed-tables.md)。

```python
from layerweave.tool.builtin.usage.undo.service import undo_operation

undone = undo_operation(connection, original_operation_id)
if undone["ok"] and undone["applied"]:
    redone = undo_operation(connection, undone["operation_id"])
```

**输入：**operation_id；可选 config_root 和 checker 与其他写入接口一致。

**返回：**标准操作结果及 undo_of；成功时 data 包含 undone_operation_id、restored_records。使用返回的新 operation_id 重做，不重复撤销原编号。

| 原操作 | 恢复方式 | 冲突比较 |
|---|---|---|
| 创建记录 | 删除该记录 | 整条记录 |
| 删除记录 | 按原编号恢复 | 记录存在性、编号与引用条件 |
| 更新记录 | 恢复该操作最终改变的顶层字段 | 这些字段是否仍等于原操作结束值 |

**边界行为：**

- 一次操作的多次修改按最初/最终状态合并，已抵消的变化不回退后来修改。
- information、axis 各算一个完整字段，不合并其内部键；其他未被原操作改变的字段保留后续值。
- 创建/删除仍按整条记录判断；任一冲突都会阻止整批恢复，没有局部撤销或强制覆盖。
- 缺少恢复所需层/项目、原编号被占用、待删除记录被后来记录引用，都会报告冲突。
- 跨表编号占用仅比较同簇、同计数范围的成员。provided 簇外工具表可以与层、对象使用相同数字；规则见[编号模块](../../../support/numbering/README.md)。
- 冲突时 ok=false、applied=false，error.conflicts 给出目标、字段、预期/当前/拟恢复值或引用阻碍；comparison 为 fields 或 record。
- 恢复原编号、历史坐标、内容、config_ref 和层 type，不按当前轴重新落点。已提交的发号进度不回退。
- 成功撤销作为新操作记入历史。没有最终变化时 unchanged；操作不存在或没有实际日志时为 operation_not_found。
- 恢复后按当前配置检查，诊断 error 不撤销已完成的恢复。Python、TOML 和媒体文件不属于数据库撤销范围。

```sh
python -m layerweave.tool.builtin.usage.undo.cli DATABASE OPERATION_ID
python -m layerweave.tool.builtin.usage.undo.cli DATABASE UNDO_OPERATION_ID --json
```

文字反馈将写入结果和检查问题分开，完整协议见 [CRUD](CRUD.md)。旧数据库在写入前使用[开发工具](../developer/README.md)显式升级；普通读取不自动升级。

完整内存示例：`python examples/review_history.py`。

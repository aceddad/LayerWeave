# 用法五：持续读取变化，按需刷新

视图、索引或其他缓存工具可以先读一次完整内容，再连续读取业务日志，只更新受影响的数据。[返回开发指导](README.md)。本篇使用 0.4.0 新增的支撑接口，不要求安装历史工具，也不改数据库结构。

## 首次读取：内容和游标取同一快照

connection 为已打开的读取连接，project_id 为已有项目编号：

```python
from layerweave.support.api import (
    read_snapshot, read_project_details, change_cursor, read_changes,
)

with read_snapshot(connection):
    initial = read_project_details(connection, project_id)
    cursor = change_cursor(connection)
```

自己的批注、已读状态等工具表也在这个 with 内读取。这样加载期间其他连接提交的修改，或者已反映在 initial 中，或者能从 cursor 后继续读到。不要先结束完整读取，再单独取当前日志末尾，避免把中间发生的修改跳过去。

## 后续读取：处理成功再前移游标

```python
page = read_changes(connection, after=cursor, limit=100)
for change in page["changes"]:
    print(change["action"], change["kind"], change["target_id"])
# 实际工具先把本页应用到自己的缓存，成功后再执行下一句。
cursor = page["next_cursor"]
```

has_more=true 时继续从新游标读取；为 false 时等下一次轮询或通知。每页包含完整操作，limit 是行数软上限。例如一次操作改了 800 条记录，即使 limit=100，也会返回该操作全部日志。界面先应用完本页再渲染，避免展示一半的批次。

缓存直接应用日志时，create/update 的 after_data 是该次变更后的完整记录，delete 的 before_data 指明被删记录。按日志顺序处理，同一个对象在一页中可以出现多次。同一批里创建后又删除也会原样返回，最终状态由调用方依次应用得到。

如果只需要知道“哪些记录需要重读”，可按完整身份去重。但重读得到的可能是比本页更晚的最新状态；这种刷新方式应始终重读，不要再交错应用旧页快照把缓存倒退。视图按自己的状态管理选择一种方式。

## 怎样判断受影响内容

| 变化 | 使用哪些信息 |
|---|---|
| 对象改内容或换层 | before_data/after_data 中的 layer，旧层和新层的数量或排序都可能需要更新 |
| 层改父级 | 修改前后的 father，刷新相关层级结构 |
| 对象或层删除 | before_data 保留原身份与归属 |
| bind 新增、改指向或删除 | 前后快照的 source/target 完整身份，可能影响两个项目 |
| 批注、已读状态等工具表 | kind 与该表声明；scoped 表使用 project_id/id，独立表只使用 id |
| 撤销或重做 | 同样按 create/update/delete 应用，undo_of 仅说明来源 |

接口返回全库日志，调用方再筛选相关内容。推进游标时也要经过不关心的记录；不能把日志的 project_id 当作唯一项目筛选条件，因为 bind 两端可能跨项目。层改父级等变化可能影响没有直接改动的派生显示，刷新范围由视图决定。

这份日志覆盖通过统一写入接口发生的业务变化。单独领号、表结构维护、外部直接 SQL、TOML 或媒体文件变化不在其中。缓存项目 max_id 时按需重读；替换数据库、主动重置或采用日志之外的修改方式后重新读取快照。PRAGMA data_version 可继续作为数据库变化提示，不能代替业务日志内容。

## 与文档同步、关联阅读配合

从文档反复更新内容时，使用 upsert_objects 保留原对象身份；用名字匹配或在 information 保存自己的稳定键。参数与重名处理见[匹配更新](../../src/layerweave/tool/builtin/usage/GUIDE.md#匹配更新或创建)。

要沿批注或对象关联阅读，使用查询包的 walk_relations；它返回标准 bind 的节点、边、步数和原始内容，摘要与排版由视图自己定义。规则见[关联展开](../../src/layerweave/tool/builtin/usage/GUIDE.md#沿关联展开)。

完整可运行示例：[sync_and_refresh.py](../../examples/sync_and_refresh.py)。接口字段以[基础 API](../../src/layerweave/support/API.md#增量读取业务日志)为准。

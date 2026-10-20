# 视图的增量刷新

页面首次读取完整项目和日志游标，之后只接收游标后的变化。协议由视图工具适配现有支撑接口，不增加业务表，也不改变写入方式。底层快照、日志覆盖范围与游标规则见[持续读取指导](../../../../../docs/build-with-layerweave/05-incremental-reading.md)；本篇说明视图自己的 HTTP 格式、缓存和同步流程。

## HTTP 入口

以下路径由正在运行的 view_server 提供，项目编号为示意值。两个入口都只读。

```text
GET /api/project/1/snapshot
GET /api/project/1/delta?after=120
GET /api/project/1/delta?after=120&limit=100
```

首次请求 snapshot；成功应用后，把 next_cursor 作为下一次 delta 的 after。delta 的 limit 默认为 100，HTTP 入口将它限制在 1–1000；这是日志行数的软上限，页尾不会切断一次操作。一批改动超过 limit 时仍整批返回。

### 完整快照

| 字段 | 含义 |
|---|---|
| mode | snapshot |
| data | ProjectData：project、roots、layers、binds、folds、noteReads；项目不存在时为 null |
| next_cursor | 与 data 同一数据库读取快照中的全库日志末尾 |
| has_more | false |

项目详情、关联、折叠、已读状态和游标共用 read_snapshot。其他连接在加载期间提交的业务修改，要么已经出现在 data 中，要么能从 next_cursor 后读到。

原来的 GET /api/project/1 继续返回单独的 ProjectData，缺失项目返回 404；它不带增量游标。snapshot 返回 data=null 时仍是正常协议响应，页面据此清空已删除项目的画面。

### 增量页

```json
{
  "mode": "delta",
  "changes": [
    {
      "kind": "view_note",
      "id": 42,
      "operation_id": "9ab32932b143469e9fc2db153995dafa",
      "change_id": 121,
      "undo_of": null,
      "after": {"用户": 48}
    }
  ],
  "next_cursor": 125,
  "has_more": false
}
```

这份示例表示楼主批注 42 的已读记录变成了“用户读到 48”。121 是这条变化的日志编号；125 是处理完本页全库日志后的游标，后面的几条日志可以与本项目无关。客户端必须采用 next_cursor，不能从筛选后的 changes 重新计算页尾。

changes 保持日志顺序，同一记录可以出现多次。事件共有 kind、id、operation_id、change_id、undo_of、after；id 是目标记录编号，change_id 是日志编号。after 来自该条日志的完整 after_data，经过视图投影后返回，不是另一次查询得到的较晚业务行，也不是字段差异。

| kind | after 与附加字段 |
|---|---|
| object | 与完整读取一致的画面对象：id、name、type、begin、end、tips、text、media、information；另外给出 before_layer、after_layer，创建前或删除后的一端为 null |
| bind | id、tips、source、target；两端均为 kind/project/id。删掉或移出本项目时 after=null |
| project | id、name、tips；项目创建、恢复或删除使用完整快照响应 |
| view_layer | layer、user、user_tips、ai、ai_tips；记录删除或两边都未折叠时 after=null |
| view_note | 已解析的“署名 → 最后读到的批注编号”字典；记录删除或为空时 after=null |

after=null 的事件从对应的视图集合中移除目标。它不一定表示数据库行已删除：例如关联改指到别的项目后，本项目画面不再收录它。恢复与撤销使用同样的事件格式，undo_of 只记录来源，不需要客户端再推导反向操作。

服务端检查 bind 修改前后两份记录的两端，因此从外部项目指向这里、以及从这里移走的关联都会被正确处理。其他工具表目前不会自动变成视图事件；新增视图状态需要明确补投影和客户端处理。

### 什么时候返回 snapshot

delta 入口也可能返回 mode=snapshot，客户端必须同时支持这两种响应：

- 本页包含这个项目的层变化，包括改名、轴、父层、增删等。层名和类型参与轨道合并，所以当前实现统一回退完整读取。
- 本页包含项目创建、恢复或删除。删除时返回 data=null；恢复空项目时也返回完整 data，不依赖层事件触发重新加载。
- after 超过当前库日志末尾，或落在某次操作内部。

回退快照读取当前数据库快照的完整状态，并返回该快照末尾的游标，不停在刚才那页的页尾。普通对象、关联、项目名称/备注、折叠和已读变化使用 delta。

## 前端怎样保持一致

sync.ts 将项目读取排成单条队列；轮询自身也只允许一轮进行中。每次请求带有项目代次和本地写入代次。切走再切回同一项目、或读取期间开始写入，都会使旧请求失效；旧响应不能回写数据或推进游标。

has_more=true 时，后续页先在局部变量中合成，直到追完才一次发布。某一页请求失败，画面和已应用游标都不前移。这样既不会展示半次操作，也不会在追旧日志时短暂覆盖刚确认的乐观状态。

已读、已处理和折叠仍先修改本地画面。当前项目有 pending 写入时不应用远端读取；所有 pending 写入结束后再同步。写入失败时重新取快照恢复实际状态；写入已提交而刷新失败时保留待刷新状态，由后续轮询重试。拖动画板期间同样暂停发布，拖完后继续从原游标读取。

折叠开始时也记录当前项目代次。写入期间切到其他项目再切回来，旧请求可以正常完成数据库写入，但不能把重新加载期间的空排版或后来那次页面的排版当成本次折叠结果保存。

PRAGMA data_version 继续提供在线/变化提示，页面不再用它代替日志游标。共享排版和插件清单使用各自的 serial，分别刷新。排版 serial 由 view_layout/view_layout_member 的最新日志编号及旧文件修订组成，作为不透明字符串比较。布局写入不混入业务 after 事件，而是触发排版专用读取；撤销、复制也通过同一机制更新。

## 缓存的失效范围

对象事件按层合并后只排序一次，保留其他层和未改对象的引用。受影响根重新计算完整范围，删除原来的首尾对象也能正确收缩。Model 依据数据引用判断哪些根发生了变化，再继承不受影响的轨道和画板布局缓存。

| 变化 | 缓存处理 |
|---|---|
| 对象内容、位置、增删或换层 | 旧层、新层所属根失效；其他根可继续复用 |
| 根范围变化 | 包含这个根的整条接续行失效，后续段的 offset 和自动像素比重新计算 |
| 折叠状态变化 | 对应根的轨道/画板布局失效，必要时重新排列下方画板 |
| 关联或已读变化 | 几何输入未变时复用整套几何索引和布局；Model.data 仍指向最新完整数据，供插件读取 |
| 批注层或关联变化 | 重建批注列表、楼和目标索引；普通层变化不强制重建批注 |
| 层结构变化、全量重载 | 使用新快照重新建立模型 |

未改变的对象引用指原始画面对象；发生变化的层需要新的层记录及相应装配对象。缓存不是只看对象编号：层归属、根范围、显示过滤和画板宽度都可能影响布局。

## 数据之外的变化

这个协议同步经过 LayerWeave 统一写入入口记录的业务变化。直接执行 SQL、修改 TOML、替换媒体文件、维护工具表声明或替换整个数据库，不由 changes 完整描述。遇到这些操作应重新加载页面/快照；仅看到 data_version 变化不能推导出缺失的业务事件。

媒体 available 是投影时检查本地文件得到的展示信息；数据库读取快照不能锁定磁盘文件。共享排版已进入数据库事务，但通过自己的 serial 重新读取；旧本机布局仅作迁移回退。需要同步媒体文件或配置更新时，应在视图工具里增加明确的资源失效方式，不把它们伪装成对象更新日志。

## 扩展和验证位置

| 需要修改的部分 | 源码 |
|---|---|
| HTTP 路由和参数 | [server.py](server.py) |
| 项目筛选、快照回退、新工具状态事件 | [incremental.py](incremental.py) |
| 全量与增量共用的展示字段 | [data.py](data.py) 的 object_view/object_views/bind_view |
| 协议类型和请求 | [types.ts](../../../../../frontend/view/src/types.ts)、[api.ts](../../../../../frontend/view/src/api.ts) |
| 事件合成和根范围 | [model/incremental.ts](../../../../../frontend/view/src/model/incremental.ts) |
| 请求代次、pending 写保护、游标提交 | [sync.ts](../../../../../frontend/view/src/sync.ts)、[model/syncGate.ts](../../../../../frontend/view/src/model/syncGate.ts) |
| 模型缓存和批注缓存 | [model/model.ts](../../../../../frontend/view/src/model/model.ts)、[store.ts](../../../../../frontend/view/src/store.ts)、[model/notes.ts](../../../../../frontend/view/src/model/notes.ts) |

新增事件时同时补服务端投影、TypeScript 联合类型、纯合成函数和失效范围。不要先读一页旧日志，再用较晚的业务行替换 after；如果希望采用“日志只通知失效、客户端重读最新值”的方案，需要整体约定这种读取方式，不能与当前日志回放交错使用。

后端回归见 [test_view_incremental.py](../../../../../tests/view/test_view_incremental.py)：双连接快照、完整操作、工具表撤销、跨项目关联移出、HTTP 路由。前端见 [incremental.test.ts](../../../../../frontend/view/src/model/__tests__/incremental.test.ts) 和 [sync.test.ts](../../../../../frontend/view/src/model/__tests__/sync.test.ts)：缓存引用、根范围、接续偏移、乱序请求、失败重试和乐观状态保护。

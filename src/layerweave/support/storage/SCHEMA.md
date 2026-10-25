# 数据表、编号与持久化

本专题维护存储格式与写入约定。[返回存储入口](README.md)。

`schema.sql` 定义四张业务表和一张 changes 日志表；`database.py` 提供打开连接和初始化，support/numbering 提供发号，`crud.py` 提供通用操作，`journal.py` 记录改动；`errors.py` 仅在 SQL 约束失败时解释缺失/被引用的记录。完整模型读写优先见 [公共 API](../API.md)；单条请求和检测协议见 [请求与反馈协议](../../tool/builtin/usage/CRUD.md)。

## 初始化

使用 Python 3.11+ 标准库；发号语句使用 SQLite 3.35+ 的 UPDATE RETURNING。

完成可编辑安装后，在项目根运行：

```sh
python -X utf8 -B -m layerweave.tool.builtin.developer.database.cli output/ai-production.sqlite3
```

会创建父目录、数据库文件和缺失的表，保留已有记录；原来的四表数据库可通过此命令补建 changes。旧版可空的 objects.layer 会在事务中升级为 NOT NULL，保留数据、日志和对象表的索引、触发器。若有 layer=NULL 的旧对象，迁移明确列出其项目和编号并停止；先由调用方选择所属层，再重试，不自动分配归属。每个连接都需要启用外键；`open_database()` 已处理此事。

## 表与映射

| 表 | 用途 |
|---|---|
| projects | id、name、max_id、tips；项目编号独立发放 |
| layers | 以 (project_id, id) 保存层，father 指向同项目的层 |
| objects | 以 (project_id, id) 保存对象，layer 指向同项目的层 |
| binds | 两端各自记录 kind、project_id、id，另存 tips 和全库递增、不复用的独立 id |
| changes | 内部 id、operation_id、UTC 时间、目标种类/项目/编号、动作、前后 JSON 快照；undo_of 记录撤销来源 |

register_tables 可按工具声明创建额外的托管表；首次接入时建立 _layerweave_tables 保存声明，普通初始化仍只有上述五张表。发号词条与簇成员另由按需创建的 _layerweave_numbering 保存。工具表的字段、身份和引用详见[接入说明](../../../../docs/build-with-layerweave/03-managed-tables.md)。现有 kinds 及存储列不因此改变。

_layerweave_tables 的 definition 同时保存 logical_references 和 exchange.on_copy 元信息，补登记不增加业务列或重建业务表。仅 references 生成 SQL 外键、参与引用错误及恢复判断；逻辑引用由交换等工具按需解释，不增加数据库约束。

注销托管首次创建 _layerweave_retired_tables(kind TEXT PRIMARY KEY, definition TEXT NOT NULL, retired_at TEXT NOT NULL)，冻结原声明与 UTC 退出时间；普通读取不建表。活动/退役目录、发号成员在同一事务内更新，物理表不变。历史解释可用退役定义，正常 CRUD/交换只看活动目录；保留的物理外键仍会阻止相关删除，失败时诊断查当前真实外键。接口及依赖规则见[注销托管](../../../../docs/build-with-layerweave/03-managed-tables.md#注销托管)。

工具 BLOB 列存真实字节，Python 返回 bytes；journal 将声明的 BLOB 字段编码为 Base64，快照根结构及 id/project_id 路径不变。读取历史时按活动/退役声明解码，不补后来新增的字段；恢复才对当前活动结构补默认值。普通 JSON 列不能包含字节。历史与对应声明需一起保留，0.7.9b3 及更早 SDK 不支持此编码与注销语义。

- `config_ref` 是两类实体的存储元数据，路径相对于项目的 `src/layerweave/configs/`，例如 `objects/image.toml`。它给读取配置、恢复对应 Python 类提供依据，不添加到基础类中。
- 层的 `type` 保存 TOML 中的类型标识，Python 类不再声明同名字符串。save_layer 自动取得它；dispatch 在省略 type 且提供 config_ref 时也会补齐。低层 crud 不读配置，仍写入调用方提供的原始 type/config_ref，独立检测负责报告矛盾。
- 对象的 begin/end 在 CRUD 写入时按适用轴精度落点，缺少精度用 1e-6；直接 SQL 不经过该过程。更新只归一提交的坐标，换层时两端都按目标层精度归一；其他字段更新不改旧坐标。日志记录实际落点后的值。
- `axis` 和 `information` 使用 JSON 文本；无轴说明使用 SQL NULL，空 information 使用 `{}`。
- 层的 objects 从对象表反查并装载，bind 从关联表反查当前实体发出的关联，不在实体行内再存副本。
- 项目归属和层归属有外键；father 可为 NULL 表示根层，objects.layer 必须非空并指向同项目实际存在的层。没有级联更新或删除。
- bind 两端没有实体外键，可以保存或保留失效引用；kind 的含义为 layer 或 object，独立检测通道统一检查两端。
- 父链无环由支撑在提交前保证；区间先后、轴设置、JSON 内容和封装规则交给可选检测，资源存在性不自动检查。
- 外键由 SQLite 原有约束处理；失败时在回滚前读取失败现场，区分缺项目、缺所属层/父层以及删除仍被引用的实体。不会为成功写入额外查询这些引用，也不把其他 SQL 错误误报为外键问题。

使用 write.defer_references() 时，外键可以延迟到提交才检查。若提交失败，errors.py 在回滚前用 foreign_key_check 列出失败记录：error.violations 包含各项 target、field、reference、message，顶层错误也保留第一项定位。数据、发号和日志仍一起回滚；这只补充失败说明，不改变是否允许写入的规则，也不在成功路径扫描全库。

## 编号身份

项目使用独立编号；同一项目内，层、对象与默认 auto 的 scoped 工具表共用 project_entities 发号词条，不同项目可以有相同的局部编号。这些记录的完整身份是 (project_id, id)，引用还携带 kind 区分种类；text/image 等封装 type 与 kind 分开。项目、bind 与未加入发号词条的 auto 独立工具表分别使用各表的自增编号，不占 projects.max_id。provided 工具表由调用方提供 ID，默认不属于任何簇；自定义簇的成员和计数位置见[发号说明](../numbering/README.md)。

## 发号与写入

同一项目的层和对象在创建时通过默认词条申请编号。开发接口为 `allocate("project_entities", data={"project_id": project_id})`，隐式使用当前写会话，只更新 max_id，不提交事务、不创建业务记录。发号和保存实体放在同一个事务里：

```python
from contextlib import closing
from layerweave.support.api import initialize_database, open_database, transaction

path = initialize_database("scratch/example.sqlite3")
with closing(open_database(path)) as connection:
    with transaction(connection) as write:
        project = write.create("project", {"name": "示例"})
        layer = write.create("layer", {"type": "text", "config_ref": "layers/text.toml"}, project_id=project["id"])
    print(write.operation_id, layer["id"])
```

已提交的编号不因删除实体而回退；整个事务回滚时，本次发号也回滚。实体编号在写入事务提交后才作为持久化身份使用。

关联经统一 CRUD 入口创建，binds.id 由 SQLite AUTOINCREMENT 保持全库递增，不占 projects.max_id。initialize_database 还会升级旧关联表并补上 changes.undo_of；关联发号起点同时参考现存行和已删除记录的历史最大编号，保留旧数据及索引。普通打开连接不会自动迁移；旧库写入前运行初始化命令，详见 [历史与恢复](../../tool/builtin/usage/HISTORY.md)。

各托管表的主键防止同表重号，同簇、同范围的跨表编号由发号及提交前检查保证；未入簇的自定义 ID 不参与跨表占用比较。直接 SQL 会绕过日志与结构保证，不属于工具的受支持记录写入接口。工具声明通过 register_tables 交给支撑维护；建表脚本没有额外触发器。

CDUR 请求由 records 包的 dispatch 翻译，最终通过支撑写会话执行。开发其他工具直接使用 transaction/run_operation，无需依赖 CDUR 包；记录原语只在统一写会话内工作。

## 声明读取与缓存范围

`_metadata.py` 仅在同一次写事务或 read_snapshot 内按连接复用表声明、退役声明及发号词条。同连接的嵌套读取共用这一份声明，不同连接隔离；最外层退出、失败回滚后丢弃，下次操作重新读取。不使用跨事务的全局缓存、后台刷新或额外数据库表。

登记、追加列、注销及持久化发号规则会刷新当前范围的元信息。正常记录写入不使声明缓存失效；projects.max_id、业务记录、同簇实际占用始终从当前事务读取，不能缓存或按旧值回填。SQLite 快照本来可见的声明保持一致，其他连接提交的新声明在后续读取快照中生效。

table_specs、retired_tables、numbering_entries 的公开返回仍是独立副本；内部只读消费者借用缓存，外部发号规则也得到独立词条。无需调用方增加参数或维护刷新动作。直接 read_record 也覆盖一次读取快照，在批量还原日志时复用声明；调用方已有事务时不会替其提交。

## 改动日志

- 实际发生的 create、update、delete 各记录目标行的前后快照；read、空修改、无变化及目标不存在的操作不记日志。
- 什么算改动，以实际存储的前后值为准，具体比较规则见下节。
- 业务写入与日志同事务提交；数据或日志写入失败时，由事务调用方一起回滚。
- operation_id 由支撑的统一入口生成 UUID，同一批操作共用，不占 projects.max_id；工具不自行生成 operation_id 或构造日志。
- 日志没有实体外键，目标被删除后仍能查看历史。日志本身通过 read(kind="change") 查询。
- 检测在提交后运行，不改变日志或业务操作的提交状态。显式撤销由 undo_operation 提供，新操作保留 undo_of；不自动撤回有诊断的写入。失败操作的持久化诊断日志尚未实现。

历史查询通过 read_history 按操作分组、分页并展示字段差异；撤销使用日志恢复原编号和实际存储值，不重新取整坐标，也不回退发号上界。更新只恢复原操作净改变的顶层字段，information/axis 各为整体；创建、删除继续按整条记录判断。比较和恢复同事务，任意失败整批回滚。完整说明见 [复查、历史与撤销](../../tool/builtin/usage/HISTORY.md)。

src/layerweave/tool/builtin/usage/editing/tree_service.py 提供子树删除与整层复制，复用既有范围读取、CRUD 和 run_operation；新编号取实际创建结果。删除范围包含树内实体发出的关联，外部入向关联保留；复制仅重映射明确的结构引用。两者都记录为一个可撤销操作，详见 [子树工具](../../tool/builtin/usage/SUBTREES.md)。

跨项目复制/剪切在同模块中复用上述内部步骤；目标项目重新发号并在根部落位，原 begin/end 数值精确保留。剪切还把外部入向关联的目标改为新身份，和源删除、目标创建一起记录。对象分割与插空档的共同计算和写入在 src/layerweave/tool/builtin/usage/editing/timeline.py，普通平移由编辑包内 _plan 执行。详见 [编辑工具](../../tool/builtin/usage/EDITING.md)。

## 什么算改动

普通 SQL 列和 JSON 内容按各自的存储语义比较：

| 内容 | 比较方式与例子 |
|---|---|
| 普通 SQL 列 | 接受数据库类型规范化；数值列的 0 和 0.0 相等，不算变化 |
| JSON 内容 | 保留实际类型，1、1.0、true 互相变更会记日志；嵌套字典/列表同样处理，字典键顺序不算变化 |

SQL 数值列存的是坐标等数值，JSON 则是调用方的原始内容；将两者统一成严格类型比较，会把 SQL 的正常类型转换误判成修改。日志和检测范围均依据实际前后记录，保留 JSON 的类型变化。

UPDATE 前会排除已经能判定无变化的字段；最终是否记日志，还要看数据库实际存下的结果。例如已有 name="1" 时传入 name=1，可能执行一次 UPDATE，SQLite 的 TEXT 类型仍将其保存为 "1"，因此结果为 unchanged、不产生改动日志。unchanged 不承诺“从未执行过 SQL 写语句”。

## 范围与验证

目前已实现表结构、初始化与所属层迁移、发号、记录 CRUD、事务日志、分流、配置加载、模块化检测和完整读写。assembly.py 组合层/对象及关联的记录字典；models.py 按配置还原派生实例；save.py 原子保存模型或记录字典。三者经 layerweave.support.api 对外提供稳定入口，底层 CRUD 仍返回单表记录。

完成安装后，在项目根运行存储检查：

```sh
python -X utf8 -B -m unittest discover -s tests -t . -v
```

检查使用内存数据库；CLI 检查另外创建并清理专用临时数据库，不写入用户的项目数据。

父链成环在支撑提交前拒绝，按本批修改的父关系最终状态判断；原始查询仍可读取旧库问题。实际 SQL 写入只在支撑中发生，日志与实体一起回滚。

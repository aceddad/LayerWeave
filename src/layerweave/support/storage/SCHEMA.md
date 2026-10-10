# 数据表、编号与持久化

本专题维护存储格式与写入约定。[返回存储入口](README.md)。

`schema.sql` 定义四张业务表和一张 changes 日志表；`database.py` 提供打开连接、初始化和项目内发号，`crud.py` 提供通用操作，`journal.py` 记录改动；`errors.py` 仅在 SQL 约束失败时解释缺失/被引用的记录。完整模型读写优先见 [公共 API](../API.md)；单条请求和检测协议见 [请求与反馈协议](../../tool/builtin/usage/CRUD.md)。

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

- `config_ref` 是两类实体的存储元数据，路径相对于项目的 `src/layerweave/configs/`，例如 `objects/image.toml`。它给读取配置、恢复对应 Python 类提供依据，不添加到基础类中。
- 层的 `type` 保存 TOML 中的类型标识，Python 类不再声明同名字符串。save_layer 自动取得它；dispatch 在省略 type 且提供 config_ref 时也会补齐。低层 crud 不读配置，仍写入调用方提供的原始 type/config_ref，独立检测负责报告矛盾。
- 对象的 begin/end 在 CRUD 写入时按适用轴精度落点，缺少精度用 1e-6；直接 SQL 不经过该过程。更新只归一提交的坐标，换层时两端都按目标层精度归一；其他字段更新不改旧坐标。日志记录实际落点后的值。
- `axis` 和 `information` 使用 JSON 文本；无轴说明使用 SQL NULL，空 information 使用 `{}`。
- 层的 objects 从对象表反查并装载，bind 从关联表反查当前实体发出的关联，不在实体行内再存副本。
- 项目归属和层归属有外键；father 可为 NULL 表示根层，objects.layer 必须非空并指向同项目实际存在的层。没有级联更新或删除。
- bind 两端没有实体外键，可以保存或保留失效引用；kind 的含义为 layer 或 object，独立检测通道统一检查两端。
- 父链无环由支撑在提交前保证；区间先后、轴设置、JSON 内容和封装规则交给可选检测，资源存在性不自动检查。
- 外键由 SQLite 原有约束处理；失败时在回滚前读取失败现场，区分缺项目、缺所属层/父层以及删除仍被引用的实体。不会为成功写入额外查询这些引用，也不把其他 SQL 错误误报为外键问题。

## 编号身份

项目使用独立编号；同一项目内，层与对象共用发号器，不同项目可以有相同的局部编号。层/对象的完整身份是 (project_id, id)，引用还携带 kind 区分实体种类；text/image 等封装 type 与 kind 分开。项目编号和全库独立的 bind 编号均不占 projects.max_id。

## 发号与写入

同一项目的层和对象都通过 `allocate_id()` 申请编号，它只更新 max_id，不提交事务。发号和保存实体放在同一个事务里：

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

两个实体表的主键各自防止同表重号，跨表共享编号由统一发号和恢复入口保证。直接 SQL 会绕过日志与结构保证，不属于工具的受支持写入接口。建表脚本没有额外触发器。

CDUR 请求由 records 包的 dispatch 翻译，最终通过支撑写会话执行。开发其他工具直接使用 transaction/run_operation，无需依赖 CDUR 包；记录原语只在统一写会话内工作。

## 改动日志

- 实际发生的 create、update、delete 各记录目标行的前后快照；read、空修改、无变化及目标不存在的操作不记日志。
- JSON 值比较保留布尔、整数、浮点数的类型区别，覆盖嵌套字典和列表；字典键顺序不计为变化。同一比较方式用于日志和检测范围，避免已经改变数据却漏记日志、漏检。
- UPDATE 前排除未变化字段；普通 SQL 数值列接受等值 int/float 的存储规范化。没有变化时不执行写语句。
- 业务写入与日志同事务提交；数据或日志写入失败时，由事务调用方一起回滚。
- operation_id 由支撑的统一入口生成 UUID，同一批操作共用，不占 projects.max_id；工具不自行发号或构造日志。
- 日志没有实体外键，目标被删除后仍能查看历史。日志本身通过 read(kind="change") 查询。
- 检测在提交后运行，不改变日志或业务操作的提交状态。显式撤销由 undo_operation 提供，新操作保留 undo_of；不自动撤回有诊断的写入。失败操作的持久化诊断日志尚未实现。

历史查询通过 read_history 按操作分组、分页并展示字段差异；撤销使用日志恢复原编号和实际存储值，不重新取整坐标，也不回退发号上界。更新只恢复原操作净改变的顶层字段，information/axis 各为整体；创建、删除继续按整条记录判断。比较和恢复同事务，任意失败整批回滚。完整说明见 [复查、历史与撤销](../../tool/builtin/usage/HISTORY.md)。

src/layerweave/tool/builtin/usage/editing/tree_service.py 提供子树删除与整层复制，复用既有范围读取、CRUD 和 run_operation；新编号取实际创建结果。删除范围包含树内实体发出的关联，外部入向关联保留；复制仅重映射明确的结构引用。两者都记录为一个可撤销操作，详见 [子树工具](../../tool/builtin/usage/SUBTREES.md)。

跨项目复制/剪切在同模块中复用上述内部步骤；目标项目重新发号并在根部落位，原 begin/end 数值精确保留。剪切还把外部入向关联的目标改为新身份，和源删除、目标创建一起记录。对象分割与插空档的共同计算和写入在 src/layerweave/tool/builtin/usage/editing/timeline.py，普通平移由编辑包内 _plan 执行。详见 [编辑工具](../../tool/builtin/usage/EDITING.md)。

## 范围与验证

目前已实现表结构、初始化与所属层迁移、发号、记录 CRUD、事务日志、分流、配置加载、模块化检测和完整读写。assembly.py 组合层/对象及关联的记录字典；layerweave.models.py 按配置还原派生实例；save.py 原子保存模型或记录字典。三者经 layerweave.support.api 对外提供稳定入口，底层 CRUD 仍返回单表记录。

完成安装后，在项目根运行存储检查：

```sh
python -X utf8 -B -m unittest discover -s tests -v
```

检查使用内存数据库；CLI 检查另外创建并清理专用临时数据库，不写入用户的项目数据。

父链成环在支撑提交前拒绝，按本批修改的父关系最终状态判断；原始查询仍可读取旧库问题。实际 SQL 写入只在支撑中发生，日志与实体一起回滚。

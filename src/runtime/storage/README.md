# SQLite 存储

`schema.sql` 定义四张业务表和一张 changes 日志表；`database.py` 提供打开连接、初始化和项目内发号，`crud.py` 提供通用操作，`journal.py` 记录改动。完整模型读写优先见 [公共 API](../API.md)；单条请求和检测协议见 [运行接口说明](../README.md)。

## 初始化

使用 Python 3.11+ 标准库；发号语句使用 SQLite 3.35+ 的 UPDATE RETURNING。

在项目的 `src/` 下运行：

```sh
python -X utf8 -B -m runtime.storage.database ../output/ai-production.sqlite3
```

会创建父目录、数据库文件和缺失的表，保留已有记录；原来的四表数据库可通过此命令补建 changes。旧版可空的 objects.layer 会在事务中升级为 NOT NULL，保留数据、日志和对象表的索引、触发器。若有 layer=NULL 的旧对象，迁移明确列出其项目和编号并停止；先由调用方选择所属层，再重试，不自动分配归属。每个连接都需要启用外键；`open_database()` 已处理此事。

## 表与映射

| 表 | 用途 |
|---|---|
| projects | id、name、max_id、tips；项目编号独立发放 |
| layers | 以 (project_id, id) 保存层，father 指向同项目的层 |
| objects | 以 (project_id, id) 保存对象，layer 指向同项目的层 |
| binds | 两端各自记录 kind、project_id、id，另存 tips 和独立的内部行号 |
| changes | 内部 id、operation_id、UTC 时间、目标种类/项目/编号、动作和修改前后的 JSON 快照 |

- `config_ref` 是两类实体的存储元数据，路径相对于项目的 `configs/`，例如 `objects/image.toml`。它给读取配置、恢复对应 Python 类提供依据，不添加到基础类中。
- 层的 `type` 保存 TOML 中的类型标识，Python 类不再声明同名字符串。save_layer 自动取得它；dispatch 在省略 type 且提供 config_ref 时也会补齐。低层 crud 不读配置，仍写入调用方提供的原始 type/config_ref，独立检测负责报告矛盾。
- `axis` 和 `information` 使用 JSON 文本；无轴说明使用 SQL NULL，空 information 使用 `{}`。
- 层的 objects 从对象表反查并装载，bind 从关联表反查当前实体发出的关联，不在实体行内再存副本。
- 项目归属和层归属有外键；father 可为 NULL 表示根层，objects.layer 必须非空并指向同项目实际存在的层。没有级联更新或删除。
- bind 两端没有实体外键，可以保存或保留失效引用；kind 的含义为 layer 或 object，独立检测通道统一检查两端。
- 不检查区间先后、环、轴设置、JSON 内容、资源存在性和封装规则。

## 发号与写入

同一项目的层和对象都通过 `allocate_id()` 申请编号，它只更新 max_id，不提交事务。发号和保存实体放在同一个事务里：

```python
from contextlib import closing
from uuid import uuid4
from runtime.storage import crud
from runtime.storage.database import open_database

with closing(open_database("../output/ai-production.sqlite3")) as connection:
    operation_id = uuid4().hex
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        project, _ = crud.create(
            connection, "project", {"name": "示例项目"}, operation_id=operation_id,
        )
        layer, _ = crud.create(
            connection, "layer",
            {"name": "主线", "type": "text", "config_ref": "layers/text.toml"},
            project_id=project["id"], operation_id=operation_id,
        )
```

已提交的编号不因删除实体而回退；整个事务回滚时，本次发号也回滚。实体编号在写入事务提交后才作为持久化身份使用。

两个实体表的主键各自防止同表重号，跨表共享编号由统一发号方法保证。直接 SQL 会绕过 CRUD 日志；若使用自定编号，还需写入方保持跨表不重号并相应更新 max_id。建表脚本没有额外触发器。

通用调用优先使用 dispatch，它会统一生成 operation_id、开启事务和返回反馈。低层 CRUD 供需要动态组合操作的 Python 调用方使用，不自行提交。

## 改动日志

- 实际发生的 create、update、delete 各记录目标行的前后快照；read、空修改、无变化及目标不存在的操作不记日志。
- JSON 值比较保留布尔、整数、浮点数的类型区别，覆盖嵌套字典和列表；字典键顺序不计为变化。同一比较方式用于日志和检测范围，避免已经改变数据却漏记日志、漏检。
- UPDATE 前排除未变化字段；普通 SQL 数值列接受等值 int/float 的存储规范化。没有变化时不执行写语句。
- 业务写入与日志同事务提交；数据或日志写入失败时，由事务调用方一起回滚。
- operation_id 由分流入口生成 UUID，同一批操作共用，不占 projects.max_id。低层组合操作由其调用方生成一次并传入。
- 日志没有实体外键，目标被删除后仍能查看历史。日志本身通过 read(kind="change") 查询。
- 检测在提交后运行，不改变日志或业务操作的提交状态。自动撤销和失败操作的持久化诊断日志尚未实现。

## 范围与验证

目前已实现表结构、初始化与所属层迁移、发号、记录 CRUD、事务日志、分流、配置加载、模块化检测和完整读写。assembly.py 组合层/对象及关联的记录字典；models.py 按配置还原派生实例；save.py 原子保存模型或记录字典。三者经 runtime.api 对外提供稳定入口，底层 CRUD 仍返回单表记录。

在项目的 `src/` 下运行存储检查：

```sh
python -X utf8 -B -m unittest discover -s ../tests -v
```

检查使用内存数据库；CLI 检查另外创建并清理专用临时数据库，不写入用户的项目数据。

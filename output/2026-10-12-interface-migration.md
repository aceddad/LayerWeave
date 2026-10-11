# LayerWeave 0.3.0 接口调整与迁移报告

日期：2026-10-12。对照基线：main 的 `2e97205`。本文供 Claude 接入视图或其他工具时核对调用变化。

本轮让现有项目内容工具可以共用一次事务，区分两种保存入口，并修正领号反馈和 help。数据库结构、config_ref、层/对象约定、自定义 ID 与簇规则没有变更；已有数据库不需要因本轮调整而迁移。

## 1. 接入方需要改什么

| 当前用法 | 迁移方式 |
|---|---|
| 从 `layerweave.support.api` 导入 `save_layer/save_object` | 保持原样，仍默认不检测 |
| 从 `layerweave.tool.builtin.usage.records.save` 导入 `save_layer/save_object` | 改为 `save_layer_with_checks/save_object_with_checks`；旧工具层名称已移除 |
| 单独调用 append、shift、split、gap、copy、transfer、dispatch、undo | 原独立入口与调用参数保留 |
| 在 `transaction` 或 `run_operation` 内调用上述独立入口 | 改用对应 `*_in_session(write, ...)`，交由外层提交 |
| 用 `operation.changes` 是否为空判断整次操作是否写入 | 使用 `applied` 或 `operation.status`；只领号也可能已提交 |
| 假定历史里每个操作只可能撤销一个来源 | 普通撤销保持原样；混合操作还要读取逐条 `undo_of` 和 `undo_of_operations` |

工具层保存的导入修改如下，其他参数保持原样：

```python
# 旧
from layerweave.tool.builtin.usage.records.save import save_layer, save_object

# 新
from layerweave.tool.builtin.usage.records.save import (
    save_layer_with_checks,
    save_object_with_checks,
)
```

这里的 with_checks 表示接入默认检测提供者；没有安装检测包时仍返回明确的 not_run。内容检测在提交后执行，检查中的 error 不表示写入失败。

## 2. 多个工具共用一次事务

新增 16 个 Python 事务内函数。它们使用现有业务实现，不另写一套编辑算法。第一参数统一为当前写会话 `write`，返回业务数据，失败抛出异常；不自行提交、不自行调用检测器。

下表模块前缀均为 `layerweave.`：

| 模块 | 新函数 |
|---|---|
| `tool.builtin.usage.editing.objects` | `append_object_in_session`、`copy_object_in_session` |
| `tool.builtin.usage.editing.positions` | `arrange_objects_in_session`、`align_objects_in_session`、`set_duration_in_session` |
| `tool.builtin.usage.editing.timeline` | `shift_objects_in_session`、`split_object_in_session`、`insert_gap_in_session` |
| `tool.builtin.usage.editing.tree_service` | `delete_subtree_in_session`、`copy_subtree_in_session`、`transfer_subtree_in_session`、`transfer_objects_in_session` |
| `tool.builtin.usage.records.dispatch` | `dispatch_in_session` |
| `tool.builtin.usage.undo.service` | `undo_operation_in_session` |
| `support.api` | `save_layer_in_session`、`save_object_in_session` |

组合示例，connection 为已初始化连接，项目和层编号来自实际记录：

```python
from layerweave.support.api import run_operation
from layerweave.support.providers import optional_checker
from layerweave.tool.builtin.usage.editing.objects import append_object_in_session
from layerweave.tool.builtin.usage.editing.timeline import shift_objects_in_session

def work(write):
    obj = append_object_in_session(
        write, project_id, layer_id,
        {"config_ref": "objects/text.toml", "information": {"text": "新字幕"}},
        duration=2,
    )
    return shift_objects_in_session(write, project_id, [obj["id"]], offset=1)

result = run_operation(connection, work, checker=optional_checker())
```

这两个步骤共用一个 operation_id；后一步抛错会回滚本批数据、编号和日志。成功提交后只检测一次。省略 checker 时沿用基础支撑默认，不进行内容检测。

需要注意的返回差异：

- `*_in_session` 返回数据，不带独立的 ok/operation/checks 外壳；最终外壳由外层 run_operation 给出。
- `dispatch_in_session` 对单条请求返回数据，对批次返回按请求顺序排列的数据列表。
- `save_*_in_session` 返回完整层/对象字典，**不回填传入实例或字典的 id/layer/bind**。后续步骤使用返回记录，提交后可重新 load；避免外层失败后输入实例残留已回滚的编号。独立 save 仍在成功提交后回填。
- 事务内函数不接受 checker。编辑接口中仅供检测使用的 config_root 也交由最外层配置；实际需要解析配置的 dispatch/save 保留 config_root。
- 不要在外层吞掉异常后假装整批成功；如果自行捕获异常继续执行，就由调用方决定接受哪些修改。支撑不会把任意业务字典中的 `ok=false` 猜成执行失败。

已有 LayerWeave 会话中，针对同一连接误用独立操作入口，现在直接抛 ValueError，提示使用事务内入口。此前内层失败可能作为普通字典交回外层，导致前面的修改仍被提交。普通独立调用仍使用原有失败反馈；调用方手动开启的待提交 SQLite 事务也不会被接管。

这些函数针对项目内容操作。数据库初始化、表结构登记、KEY/文件工具和版本扫描保留各自开发入口。本轮没有增加通用插件执行框架。

完整返回说明见[事务内组合](../docs/build-with-layerweave/04-composing-tools.md)，可运行示例见[composition.py](../examples/composition.py)。

## 3. 单独领号也明确显示已经提交

以前 run_operation 中只调用 allocate，计数已推进，但反馈可能是 applied=false / unchanged。现在成功领号会得到：

```text
ok: true
applied: true
operation.status: committed
operation.changes: []
operation.numbering: [本次计数推进的信息]
```

numbering 每项记录 counter、before、after；通过 allocate 调度时还附 entry、rule、identity。直接 increment 的反馈可能没有这些调度字段。普通自动创建也会附相应领号信息，只有非空时才增加 operation.numbering。

自定义发号规则的函数签名仍为 function(entry, data)。allocate 传入的 entry 副本额外带 name（当前词条名），用于反馈；持久化登记格式没有改变。

numbering 是本次返回的计数说明，不增加数据库业务 changes 行。只领号没有可撤销的业务记录；已提交编号不回收。整批失败不会返回已回滚的领号信息。write.numbering 可读取当前事务内的副本，但外层提交前仍是临时结果。

详细协议见[基础 API](../src/layerweave/support/API.md)及[编号模块](../src/layerweave/support/numbering/README.md)。

## 4. 组合撤销的历史表达

新增入口允许“一次撤销 + 普通修改”，也允许在同一事务内撤销多次操作，因此历史不能只取第一条日志的 undo_of 当作整批来源。

- 每条撤销改动携带自己的 undo_of。
- 整批改动都来自同一次撤销时，顶层 undo_of 仍是该来源编号。
- 混合来源时，顶层 undo_of 为 None，新增 undo_of_operations 列出撤销来源；文字反馈也逐条标明。
- 字段冲突检查、原编号恢复、计数不回退的规则保持原样；组合操作本身仍可整体撤销。

## 5. help 与开发导引

- command_help 的 14 个相关命令详情新增 session_entrypoint，指向对应 Python 组合入口。它们没有成为额外 CLI 命令，命令总数仍为 28。
- source_root 说明修正为默认扫描包内 tool/builtin；传入其他目录是替换扫描范围。
- initialize_database 的 Python 参数正确显示为 path，并注明它对应 CLI 的 database 位置参数；实际函数和 CLI 参数没有改名。
- 配置 help 生成的保存示例继续使用基础 support.api，保证帮助包可以独立使用；文档明确默认不检测，以及如何改用 with_checks。
- 新增组合开发指导，同步 AGENTS、基础 API、工具手册、README、示例与文档索引。

## 6. 组件版本

| 组件 | 本轮版本 |
|---|---|
| LayerWeave foundation / 安装包 | 0.3.0 |
| records、editing、history | 0.2.0 |
| undo | 0.3.0 |
| help、database | 0.1.1 |

版本写在各组件 component.toml。版本登记库要执行 sync 才会反映新声明；本轮没有操作已有 output 用户数据库、KEY 配置或外置 skills。

## 7. 验证结果

| 验证 | 结果 |
|---|---|
| 全量 unittest | 运行 505 项，504 项通过，1 项因当前 Windows 环境不允许创建测试目录符号链接而跳过；无失败 |
| 新增事务组合回归 | 21 项通过，涵盖一次提交、失败回滚、嵌套误用、保存回填、领号反馈、组合撤销和检测异常 |
| 隔离验收（包含于全量测试） | 核心独立运行、无工具的支撑读写、12 个工具包逐个单独安装使用均通过；records/editing/undo 的新事务内入口也在隔离环境执行 |
| 普通 wheel 安装 | 临时安装后验证通过；只占 layerweave 顶层包，97 份资源与源码一致，发现 28 个命令；新组合入口和领号反馈实际执行通过 |
| 示例 | composition.py、read_write.py、title.py 实际运行通过 |
| 文档 | 检查 64 份 Markdown 中的 426 个本地链接及章节跳转，通过 |
| Git 差异 | diff --check 通过 |

复现主要测试，在源码根使用已安装本项目的 Python：

```sh
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B examples/composition.py
python -m pip wheel --no-deps --wheel-dir scratch/interface-dist .
python -X utf8 -B tests/check_wheel.py scratch/interface-dist/layerweave-0.3.0-py3-none-any.whl
```

推荐 Claude 侧核对自己的保存函数导入，以及“一个视图动作调用多个编辑工具”的事务边界。已有数据库、Python 类和 TOML 无需为本轮变化重写。

# LayerWeave 插空档 命令帮助与字段撤销修复报告

日期：2026-10-10。对照基线：`a35f175`。供 Claude 复测本轮反馈使用。

本轮已完成插空档的显式范围与 split/keep 处理、命令行就地帮助、统一命令查询接口，以及按顶层字段撤销。全量 316 项测试通过，测试使用内存或临时数据库。没有新增业务表、基础类字段或跨界规则配置文件。

## 插空档范围与跨界处理

原来的 `layer_id` 已经只处理直属对象，`layer_ids` 会包含子孙层。本轮取消了省略范围时默认操作整个项目的行为；调用者必须明确选择一个范围。

| Python 参数 | CLI 参数 | 实际范围 |
|---|---|---|
| `layer_id=4` | `--layer-id 4` | 层 4 的直属对象 |
| `layer_ids=[4,7]` | `--layer-ids 4 7` | 两棵子树，包含全部后代并去重 |
| `whole_project=True` | `--project` | 整个指定项目 |

省略或混用范围会失败，本批不写入。显式空子树列表仍表示空选择，不扩展为全项目。

跨界对象仅支持两种调用时选择：

| action | 行为 |
|---|---|
| `split` | 提供两份完整 information；分割并移动后段，第一段保留编号和现有关联 |
| `keep` | 保留原区间、内容、编号及关联，不需要复制内容 |

没有实现 `stretch`，也不根据对象类型、长度或用途自动选择策略。这是本次调用的参数，不是新增 TOML 配置层。

对反馈中的例子，在 10 处插入长度 2：

| 对象 | 显式选择 | 预期结果 |
|---|---|---|
| 段落说明 `[0,30)` | keep | 仍为 `[0,30)`，内容不变 |
| 歌词 `[8,12)` | split | `[8,10)` 与 `[12,14)`，采用调用者提供的两段内容 |
| 背景原画 `[5,15)` | keep | 仍为 `[5,15)`，资源引用不变 |

如果只指定歌词层的 `layer_id`，另外两层甚至不进入本次选择，不需要为它们传 keep。如果指定包含三层的子树，才需要逐个给出跨界处理。

调用格式如下，编号需替换为真实对象编号：

```python
from runtime.api import insert_gap

result = insert_gap(connection, project_id, at=10, length=2,
    layer_ids=[root_layer_id],
    crossing_actions=[
        {"object_id": paragraph_id, "action": "keep"},
        {"object_id": lyric_id, "action": "split",
         "first_information": {"text": "前半句"},
         "second_information": {"text": "后半句"}},
        {"object_id": background_id, "action": "keep"},
    ])
```

返回中的 `data.scope` 表示实际范围，`splits`、`kept`、`shifted` 分别说明发生了什么。`data.gaps` 保留为插入位置与长度信息，文字改称“插入时段”；keep 对象可以覆盖它，工具不再宣称这段时间没有任何对象。

缺少处理时，`error.required_crossings` 列出对象、所属层、原区间和实际切点，`allowed` 为 split/keep。范围外或不再跨界的处理项列入 `unused_object_ids`。这些失败均不产生部分写入。

兼容方式：旧 `split_contents` 参数仍可用，旧内容文件明确给出 `first_information` 和 `second_information` 但没有 action 时仍表示 split；不能同时传新旧参数。`required_splits` 暂保留为 `required_crossings` 的同值兼容别名。旧调用若依赖默认全项目，必须补 `whole_project=True` 或 CLI 的 `--project`。

## 命令帮助与统一查询

`split --help` 现在解释 object_id、JSON 文件最外层结构及完整示例；`gaps --help` 解释 at、length、范围和 split/keep 内容文件。所有现有命令模块的根级 --help 都复用工具声明中的示例。

split 文件最外层是对象。下例假设原区间为 `[10,20)`，实际调用时切点必须位于真实对象区间内部：

```json
{"first_information":{"text":"前段"},"cuts":[{"at":14,"information":{"text":"后段"}}]}
```

gaps 文件最外层是列表：

```json
[{"object_id":8,"action":"split","first_information":{"text":"前段"},"second_information":{"text":"后段"}},{"object_id":9,"action":"keep"}]
```

新增查询接口：

```python
from runtime.api import command_help

overview = command_help()
details = command_help(["split", "insert_gap", "undo"])
```

当前目录含 23 个命令，覆盖内部工具、基础 CRUD 分流和数据库初始化。总览给出名称、用途、读写性质与 CLI 模块入口；详情提供参数、返回、完整示例、Python entrypoint 和声明位置。

各工具在自己的 Python 模块中声明字面量 `COMMANDS`。目录静态读取，不导入被发现的模块、不连接数据库、不执行命令；新增声明会在下次查询出现，无需修改中央名单。名称、别名和完整 entrypoint 可查询，重复选择去重；损坏声明或名称歧义逐项报告，其他条目继续。

当前 tools/README 已有工具入口，本轮进一步加入统一命令目录入口及扩充说明。未来 MCP 可以复用这些描述数据；本轮没有新增 MCP 服务或按字符串执行任意函数的入口。

## 按顶层字段撤销

普通更新以同一操作合并后的最初与最终状态计算净改变的顶层字段，只比较并恢复这些字段。

例如先将 end 从 12 改为 14，后来只修改 information：撤销前一次操作会把 end 恢复为 12，保留新的 information。SQL UPDATE 也只写 end，不会因整行赋相同值触发 information 列的更新。

| 情况 | 结果 |
|---|---|
| 后续修改其他顶层字段 | 保留后续值，允许撤销 |
| 后续修改原操作改变的同一字段 | 报冲突，整批不写 |
| information 内不同键分别被两次操作修改 | information 仍算同一字段，报冲突，不合并内部键 |
| axis 内不同键发生变化 | axis 同样作为一个整体字段 |
| 撤销创建或删除 | 仍要求整条记录的存在性与内容匹配 |
| 一个批次中仅一条记录冲突 | 整个批次不写，不做部分撤销 |

冲突返回 `comparison=fields` 或 `record`，`fields` 只定位顶层字段；保留预期、当前和拟恢复记录供检查。原操作中已相互抵消的字段变化不再回退后来对它的修改。

撤销和重做继续产生新操作记录，仍使用现有外键、引用与提交后语义检查。原编号、实际历史位置和发号上界规则保持。字段级恢复不猜测未知的业务依赖关系。

跨项目剪切也已覆盖：如果后来只修改了被改指关联的 tips，撤销剪切会恢复原目标地址并保留新的 tips；如果后来修改的是这次剪切改过的目标字段，则整批冲突。

## 复测步骤

从项目的 src 目录执行：

```sh
python -X utf8 -B -m unittest discover -s ../tests -p test_review_fixes.py -v
python -X utf8 -B -m unittest discover -s ../tests -p test_command_help.py -v
python -X utf8 -B -m unittest discover -s ../tests -p test_transfer_tools.py -v
python -X utf8 -B -m unittest discover -s ../tests -q
```

本轮全量结果：`Ran 316 tests ... OK`。其中新增 24 项测试，覆盖范围隔离、split/keep、帮助示例、命令发现、顶层字段冲突和跨项目引用备注保留。旧测试中依赖全项目默认范围的调用已显式补范围；原来用“不同字段变化”制造冲突的用例改为同字段冲突，并新增了不同字段应成功的用例。

可直接检查帮助输出，无需数据库：

```sh
python -X utf8 -B -m tools.common.command_help --json
python -X utf8 -B -m tools.common.command_help split insert_gap undo --json
python -X utf8 -B -m tools.common.split --help
python -X utf8 -B -m tools.common.gaps --help
```

建议重点复测原来的三种跨界对象，并分别使用直属歌词层、包含三层的子树和显式全项目范围。之后复测 end 与 information 的交错修改、information 内部不同键的修改，以及撤销剪切时外部关联的后续备注。

## 实现与说明位置

- [范围与跨界处理](../src/runtime/storage/timeline.py)
- [顶层字段撤销](../src/runtime/storage/undo.py)
- [命令目录读取](../src/tools/catalog.py)
- [命令目录接口和开发说明](../src/tools/COMMANDS.md)
- [编辑工具说明](../src/runtime/storage/EDITING.md)
- [历史与撤销说明](../src/runtime/storage/HISTORY.md)
- [反馈回归测试](../tests/test_review_fixes.py)
- [命令帮助测试](../tests/test_command_help.py)

这些修改不需要数据库迁移。报告与修复代码一同提交；业务数据库、缓存及其他 output 文件继续忽略。

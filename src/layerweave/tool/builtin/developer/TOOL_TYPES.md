# 工具包登记自己的层和对象

工具包的业务需要一种新的层或对象时，不改核心就能加：配置放进核心的 `configs/`，Python 类放在工具包里，配置用 `requires` 写明依赖哪个工具包。这样 AI 和别的工具按类型就能找到它，配置 help 照常列出，检测照常执行。[返回开发工具](README.md)。

现有的例子是视图工具的批注层：一个项目一个、默认收起的层，按顺序装批注，每条批注用关联指向它说的东西。下文的步骤都以它为例。

## 什么时候需要新类型

- 现有类型装不下工具的业务字段，或者要约束"这个层只装某种对象"。
- 想把一个层当容器、当有序列表用（见下文）。
- 只是给已有对象附加几个键时不需要：内置对象 `open = true`，information 可以直接加键。

## 步骤

| 步骤 | 做法 | 批注层的写法 |
|---|---|---|
| 1. 类 | 在工具包里写 Python 类，继承最接近的内置类；没有新行为时类体可以是空的 | `view/notes/models.py`：`NoteLayer(TextLayer)`、`Note(Text)` |
| 2. 层配置 | 新建 `configs/layers/<类型>.toml`：`class` 指向工具包里的类，`extends` 继承内置配置，`requires` 写工具包模块；只装一种对象时写 `objects = "<对象类型>"` | `configs/layers/note.toml`：`extends = "text.toml"`、`objects = "note"`、`requires = "layerweave.tool.builtin.view"` |
| 3. 对象配置 | 新建 `configs/objects/<类型>.toml`，同样写 `class`、`extends`、`requires`；业务字段写进 `[object.information]` | `configs/objects/note.toml`：`status`、`author`、`span`，都是 `optional` |
| 4. 显示 | 容器一类不该占画布的层写 `[layer.display] default_visible = false`，视图默认收起，可以勾选显示 | 批注层默认收起 |
| 5. 创建 | 不改项目创建流程。工具第一次用到时在写会话里创建这个层，之后按 `config_ref` 找回同一个 | `view/note.py` 的 `_note_layer`：找不到就建一个名为「批注」的根层 |
| 6. 读写 | 照常走 `layerweave.support.api` 的 `transaction` / `run_operation`，进改动日志，可以撤销；删除时一并删掉自己发出的关联 | `add_note`、`update_note`、`remove_note` |
| 7. 测试 | 配置数量变了，更新 `test_configuration.py` 的缓存数；配置 help 的期望在 `test_config_help.py`；再给工具写往返和检测测试 | `tests/test_view.py` 的批注测试 |

要点：

- 配置文件必须放在核心的 `configs/layers`、`configs/objects` 下。配置读取能跟着相对路径读到别处的文件，但 `objects = "<类型>"` 只在 `configs/objects` 里查找，放进工具包目录就找不到。
- `requires` 只是声明，不会自动导入工具包。卸掉那个工具包后，配置仍然说明数据的样子，检测照常；只是 `class` 导入不了，不能还原成 Python 实例。
- 配置 help 会写出"由某工具包登记"。合并视图里，工具登记的对象类型只在同一个工具包登记的层下面展开（批注对象只出现在批注层下面），免得内置层的 help 随工具增多而变长。

## 用层当有序列表

层不一定是画面时间轴。把轴设成"条"，层就成了一个有序列表，用来装工具自己的信息。批注层就是这样：

| 约定 | 批注层的做法 |
|---|---|
| 轴 | 根层，`axis = { unit = "条", precision = 1 }` |
| 位置就是顺序 | 第 n 条占 `[n, n+1)`；新的一条接在最后（现有最大 end 取整）；移动对象就是调整顺序 |
| 指向 | 从条目发出关联（bind），指向它说的对象或层，可以指好几个、可以跨项目；没有关联表示整个项目 |
| 指向一段时间 | 关联到那个时间轴的层，范围写在 information 里（`span`），用那个层的单位 |
| 条目之间的关系 | 条目关联到另一个条目：批注里就是回复，按楼显示，楼主的 `status` 代表整楼 |
| 状态 | 写在 information 里（`status = open / done`） |

这样做不用新建数据表：增删改照常进改动日志，可以撤销；AI 用通用的读取工具和 `read_record` 就能读；目标被删除后关联仍在，检测会报告失效引用，条目本身保留。

不适合的情况：条目需要严格的唯一性或频繁的并发追加（这里只有事务保证，没有额外的锁），或者条目本身就是画面内容（那应该放在时间轴的层里）。

## 相关说明

- 批注层的读写工具和页面行为：[视图工具](../view/README.md#批注层用一个层当有序列表)
- 配置继承、合并与类绑定：[配置说明](../../../support/configuration/README.md)
- 读写接口：[公共 API](../../../support/API.md)
- 命令声明（新工具的 COMMANDS）：[命令专题](../shared/help/COMMANDS.md)

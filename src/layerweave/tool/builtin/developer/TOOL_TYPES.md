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

## 例子：批注层是一个有序列表

把一层的对象当作有序条目来用的思路，主要说明在[AI 开发指导·有序列表与隐藏信息管理](../../../../../docs/build-with-layerweave/02-ordered-metadata.md)。批注层就是照这个思路、再登记成自己的类型：轴是 `{unit = "条", precision = 1}`，每条用关联指向它说的东西，回复是指向另一条批注的关联，状态写在 information 里。具体约定见[视图工具](../view/DEVELOPMENT.md#批注层用一个层当有序列表)。

序号的写法两种都行，由层自己解释：开发指导的例子里每个条目占一个点（`begin = end = 序号`）；批注层让第 n 条占 `[n, n+1)`，这样批注层在视图里显示出来时每条是一块有宽度的色块。

条目只是工具自己的结构、不算项目内容时（比如界面状态、任务记录），用[工具自己的表](../../../../../docs/build-with-layerweave/03-managed-tables.md)更合适，不必登记成层。

## 给自己的层配一个视图页面：视图插件

工具登记的层或对象可以由独立视图插件提供专用页面、侧栏、对象详情和跳转点。插件使用宿主传入的 `host`，不带 Python 写入口、不直接操作数据库；要开发完整 Python 工具仍按前面的工具包约定。

插件默认导出 `(host) => ViewPlugin`，共享 `host.React`。当前接口 `host.api = 3`；已收回的 `block` 栏位不可用。发布插件用 `plugin.json` 声明稳定身份、兼容条件、用途和参数，运行时按本机清单加载。完整字段和流程统一维护在[视图插件协议](../view/PLUGINS.md)。

- 快速试写：主仓库 `frontend/view/example-plugin/plugin.js` 是一个无需构建的字数示例；复制到自己的目录后用 `view_plugin add 路径` 链接。
- 独立开发：固定引用视图包 `sdk/host-api-3` 的生成类型快照，只导入类型，不依赖宿主源码；示例见[官方插件仓库](https://gitee.com/emotion1354414/layerweave-plugins)。
- 发布与更新：插件仓库独立构建、测试和生成 ZIP/目录。主程序不再随包携带官方插件；本地开发链接仍可不写 manifest。
- 截图：页面实际完成后调用 `host.markReady()`。缺插件、加载或渲染失败时截图明确失败，不替换成画布。

## 相关说明

- 批注层的读写工具和页面行为：[视图工具](../view/DEVELOPMENT.md#批注层用一个层当有序列表)
- 配置继承、合并与类绑定：[配置说明](../../../support/configuration/README.md)
- 读写接口：[公共 API](../../../support/API.md)
- 命令声明（新工具的 COMMANDS）：[命令专题](../shared/help/COMMANDS.md)

视图 0.29.0 为 host.api 3 增加 `t` / `useI18n`，仅增加翻译能力，不改变已有字段。插件词典与兼容声明见[视图语言包](../view/LANGUAGES.md)。

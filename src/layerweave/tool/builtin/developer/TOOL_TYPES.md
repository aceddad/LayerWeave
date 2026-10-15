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

把一层的对象当作有序条目来用的思路，主要说明在[AI 开发指导·有序列表与隐藏信息管理](../../../../../docs/build-with-layerweave/02-ordered-metadata.md)。批注层就是照这个思路、再登记成自己的类型：轴是 `{unit = "条", precision = 1}`，每条用关联指向它说的东西，回复是指向另一条批注的关联，状态写在 information 里。具体约定见[视图工具](../view/README.md#批注层用一个层当有序列表)。

序号的写法两种都行，由层自己解释：开发指导的例子里每个条目占一个点（`begin = end = 序号`）；批注层让第 n 条占 `[n, n+1)`，这样批注层在视图里显示出来时每条是一块有宽度的色块。

条目只是工具自己的结构、不算项目内容时（比如界面状态、任务记录），用[工具自己的表](../../../../../docs/build-with-layerweave/03-managed-tables.md)更合适，不必登记成层。

## 给自己的层配一个视图页面：视图插件

登记了新类型以后，如果想在视图里给它一个专用页面（像接缝页那样），写一个视图插件。插件开着就出现，不用重新编译视图；关掉就消失，视图照常工作。接缝就是视图的第一个插件：源码在仓库 `frontend/view/plugins/cuts/`，编译结果在 `view/plugins/cuts/plugin.js`。

插件由视图管：视图有一份本机清单（`~/.layerweave/view/plugins.json`），清单里有的、开着的才载入。工具包不用在 `component.toml` 里写任何东西，视图也不扫描目录。不管工具包多大，在视图这里都只是一行：名字和一个编译好的 js。

| 步骤 | 做法 | 接缝的写法 |
|---|---|---|
| 1. 写插件 | 一个 ES 模块，默认导出 `(host) => ViewPlugin`。`host` 给 React（和视图共用一份，插件不要自己打包）、读项目的 `useView()`、`selectObject` / `startWalk` / `toast` / `markReady` 这些动作、`Img` / `Thumb` / `Frame` 小部件和 `kindOf`、`fmt`、`lanes` 等工具函数。接口定义在 `frontend/view/src/plugin/host.ts`，版本号是 `host.api` | `plugins/cuts/index.tsx` |
| 2. 返回什么 | `label`（标签上的字）、`handles`（管哪些种类的对象；项目里一个都没有就不显示它的页面和侧栏），再加上要用的栏位（见下表）。名字不用写，由清单定（也是地址里的 `view=`、`side=`） | 接缝：`label: '接缝'`、`handles: ['image', 'video']`、`page`、`jumpPoints`；样板「字数」：`side`、`objectDetail`、`block` |
| 3. 编译 | 不打包 React：JSX 编译成 `h(...)`，`h` 在插件被加载时从 `host.React.createElement` 拿。样式写成字符串，用 `host.addStyle` 加进页面 | `vite.plugins.config.ts`：`npm run build` 会编译 `plugins/` 下每个插件 |
| 4. 放好、加进清单 | 编译好的 js 放在自己的目录里，最好一个插件一个文件夹（入口叫 `plugin.js`，同一个文件夹里的拆出去的代码、图片、样式也能访问）。不要放进 LayerWeave 的安装目录，软件更新时会被换掉。然后 `view_plugin add 路径`（或网页顶栏「插件」里加）；小插件可以放在默认文件夹 `~/.layerweave/view/plugins/<名字>/`，加的时候只写名字。工具包的说明里写上这一步 | 接缝是内置的：写在 `view/plugins.py` 的 `BUILTIN` 里，随视图包分发（pyproject 的 package-data 有 `plugins/*/*.js`） |
| 5. 截图 | 截图页面上画完要调 `host.markReady()`，`view_screenshot --view <name>` 就能拍 | 接缝页在页面出来以后调 |
| 6. 测试 | 计算写成纯函数，工具函数从参数传进来，测试里传视图真正的那些 | `plugins/cuts/cuts.test.ts` |

插件能放东西的位置（栏位）：

| 栏位 | 字段 | 给什么 | 例子 |
|---|---|---|---|
| 顶栏页面 | `page` | 一个组件，顶栏多一个标签，点开是它 | 接缝页 |
| 侧栏 | `side` | 一个组件，侧栏多一个标签（和「此刻」「批注」并排） | 样板的「字数」：每个文字层多少字 |
| 对象详情 | `objectDetail` | 一个组件，收到 `{object, model}`；选中对象的详情里多一段。设了 `handles` 时只给这些种类的对象；没话说就返回 `null` | 样板：几个字、每秒几个字 |
| 画布格子 | `block` | `{kinds, types, draw(ctx, o, {width, height, unit, layer})}`：某类对象的格子里画什么，换掉默认的缩略图、画面、波形。`types` 按对象的类型名（`o.type`，配置里的类型，比如 `text`）认，`kinds` 按 `kindOf` 认；两个插件都认时，清单里排在前面的画 | 样板：文字格子底下一条，越快越长、越红 |
| 键盘 `[ ]` | `jumpPoints(model, board)` | 一串时刻（画板时间），`[ ]` 在它们之间跳 | 接缝的时刻 |

样板插件：仓库里的 `frontend/view/example-plugin/plugin.js`（「字数」）。一个文件，不用构建，用到侧栏、对象详情、画布格子三个栏位；复制这个文件夹，放到 LayerWeave 安装目录以外的地方改成自己的。它的类型注释在 `npm run build` 时一起检查，接口改了它会先报错。

要点：

- 每个栏位都包在出错保护里：插件的组件出错，只在它自己那块写一句"出错了"，记进「插件」小窗，视图和别的插件照常。
- 画布格子（`block`）：`host.api = 2`，`draw(ctx, o, {width, height, unit, layer})` 的签名不变。`width`、`height` 是本次绘制的设备像素尺寸，按镜头停下时的缩放提供。`ctx.canvas` 可以是脱离 DOM 的临时画布；插件依照传入尺寸绘制，不查询它的 `clientWidth`、页面位置或父元素。视图负责把结果贴到轨道的共享媒体表面，最终画面与对象的点击、文字、标记分别管理。
- 格子大小、停下后的缩放或对象内容变化时才重新调用 `draw`；已经准备好的结果不因纯平移或拖动重绘，首次进入 near 范围的格子仍会开始绘制。格子太小、只画色块时不调用插件。媒体准备与贴图使用同一个队列，单帧同步工作预算为 3 毫秒；预算耗尽后继续的任务放到下一帧。它不能中断一次较慢的 `draw`，也不代表 Promise 后续回调或 GPU 工作受 3 毫秒限制，插件应自行避免长时间同步计算。
- 未被插件接管的普通音频波形也由轨道共享表面管理，保留原来的采样、立即加载和缩小时照常显示。插件接管音频仍遵循上述插件规则。侧栏/一览的独立媒体与超长对象回退不改变插件接口，具体尺寸边界见[共享媒体的范围](../view/PERFORMANCE.md#共享媒体的范围)。
- `draw` 需要等待图片等资源时返回 Promise，完成表示这一代结果可以贴图。正常页面不设异步绘制时限，Promise 拒绝或绘制抛错时才报告失败。对象删除或新一代绘制取代旧任务时，旧结果会丢弃，也不再阻塞当前画面的等待；同一资源仍被其他对象使用时，其他对象继续等待它。截图等待当前代的准备和最终贴图完成，原生图片/视频也等待真实的完成或错误事件；等待上限由截图工具的 `wait_ms`、性能量具等调用方控制，超时不会在页面里伪装成已画好。插件不依赖临时画布在 Promise 完成后继续显示或继续绘制。
- 插件只在页面里运行，读视图服务已有的数据；写入仍然只有视图自己的两种（批注、折叠）。插件不带 Python 写入口，不碰数据库。
- 清单改了不用重启视图服务，页面自己跟上。有问题的（名字不合规矩、文件不在、重名、在安装目录里）不载入，在 `view_plugin` 和网页小窗里标出原因。
- 一个插件载入失败，页面只提示一句、在小窗里标出原因，不影响别的插件和视图本身。
- 开发时：把自己的插件链接进来，改完重新构建，再点开网页上的「插件」小窗（或刷新页面）就换成新的。
- `host` 的接口只加不改；改了要在这里写明，并改 `host.api` 的版本号。现在是 2：1 只有页面和跳转点，2 加了侧栏、对象详情、画布格子。

## 相关说明

- 批注层的读写工具和页面行为：[视图工具](../view/README.md#批注层用一个层当有序列表)
- 配置继承、合并与类绑定：[配置说明](../../../support/configuration/README.md)
- 读写接口：[公共 API](../../../support/API.md)
- 命令声明（新工具的 COMMANDS）：[命令专题](../shared/help/COMMANDS.md)

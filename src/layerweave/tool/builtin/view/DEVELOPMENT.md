# 视图开发说明

修改视图的数据接入、工具表和网页源码时使用本页。[返回视图首页](README.md)。功能操作见[使用指南](GUIDE.md)，插件单独开发见[插件协议](PLUGINS.md)。开发继续在 visualization 分支进行。

## 批注层：用一个层当有序列表

批注层是视图工具登记的一种层，基于核心开发、核心不改：配置和其他层一样放在核心的配置目录（`configs/layers/note.toml`、`configs/objects/note.toml`），用 `requires = "layerweave.tool.builtin.view"` 写明依赖；Python 类在本工具包的 `notes/models.py`。这样 AI 和工具按类型就能找到它，配置帮助会列出它并注明由谁登记。它示范了另一种用层的方式——不画在时间轴上，而是当作信息容器，按顺序存放条目，每一条用关联指向它说的东西。

| 约定 | 内容 |
|---|---|
| 层 | 类型 `note`，继承文字层，`objects = "note"`（只装批注，放别的对象检测会报错）。一个项目一个，是根层，名字默认「批注」，第一次写批注时自动创建（不改项目创建流程）。`display.default_visible = false`，视图默认收起 |
| 顺序 | 轴固定为 `{unit = "条", precision = 1}`：第 n 条占 [n, n+1)，新的接在最后；移动对象就是调整顺序 |
| 一条批注 | 对象类型 `note`，继承文字对象：正文在 `information.text`；`status` 为 `open`（待处理，缺省也算）或 `done`（已处理）；`author` 写谁写的 |
| 说的是哪里 | 从批注发出关联，指向对象或层，可以指好几个，也可以跨项目。没有关联就是对整个项目的意见 |
| 一段空白时间 | 关联到那个时间轴的根层，并在 `information.span` 写 `{begin, end}`（用那个根的单位） |
| 回复（楼） | 一条批注关联到另一条批注。顺着回复找到的第一条是楼主；楼主的 `status` 代表整楼 |
| 目标被删 | 关联保留，视图显示"目标已删除"，检测报告关联端点不存在（提醒，不是错误）；批注本身保留。删掉被回复的批注，回复留下 |

- 卸掉视图工具后，配置仍说明批注的样子、检测照常，批注能按普通记录读出；只是不能还原成 Python 实例。
- 配置帮助查文字层时，批注对象只在"支持的对象类"里点名（继承文字对象，所以文字层也接受它），不展开详情；查批注层（`combined note`）才展开。
- 用层当有序列表的一般思路见[AI 开发指导·有序列表与隐藏信息管理](../../../../../docs/build-with-layerweave/02-ordered-metadata.md)；别的工具包想像这样登记自己的层（素材清单、待办……），步骤见[工具包登记类型](../developer/TOOL_TYPES.md)。

## 折叠表：视图自己的表

折叠记在业务库里视图登记的工具表 `view_layer`（通过基础支撑的 `register_tables`，第一次折叠时建表）。以后挂在层上的其他视图状态也放这张表。

| 约定 | 内容 |
|---|---|
| 身份 | 一条记录的身份就是它挂着的层：（项目，层编号），`id_source = "provided"`，不另外发号，不占项目编号 |
| 字段 | `user_fold` / `ai_fold`：那一边谁折叠的，空着就是没折叠；`user_tips` / `ai_tips`：那一边的说明 |
| 两边 | 网页是人这边（按网页里的署名记）；`view_fold` 命令和截图是 AI 这边。各改各的，都能展开对方的；网页不替 AI 折叠，AI 不替人折叠 |
| 引用 | 逻辑引用（`logical_references`，不是外键）：层被使用工具删掉时不受阻挡，留下的记录视图读的时候忽略；JSON 交换复制项目（`--op add`）时，折叠跟着层换成新编号 |
| 复制 | 折叠随逻辑引用映射到新的层；已读表的不同策略见下节 |
| 旧库 | 0.21.0 以前建的表是老声明：`view_tables` 查，`view_tables --upgrade` 显式升级一次（只改声明，不改数据、不进改动日志）。视图服务启动时发现旧声明会提示 |
| 日志 | 写入走统一写会话，进改动日志（种类 `view_layer`），可以撤销；视图的"改动"面板不列它们，画布上直接看得到 |

## 已读表与本机状态

`view_note` 由 `notes/reads.py` 声明，一楼一行，身份为楼主批注的（项目，编号），使用 provided，不额外发号。reads 保存“署名 → 最后读到的批注编号”。已读只代表某个人看过；整楼已处理仍是批注 information.status 的含义。

这张表的逻辑引用指向楼主对象，`exchange.on_copy = skip`：reads 中还有批注编号，复制项目时整条已读状态不带过去，新项目重新记录。原库内导出、编辑、写回照常；写入有日志，可以撤销。

排版、视图位置与插件安装清单保存在本机 `~/.layerweave/view/`，浏览器偏好存 localStorage；它们不属于上述业务表。插件管理不修改项目内容。窗口语言不会写入业务数据库。


## 网页源码

网页源码在仓库的 `frontend/view/`（不放进 `src/`，免得 `node_modules` 混进 Python 包和测试扫描）：React + TypeScript，画布用 React Flow（`@xyflow/react`，平移缩放、节点拖动、连线、小地图），状态用 zustand，Vite 编译。

```sh
cd frontend/view
npm ci               # 按锁文件安装构建依赖
npm test             # 纯计算部分的单元测试（vitest）
npm run build        # 类型检查 + 单元测试 + 接口类型快照 + 语言资源复制 + 网页编译，输出到 src/layerweave/tool/builtin/view/web/（提交这些文件）
npm run dev          # 开发：接口转给已经在跑的视图服务（默认 127.0.0.1:8765，环境变量 LAYERWEAVE_VIEW 可改）
```

| 目录 | 内容 |
|---|---|
| `src/model/` | 纯计算，不碰页面：画板分行分段、接续偏移、合并轨道、小行、画板尺寸（`model.ts`），排版操作（`layoutOps.ts`），拖动拼接的判断（`dropRule.ts`），批注成楼和"等谁回复"（`notes.ts`），改动标记（`changes.ts`），空当（`gaps.ts`），键盘跳转（`navigate.ts`），复制链接（`link.ts`） |
| `src/model/__tests__/` | 上面这些的单元测试，手写的小项目做输入（`fixtures.ts`），期望值都能心算 |
| `src/canvas/` | React Flow 画布（`Flow.tsx`）、画板节点（`BoardNode.tsx`）、对象色块、关系线；`TrackMedia.tsx` 管轨道共享媒体与超长对象回退，`Waveform.tsx` 提供共享波形算法及侧栏/一览使用的独立组件；`drop.ts` 从页面上找出鼠标落点，交给 `dropRule.ts` |
| `src/side/` | 右侧面板：此刻、改动、批注、沿读 |
| `src/tree/` | 左边的目录树（`model/tree.ts` 是它的纯计算） |
| `src/plugin/` | 插件接口（`host.ts`：插件能用的东西和栏位）、载入（`registry.ts`：按清单载入、拿下来；`plan.ts`：和清单对一遍）、出错保护（`slots.tsx`）；顶栏的「插件」小窗是 `src/PluginManager.tsx`，格子的共享媒体由 `canvas/TrackMedia.tsx` 管理；`Media.tsx` 保留旧逐格路径和特殊格子的绘制 |
| `example-plugin/` | 样板插件「字数」：不用构建的一个 js，类型注释随 `npm run build` 检查；不随软件分发 |
| `tools/export-plugin-sdk.mjs` | 构建时从真实 host.ts 生成可独立引用的类型快照，输出到 Python 视图包的 sdk/；官方插件源码在独立仓库 |
| `src/store.ts`、`sync.ts`、`camera.ts`、`actions.ts` | 状态；和服务同步（轮询、保存排版、报告"正在看哪儿"、写批注）；镜头；用户操作 |
| `src/i18n/`、`tools/copy-locales.mjs` | 语言状态、词典与 Python 资源复制；详见[语言包](LANGUAGES.md) |
| `src/capture.ts`、`params.ts` | 截图约定：地址参数，以及加载完以后设 `window.__layerweaveReady` |

**性能验收**：先运行以下命令；查看每轮有效性，再判断门槛。完整的输入方式、p95/最长帧、就绪检查、大库定位和基线比较统一见[性能说明](PERFORMANCE.md)。

~~~sh
python -m layerweave.tool.builtin.view.bench --objects 800 --rounds 3
python -m layerweave.tool.builtin.view.bench --objects 800 --rounds 3 --baseline D:/bench/before-web --json
~~~

基线是含 index.html 的旧网页构建。新旧构建共用量具、服务和数据，按交替反转顺序测量；空视口或未画出的插件不能判通过。首个对象进入 DOM 与画好、可操作是不同阶段，热身改善也不能直接归因为显卡频率。

改网页时保持后端接口和截图约定不变（地址参数、`record=0`、`__layerweaveReady`），`view_screenshot` 和测试就照常可用。画板尺寸由数据算出（`Model.boardLayout`），排版不依赖量页面。新的计算放进 `src/model/` 并补单元测试；页面上的部分（拖动、镜头）在浏览器里试。

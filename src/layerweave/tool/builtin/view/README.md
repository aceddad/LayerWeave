# 内部工具 · 视图工具

本机网页视图，以及给 AI 用的五个工具：截图、取帧、画板排版、"用户正在看哪儿"、批注。还登记了一种层：批注层。[返回内部工具导航](../README.md)。

视图只读，例外只有两种，都是视图自己的东西：批注（只写批注层，见下文）和折叠（只写视图自己的表 `view_fold`，见下文）。服务只监听 127.0.0.1，用只读方式打开数据库看项目；写这两种时才打开一次写会话，进改动日志，可以撤销。要修改项目内容，仍然用使用工具。服务端只用 Python 标准库；网页是编译好的静态文件，随包分发（`web/`），用的人不需要 Node。网页源码和改法见文末"网页源码"。

## 给人看：视图网页

```sh
python -m layerweave.tool.builtin.view.server DATABASE [--project 1] [--port 8765]
```

用浏览器打开打印出来的地址。

- **画布**：一张可以拖动、缩放的画布。每个根层连同它的子树是一块**画板**，画板里是这个根的时间轴：层按父子顺序排成轨道；对象是轴上的色块。同一层里互相重叠的对象会分成上下几行。两个对象之间空着的地方画一条标尺 `|— 3.000 —|`，写出空了多长，位数按这个根的轴精度（精度 0.001 写三位小数，按帧的写整数）；太窄放不下数字时只画两头的竖线，第一个对象之前、最后一个之后不画。图片显示缩略图，视频片段够宽时左边是第一帧、右边是最后一帧（窄的只显示开头），音频显示波形，文字直接显示；素材文件不存在的对象用斜纹标出。配置里 `display.default_visible = false` 的层（比如批注层）默认不进画布。
- **折叠**：人和 AI 各有各的折叠，互相看得见。每一层名字前都有 ▾，点一下收起这一层和它下面所有的层，只剩一条细条：层名带橙色边框，内容处是一条虚线框，写着"已折叠 · 下面 2 层 · 5 个对象 · 💬 1 楼待处理（用户 折叠的：备注）"，可以在上面写备注；画板标题上写"折叠了几条"。点 ▸ 或细条展开。左右接续时合成一条的轨道，折叠会折叠它包含的每一个层。
  - **AI 折叠的**在你的页面上照常展开，层名旁标着"AI 折叠"，轨道右上角写着"Claude 折叠了：原因"；点标签上的 × 让 AI 也展开。AI 新折叠了什么，右下角会提示。
  - **你折叠的**在 AI 的截图里照常画出，标着"用户折叠了"：AI 照常检查里面的内容，只知道你现在不关注它。AI 也能把你折叠的层展开给你看，写了理由就会在那一层留一条批注，你收到提示，可以在楼里回它。
  - 折叠存在数据库里视图自己的表（见下文"折叠表"），下次打开、换一个 AI 来看，都还是这样。画板变高变矮时，下面的画板跟着推开或收拢。地址加 `?as=ai` 可以看 AI 那边的样子（只看不改折叠）。
- **拼接**：单位相同的根才能拼。"秒"和"s"这类同义写法算同一种单位；没有单位的根各占一块，不参与拼接。
  - **上下 = 同时**：几行共用一把尺子和一根播放头，同一个数值上下对齐。单位相同的根默认就这样拼在同一块画板里。
  - **左右 = 接续**：后一个根的 0 接在前一个根的结尾（比如第二章接在第一章后面），画板上用连续的时间；两段里名字相同的层合成一条轨道（第一章的「字幕」后面接第二章的「字幕」）。这一行上方有一条窄带，标出每一段的名字和起点。只能手动接。
  - 拖动画板标题可以移动画板。拖到另一块画板的一行中间，提示拼在这一行的上方或下方；拖到某一段的开头或结尾附近，提示接在前面或后面；松手就拼上。单位不同、或者想把好几行的画板左右接时，会说明原因，松手只是摆在那里。
  - 每个根都有「拆出」：单独一行的在层名旁边，接续的在窄带的名牌上。拆出的画板放在原画板正下方；拼走的画板留下的空当会被下面的画板补上。拖到别的画板边缘附近会自动对齐。
- **操作**：拖动空白处平移（按住空格也能在画板上拖）；在尺子上拖可以圈出一段（Esc 取消）；滚轮缩放画布；Alt+滚轮只缩放鼠标下那块画板的时间；画板标题上的 − 适应 ＋ 也是缩放时间。画板左边移出视口时，层名一列会贴在视口左边。顶栏的「全部」显示所有画板；右上角的小地图可以拖动、缩放。
- **键盘**：选中对象后，←/→ 选中同一轨道的前一个、后一个（左右接续时跨段接着走），↑/↓ 选中上一条、下一条轨道上离这一刻最近的对象；没选中对象时，←/→ 让播放头在剪辑点（对象的开头、结尾）之间跳。[ / ] 让播放头跳到上一个、下一个接缝。镜头只在目标出了画面时才跟过去。
- **复制链接**（顶栏）：把现在看的位置写成一个地址——当前画板、看得见的那段时间、播放头、选中的对象、对准的批注。贴给 AI，它用 `view_screenshot --link` 就能拍到同一个画面；浏览器不让写剪贴板时，地址会显示出来让你手动复制。
- **此刻**（右侧第一个标签）：点画板上任意位置，列出这一刻这块画板每层都有什么，视频会显示这一刻的画面；点色块会展开对象详情（含指向它的批注和它的关系）。这一刻没有对象的层写一行是哪种空："空着：6–9（3 秒）"是两个对象之间空着，"已经结束""还没开始"是在这层第一个对象之前或最后一个之后；整层都没有对象的容器层不写。播放头只在当前画板上，用这块画板的单位；落在接续的行上时，同时写出是哪一段的第几秒。
- **改动**（右侧第二个标签）：列出最近 1～100 次操作改了什么——新建、删除、移动（前后位置）、改了哪些字段（information 里改了的键给出前后值）。打开时画布上标出改过的对象（角上的数字是倒数第几次操作），删除或移动之前的位置画成虚线框。点列表里的一条，镜头飞到那个对象或那个虚线框上。只读 changes 日志。
- **批注**（右侧第三个标签）：按楼列出批注，可以只看待处理、已处理或"等我回复"的楼。先选中一个对象、点一个层名，或者在尺子上圈出一段，再写，批注就指向那里；什么都不选就是写给整个项目。每条都能回复，回复按楼显示（"3 楼 回复 2 楼"）；勾上楼主表示整楼已处理；改、删、回复都在卡片里完成（不用浏览器弹窗）。画布上，有待处理批注指着的色块和层名标 💬，指向一段时间的批注画成黄色的带子；点批注里的目标，镜头飞过去；点楼主上的「定位」，镜头框住这一楼指的全部地方，目标标成橙色虚线。
- **批注提醒**：按本机的署名（批注面板里填，默认「用户」）算"等我回复"的楼——还没处理、最后一句不是你说的，和 `view_note --waiting` 是同一条规则。批注标签上的红色数字、浏览器标签页标题前的 (2)、楼上的「等你回复」都是它。别人（比如 AI 用 `view_note`）写了新批注或回复时，右下角弹一条提示，点一下打开那一楼。
- **关系线**：数据里的关联（bind）画成带箭头的线，跨画板也画；连到层的线接在层名上。平时只画选中对象的关系，顶栏勾上「关系线」画出全部。选中对象的详情里列出它的关系，点一条跳过去；另一头在别的项目时，色块角上标 ↗。
- **接缝**（顶栏第二个标签）：同一条轨道里前后相接的图片和视频，把上一段的最后一帧和下一段的第一帧并排，写出两边的时间、是紧接还是中间空着；接续的两段之间也算。用来查衔接——比如上一段球落在地上，下一段却从桌上开始。点一个接缝回到画布上的那个位置。
- **找对象**：顶栏的搜索框按名字、文字、文件名或 `#编号` 找，回车跳到下一个，Shift+回车上一个。
- **素材**：像资源管理器一样，用网格显示图片、视频封面、音频波形和文字；可以按类型筛选，点一下回到画布上的对应位置。
- 数据库被工具修改、或者排版被 AI 改了以后，两秒内自动刷新。

画板的拼接、拆分、位置和时间缩放存在本机用户目录 `~/.layerweave/view/<数据库路径的散列>.layout.json`，不写进业务库。

素材路径：`information.source` 是绝对路径就直接用，是相对路径就相对于数据库文件所在的目录；网址不经本机服务提供。服务只提供数据库里引用过、而且确实存在的文件，支持 Range 请求，所以视频可以拖动进度。

视频画面：本机有 ffmpeg（在 PATH 里，或用环境变量 `FFMPEG` 指定）时，封面和"此刻"的画面由服务端抽帧，结果稳定，截图也拍得到；没有 ffmpeg 时，交给浏览器自己解码。

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
| 引用 | 不声明引用：层被使用工具删掉时不受阻挡；编号不回收，留下的记录不会被新层误认，视图读的时候忽略 |
| 日志 | 写入走统一写会话，进改动日志（种类 `view_fold`），可以撤销；视图的"改动"面板不列它们，画布上直接看得到 |

## 给 AI 用

| 工具 | 用途 |
|---|---|
| `view_state` | 用户正在看哪儿：项目、当前画板、可见范围、播放头、选中的对象、圈出的一段、屏幕上的画板和层。用户说"这里""这段"时先读它 |
| `view_note` | 读写批注：`list`（按楼；可只看 open / done 的楼，`--waiting 名字` 只看在等这个人回复的楼）、`add`（`--to object:16`、`--to layer:1 --span 6 8`，可以多个）、`reply 编号 正文`、`done` / `reopen`、`edit`、`remove`。自动建批注层、填字段、建关联 |
| `view_screenshot` | 把视图截成 PNG：整张画布、某一块画板（`--board`，可加 `--begin --end` 放大一段）、接缝页（`--view cuts`）或素材网格；`--focus` 对准某个对象，`--note` 对准某条批注（框住它指的地方，右侧标出这一楼），`--link` 按用户「复制链接」得到的地址拍，`--changes N` 标出最近 N 次操作的改动，`--notes` 打开批注列表，`--links` 画出全部关系线，`--full-page` 把接缝页、素材页截成一整张长图。等页面把图片、封面、波形加载完才拍 |
| `view_fold` | 两边的折叠：不带动作时列出；`fold 层编号… --by 名字 --why 原因` 折叠 AI 这边的；`unfold` 展开；`unfold --side user --why 理由` 把用户折叠的展开给用户看（写了理由就留一条批注）。截图的返回里也列出两边的折叠 |
| `view_layout` | 查看或调整画板：同单位的根上下拼（`merge --side above/below`）、左右接（`merge --side left/right`）或拆开（`split`）、移动（`move`）、恢复自动排版（`reset`）。和网页改的是同一份排版 |
| `view_frame` | 取视频对象在某一刻的画面（JPEG），按时间轴全局时间或视频自身时间，`--last` 取最后一帧；需要 ffmpeg |

```sh
python -m layerweave.tool.builtin.view.state DATABASE
python -m layerweave.tool.builtin.view.note DATABASE 1
python -m layerweave.tool.builtin.view.note DATABASE 1 add "球应该落在桌子下面" --to object:16 --author Claude
python -m layerweave.tool.builtin.view.note DATABASE 1 add "这两秒空着" --to layer:1 --span 6 8
python -m layerweave.tool.builtin.view.note DATABASE 1 --waiting Claude
python -m layerweave.tool.builtin.view.note DATABASE 1 reply 46 "改好了" --author Claude
python -m layerweave.tool.builtin.view.note DATABASE 1 done 41
python -m layerweave.tool.builtin.view.screenshot DATABASE 1 输出.png
python -m layerweave.tool.builtin.view.screenshot DATABASE 1 输出.png --board 1 --begin 8 --end 14 --playhead 10
python -m layerweave.tool.builtin.view.fold DATABASE 1
python -m layerweave.tool.builtin.view.fold DATABASE 1 fold 15 --by Claude --why 先对字幕
python -m layerweave.tool.builtin.view.fold DATABASE 1 unfold 9 --side user --by Claude --why 这里空了要你看一下
python -m layerweave.tool.builtin.view.layout DATABASE 1
python -m layerweave.tool.builtin.view.layout DATABASE 1 split 19
python -m layerweave.tool.builtin.view.layout DATABASE 1 merge 19 --to 1 --side above
python -m layerweave.tool.builtin.view.layout DATABASE 1 merge 31 --to 1 --side right
python -m layerweave.tool.builtin.view.screenshot DATABASE 1 输出.png --changes 5
python -m layerweave.tool.builtin.view.screenshot DATABASE 1 输出.png --note 42
python -m layerweave.tool.builtin.view.screenshot DATABASE 1 输出.png --link "http://127.0.0.1:8765/?project=1&board=1&begin=8&end=14&select=16"
python -m layerweave.tool.builtin.view.screenshot DATABASE 1 接缝.png --view cuts --full-page
python -m layerweave.tool.builtin.view.frame DATABASE 1 16 输出.jpg --at 3.75
```

- 画板用根层编号来指：`--board 1` 是"根层 1 所在的那块画板"；子层跟着它的根走。
- 位置、播放头、时间范围都用对应画板的单位；不同画板的单位可能不同（比如一块是秒，一块是帧）。
- 左右接续的画板上，`--begin --end --playhead` 用画板上的连续时间；`view_layout` 返回的 `offset` 是每一段在画板上的起点（画板时间 = 这一段自己的时间 + offset），`view_state` 的 `playhead_at` 给出播放头落在哪一段、是那一段自己的第几秒。
- 开工前先看 `view_note --waiting 自己的名字`：用户在网页上提的问题、回复都在那里，回复用 `reply`。想看一条批注指的是哪里，用 `view_screenshot --note 编号`。
- 用户贴来视图地址（「复制链接」）时，用 `view_screenshot --link 地址` 拍同一个画面；链接里的项目要和参数里的项目一致。
- 折叠分两边：AI 折叠只影响 AI 这边（截图里收成细条，内容没画出来），折叠时写上原因。用户折叠的层在截图里照常画出、标着"用户折叠了"——那只说明用户现在不关注，判断时照常检查。开工时用 `view_fold` 看一眼两边的折叠：用户可能展开了 AI 折叠的层，想让 AI 看回来。
- 用户圈出一段后，`view_state` 的 `selection` 给出那一段在哪个根上、那个根自己的起止；要给这一段写批注，用 `view_note add --to layer:根编号 --span 起点 终点`。
- 改动的文字清单也可以用使用工具里的 `read_history`；视图的用处是把改动放回画面里看。
- 截图自动查找 Chrome、Edge 或 Chromium，也可以用 `--browser` 或环境变量 `LAYERWEAVE_BROWSER` 指定。浏览器使用临时的独立配置，不会碰到用户正在用的浏览器；截图页面不记录状态、不改排版、不写批注和折叠。返回里的 `ready` 为 False 时，表示等待时间内没加载完，图里可能缺缩略图。
- "正在看哪儿"记在本机用户目录 `~/.layerweave/view/` 下，每个数据库一份，不写进业务库。

## 网页源码

网页源码在仓库的 `frontend/view/`（不放进 `src/`，免得 `node_modules` 混进 Python 包和测试扫描）：React + TypeScript，画布用 React Flow（`@xyflow/react`，平移缩放、节点拖动、连线、小地图），状态用 zustand，Vite 编译。

```sh
cd frontend/view
npm install          # 第一次
npm test             # 纯计算部分的单元测试（vitest）
npm run build        # 类型检查 + 单元测试 + 编译，输出到 src/layerweave/tool/builtin/view/web/（提交这些文件）
npm run dev          # 开发：接口转给已经在跑的视图服务（默认 127.0.0.1:8765，环境变量 LAYERWEAVE_VIEW 可改）
```

| 目录 | 内容 |
|---|---|
| `src/model/` | 纯计算，不碰页面：画板分行分段、接续偏移、合并轨道、小行、画板尺寸（`model.ts`），排版操作（`layoutOps.ts`），拖动拼接的判断（`dropRule.ts`），批注成楼和"等谁回复"（`notes.ts`），改动标记（`changes.ts`），接缝（`cuts.ts`），空当（`gaps.ts`），键盘跳转（`navigate.ts`），复制链接（`link.ts`） |
| `src/model/__tests__/` | 上面这些的单元测试，手写的小项目做输入（`fixtures.ts`），期望值都能心算 |
| `src/canvas/` | React Flow 画布（`Flow.tsx`）、画板节点（`BoardNode.tsx`）、对象色块、关系线；`drop.ts` 从页面上找出鼠标落点，交给 `dropRule.ts` |
| `src/side/` | 右侧面板：此刻、改动、批注 |
| `src/views/` | 接缝页、素材页 |
| `src/store.ts`、`sync.ts`、`camera.ts`、`actions.ts` | 状态；和服务同步（轮询、保存排版、报告"正在看哪儿"、写批注）；镜头；用户操作 |
| `src/capture.ts`、`params.ts` | 截图约定：地址参数，以及加载完以后设 `window.__layerweaveReady` |

改网页时保持后端接口和截图约定不变（地址参数、`record=0`、`__layerweaveReady`），`view_screenshot` 和测试就照常可用。画板尺寸由数据算出（`Model.boardLayout`），排版不依赖量页面。新的计算放进 `src/model/` 并补单元测试；页面上的部分（拖动、镜头）在浏览器里试。

## 以后
- 播放（按播放头放视频和音频）、大项目只画看得见的部分：先放着。

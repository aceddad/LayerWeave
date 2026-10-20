# 多智能体协作：晚开的花（动态 SVG 长卷）

四个智能体各画一幕动态 SVG，通过 LayerWeave 的**批注**互相协商接缝、配色和修改；最后拼成 9600×1400 的长卷，用 36 秒 `viewBox` 镜头串起来。

故事是暗线，不写在画面上：**一朵晚开的花，在暖色的春天里被允许。** 四幕分别是春、夏、秋、冬夜。

> 这是一个演示案例，不是精修作品；重点是“批注驱动多智能体协作”这件事怎么落地。

## 能看到什么

| 位置 | 内容 |
|---|---|
| `project.json` | 案例数据：4 层、37 个对象（含 32 条批注）、35 条关联 |
| `scenes/` | 四幕独立动态 SVG（2400×1400，各 3 组 SMIL 动画） |
| `assets/long-scroll.html` | **自包含动态预览**，直接浏览器打开即可 |
| `assets/long-scroll.svg` | 单文件动态长卷 |
| `assets/overview.svg` / `overview.html` | 9600×1400 静态全貌 |
| `assets/screenshots/` | 四幕截图、全貌、LayerWeave 批注面板 |
| `assets/collaboration-notes.md` | 批注链与关键修改记录 |

## 直接看长卷

双击 `assets/long-scroll.html` 即可；也可先按[uv 步骤](../README.md#准备环境)设置 `$casePython`，在本案例目录启动本地服务：

```powershell
& $casePython -X utf8 -m http.server 8793
# 打开 http://127.0.0.1:8793/assets/long-scroll.html
```

`assets/long-scroll.html` 是自包含的，SVG 已内联，不依赖 `scenes/` 或网络。

## 用 LayerWeave 看项目与批注

使用完整版本（含批注类型），先按[案例目录的 uv 步骤](../README.md#准备环境)设置 `$casePython`，在本案例目录执行：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.developer.database.cli project.sqlite3
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply project.sqlite3 --data-file project.json --new-project --result-file import-result.json
$caseImport = Get-Content -Raw -Encoding utf8 import-result.json | ConvertFrom-Json
if (-not $caseImport.ok) { throw '导入失败，请检查 import-result.json' }
$caseProjectId = $caseImport.data.project_id
& $casePython -X utf8 -m layerweave.tool.builtin.view.server project.sqlite3 --project $caseProjectId --port 8794
```

打开服务打印的地址。项目数据库由 JSON 创建，不随案例包提供；使用实际返回的项目编号。画布上四幕按序号排列，右侧批注可看协作记录。

媒体路径相对于数据库目录，数据库应与 scenes 同级。个人已读状态 view_note 按复制策略跳过；批注对象与回复保留。导入反馈中的此类跳过不表示批注丢失。

## 批注怎么驱动了修改

- **spring #16 → summer #18**：spring 指出云的模糊尾巴离边界只剩 4px；summer 把 `σ=22` 降到 16，云内收 50px。
- **summer #20 → autumn #26**：summer 读第三幕，发现蓝线被花团压住；autumn 把蓝线移到最上层，路径一字未改。
- **lead #23 → spring #28**：拼接截图里第一幕的雨在 x≈2300 被硬切；spring 加了 120px 横向淡出 mask。
- **autumn #32 → lead**：autumn 反过来指出 Lead 第四幕的花茎和蓝线同色、交叉成「＋」；Lead 把花茎改成 `#4E7FA8`。
- **#13/#14/#17/#19/#33/#34**：相邻两幕互核蓝线控制点、天空渐变 `stop 0/0.55/1`、地面带 `y=1100`、左右 80px 边缘。

截图见 `assets/screenshots/view-notes.png`。

## 技术

- 四幕各 2400×1400，总内容 9600×1400；天空渐变 `0/0.55/1` = `#2B3A55 / #3E5A7A / #F2E8D5`；地面 `<rect y="1100" height="300" fill="#F2E8D5">`；蓝线标准路径 `M0 900 C 600 860, 1800 940, 2400 900`。
- 每幕 3 组 SMIL 动画，8 秒循环；无 JavaScript、无外部图片/字体（HTML 只加暂停/播放按钮）。
- 镜头用根 `<animate attributeName="viewBox">` 做 36 秒平移；拼接时地面带左右各扩 2px，避免 cream 与天空渐变的亚像素混色。
- 四幕动画各自从 0s 起跑，相位未统一；这是演示，不追求精修。

## 已知限制

- 花是扁平/几何风格，偏“贴纸感”；倒影只做 `skew`，没有真正水波扭曲。
- 部分批注楼保留为“待处理”，作为协作记录；需要收尾时可统一标 done。
- 案例不附带歌曲和歌词，画面本身是独立演示。

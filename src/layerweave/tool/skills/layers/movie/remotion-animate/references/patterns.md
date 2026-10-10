# 写法要点

## 时钟与节拍
- 一条音轨就是全局时钟：`t = useCurrentFrame() / FPS`。所有场景都用 t 计算，这样画面和声音不会慢慢错开。
- 把 audio-cues 卡点表里的 `bpm`、`beat0` 抄进 `time.ts` 的 `BPM`、`PHASE`，然后按拍来写时间：`beat(32)` 比 `16.15` 好读，也好改。
- 歌词或台词的重音时间可以从 SRT 或卡点表里取，写成一张"时间点表"，供场景引用；只写时间，不写内容。
- 用段落表切分全片，每段一个文件，并在文件开头写一句这段讲什么、怎么对拍。

## 画法
- **SVG**：图形、线条、文字、遮罩、字形变形。元素在几百个以内时最方便，而且可以直接用 CSS。
- **Canvas**：成百上千的点、拖尾、粒子、长曝光轨迹。用 `Layer` 组件，绘制函数只依赖 t。
- **图片**：放在 `public/`，用 `<Img src={staticFile(...)}>`。网点画可以用 image-halftone 导出的点坐标 JSON，在 Canvas 里一颗颗画。
- **视频片段**：生成或实拍的片段用 `<OffthreadVideo>` 或 `@remotion/media` 的 `<Video>` 放进来，再用代码加镜头运动和变速，让动作落在拍上。

## 节奏和质感
- `on12(t)`：把时间量化到 12 fps，也就是一拍二，动起来更像手绘。只在关键姿势停住时，效果更明显。
- `pulse(t)`：每拍一次的衰减脉冲，适合让大小、亮度跟拍。`hit(t, at)`：在某一刻冲击一下，然后衰减。
- 卡点表 JSON 里有每轨逐帧的响度包络，可以直接驱动运动幅度（例如鼓的包络驱动震动）。但旋律、强弱、停留是否合适，仍要原速听着看。

## 确定性
- 每一帧只由 t 决定。不要在组件里累积状态，不要用 `Math.random()`，要随机就用 `hash(编号)`。
- 需要异步加载数据（字幕、JSON）时，用 `delayRender` 和 `continueRender`，确保数据到齐了才截图。模板里的 `Subtitles` 就是这样写的。

## 字幕与原文
- 字幕在渲染时从 `public/media/subtitles.srt` 读取，代码里不写内容。
- 检查排版有两种办法：用 `Film-Layout` 入口，它把字换成占位符；或者用 [text-redacted-layout](../../../text/text-redacted-layout/SKILL.md) 生成涂黑字体，排出来的位置和断行都与原字体完全一致。
- 带真字幕的版本（`Film-Subtitled`）由有权查看原文的人来导出。

## 审阅
- 改完先渲关键几拍的静帧，用 `Film-Review` 入口，画面上会印出秒数、拍号和段名。
- 整片导出后，用 [video-timing](../../video-timing/SKILL.md) 看状态和过渡，用 [video-verify](../../video-verify/SKILL.md) 核对帧数和音画偏移，用 [video-master](../../video-master/SKILL.md) 出发布母版。

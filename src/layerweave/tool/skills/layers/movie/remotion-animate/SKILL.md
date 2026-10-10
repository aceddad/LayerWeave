---
name: remotion-animate
description: 用 Remotion（React）写代码动画：一条音轨当全局时钟，按拍子驱动画面；分段场景各放一个文件；用 SVG 画图形和字、用 Canvas 画成百上千的点和粒子；字幕在渲染时从 SRT 读取；按秒渲审阅静帧、导出视频。附一个能直接跑的最小工程模板。做 MV、PV、动态图形、手书风格的代码动画时使用。
---

# Remotion 代码动画

需要 Node.js 18 及以上。模板在 `assets/template/`，复制出来就是一个完整的工程。

工程位置、审阅静帧目录和视频输出路径由调用的 AI 按项目安排；复制模板和运行渲染脚本时显式指定，建议使用绝对路径。项目成果保存在 AI 选定的位置。

## 开始

```sh
cp -r assets/template 我的工程      # 复制模板
cd 我的工程
npm install                          # 安装 Remotion、React、TypeScript
npm run check                        # 类型检查
npm run dev                          # 打开 Remotion Studio 预览
```

- 首次渲染时，Remotion 会自动准备 Chrome Headless Shell。本机已经有的话，用环境变量 `REMOTION_BROWSER_EXECUTABLE` 指定它的路径。
- 许可：Remotion 使用自己的许可协议，个人和小团队免费，规模较大的公司需要购买授权。以 remotion.dev 上的说明为准。
- 模板固定使用 Remotion 4.0.531 测试过；升级版本后，先跑一遍 `npm run check` 和一次短渲染。

## 模板结构

| 文件 | 作用 |
|---|---|
| `src/time.ts` | 全局时钟和节拍工具：`beat(n)` 求第 n 拍的秒数，`pulse(t)` 每拍一次的脉冲，`hit(t, at)` 一次性冲击，`on12(t)` 把时间量化到一拍二，`prog`/`ease`/`lerp`/`hash` 用于插值和可复现的随机。BPM 和第 0 拍从卡点表抄过来 |
| `src/Film.tsx` | 段落表 `SEGS`：每段从第几秒开始、用哪个组件。还没做的段显示 TODO |
| `src/Root.tsx` | 四个入口：`Film` 正片、`Film-Review` 带时间码和拍号、`Film-Layout` 字幕用占位符、`Film-Subtitled` 带真字幕 |
| `src/scenes/Intro.tsx` | SVG 示例：圆每拍一跳、每小节换色、方块在指定拍滑入、一次闪白 |
| `src/scenes/Dots.tsx` | Canvas 示例：400 个点按一拍二运动，最后一小节聚拢 |
| `src/ui/Layer.tsx` | Canvas 图层，以及画点、画拖尾的工具函数 |
| `src/ui/Subtitles.tsx` | 渲染时读取 `public/media/subtitles.srt`；占位模式会把字母和汉字换成 x 和 □ |
| `scripts/stills.mjs` | 按全局秒数渲几张审阅静帧 |
| `scripts/render.mjs` | 导出视频，可以只渲一个帧范围，可以调并发 |

## 审阅与导出

```sh
node scripts/stills.mjs 审阅图文件夹 1.5 5 10 --comp Film-Review     # 按秒渲静帧
node scripts/render.mjs 成片.mp4 [--comp Film] [--frames 0-95] [--concurrency 1]
```

- 先用静帧对关键的几拍，满意了再导出整片。
- `--concurrency` 是同时渲染的浏览器标签数，默认取 CPU 核数的四分之一。机器吃紧时设为 1，并且一次只跑一个渲染。临时文件跟随系统的 TEMP/TMP 变量；系统盘紧张时，先把这两个变量指到别的盘再运行。
- 导出的视频是全范围 bt601（`yuvj420p`），色彩不写标注。发布前用 video-master 转成 bt709 母版，再用 video-verify 核对。

## 写法要点
详见 [references/patterns.md](references/patterns.md)。最重要的三条：
1. 只有一个时钟。每段拿到的都是全局秒数 t，不要在每段里各自重新计时。
2. 每一帧只由 t 决定。Remotion 是多进程、乱序渲染的，不能依赖上一帧留下的状态；需要随机时用 `hash(编号)`。
3. 内容和代码分开。字幕从 SRT 读取，图片和音频放在 `public/`，代码里不写死原文。

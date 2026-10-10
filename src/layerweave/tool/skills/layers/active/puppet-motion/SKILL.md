---
name: puppet-motion
description: 用 three.js 胶囊木偶按摄影表做动作参考：关键姿势写成关节角度，按帧插值，节奏（停住、加速砸下、余势）完全由自己定；在 Remotion 里渲出视频，作为生视频模型的参考视频，或者直接当动作草稿来检查节奏。需要控制角色动作的顺序和停顿时使用。
---

# 人偶动作参考

组件在 `assets/Puppet.tsx`，配合 [remotion-animate](../../movie/remotion-animate/SKILL.md) 模板使用。先按该技能建立工程；下面的 npm、静帧和渲染命令在工程目录执行。

工程目录、审阅图目录和视频输出路径由调用的 AI 自行管理，渲染时显式传入本次选定的位置，建议使用绝对路径。

## 放进工程

```sh
npm install three@0.170 @types/three@0.170
```

1. 把 `assets/Puppet.tsx` 复制到工程的 `src/puppet/`。
2. 在 `src/Root.tsx` 里登记一个入口：

```tsx
import {Puppet} from './puppet/Puppet';
<Composition id="Puppet" component={Puppet} durationInFrames={120} fps={24} width={1152} height={768}/>
```

3. 渲染时要给浏览器打开 WebGL，静帧和导出都加 `--gl angle`：

```sh
node scripts/stills.mjs 审阅图 0 1.3 2.6 4.9 --comp Puppet --gl angle
node scripts/render.mjs 人偶.mp4 --comp Puppet --gl angle --concurrency 2
```

## 写动作
- **姿势**（`Pose`）：骨盆位置 x、y（米），加上脊柱、脖子、手臂、手肘、大腿、膝盖、脚的角度（度，正值表示向前弯或抬起）。人偶面朝画面右边。`POSES` 里有站、低头、膝盖一软、跪下的冲击、跪住、瘫下去几个现成姿势，可以在它们的基础上改。
- **摄影表**（`Key[]`）：每一行写 `[到达这一帧, 姿势, 缓动]`。同一个姿势连写两行，就是停住；`easeIn` 越来越快，适合砸下去；`easeOut` 一下子到、慢慢停，适合冲击后的余势；`inOut` 两头慢。
- 把自己的摄影表作为 `keys` 传进组件；相机用 `camera` 调整，包括视角、位置、注视点。示例 `KNEEL_KEYS` 是：站着停一下 → 低头 → 膝盖一软 → 砸到地上 → 跪住 → 上身瘫下去。

## 检查节奏
用 [video-timing](../../movie/video-timing/SKILL.md) 的 keys.py 看渲出来的视频：停住的段、到位点、方向转折都会列出来，可以和摄影表对照。实测示例摄影表：跪住（第 56–68 帧）、瘫下（第 92–119 帧）都被准确找出；第 30–34 帧那个只有 4 帧的低头停顿太短，被并进了前面站着的那一段。

## 当作生视频的参考视频
进入 [video-generate](../../movie/video-generate/SKILL.md) 技能目录，按其连接说明配置服务，再用参考视频模式把人偶视频和角色图一起交给模型。输入与输出文件使用本次项目的实际路径：

```sh
python scripts/video.py submit 输出.mp4 提示词.txt --ref-image 角色.png --ref-video 人偶.mp4 --duration 5
```

- 只实测过一次：动作顺序和停顿跟上了，画面里没有出现人偶，角色正确。
- 问题：构图没有跟随参考视频，人物变小了；漏掉了低头；跪下前出现了参考里没有的转身；跪倒比人偶更猛。
- 还没试过的改进方向：用人偶第 0 帧当草图，按出图 skill 的草图引导出一张"同机位"的角色图作为参考图，而不是给一张正面设定图，因为正面设定图可能就是转身的原因。
- 构图必须服从时，优先用首尾帧模式；人偶视频更适合用来定节奏、对动作顺序。

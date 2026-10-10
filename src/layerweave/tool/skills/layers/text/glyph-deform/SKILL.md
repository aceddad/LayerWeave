---
name: glyph-deform
description: 让文字变成有重量的物体：把字体的真实轮廓导出成密集的点，在 SVG 里逐点变形（受力、挤压、弯曲，力量从一个字传到下一个字）；先沿斜线切开再弯曲，得到真实的切口；用"到达、峰值、回弹"的定格式受力，代替一直晃动；把整个画面切成斜向窗格，带透视碎裂飞散。做动态字体、歌词字形动画、字和画面互动时使用。
---

# 字形变形

技法来自一部手书 PV 的动效小样（Pressure Study）。这里把它整理成通用的导出脚本和 React 组件，配合 [remotion-animate](../../movie/remotion-animate/SKILL.md) 模板使用。字形导出命令在本技能目录执行，React 组件复制到所创建的工程中使用。

依赖：导出脚本需要 `pip install -r requirements.txt`（fonttools）；组件只依赖 React。

字形 JSON 和渲染结果的目录由调用的 AI 按项目管理；先准备好目录，再显式传入输出路径，建议使用绝对路径。

## 1. 导出字形轮廓

```sh
python scripts/build_glyph_shapes.py 字体.ttf 输出.json 单词1 [单词2 ...] [--height cap|em]
```

- 拉丁字母用 `--height cap`（默认），以大写字母高度为 1000；中日韩文字用 `--height em`，以整个字身为 1000。
- 字间距保留字体自己的步进宽度和字偶距（kerning）；曲线细分成小段，直线也按最大长度切开。这样逐点变形时，轮廓会连续地弯曲，而不只是移动拐角。
- 只导出要用的单词，文件小。字体里缺字时会列出来，然后退出。
- 字体授权：导出的轮廓数据来自字体文件本身，分发作品前要确认这个字体允许嵌入或分发，例如 SIL OFL 字体。

## 2. 在 Remotion 里使用
把 `assets/GlyphWord.tsx` 复制进工程（例如 `src/ui/`），把 JSON 放进 `src/`，然后：

```tsx
import shapes from './title.json';
import {GlyphWord, impact} from './ui/GlyphWord';

<svg viewBox="0 0 1920 1080">
  <GlyphWord data={shapes} word="EXECUTION" x={160} y={430} w={1600} h={220} fill="#1d2025"
    warp={(x, y, i) => { const k = impact(t - hitAt - (8 - i) * 0.009); return [x + (1760 - x) * k * 0.1, y]; }}/>
</svg>
```

- `warp(x, y, 第几个字)`：逐点变形，返回新坐标。用"第几个字"给每个字加一点延迟，力量就会沿着单词传过去。
- `cut={{x, y, angle, keep: 'above' | 'below'}}`：先沿一条直线切开轮廓，再变形。同一个单词画两次，一次保留上半、一次保留下半，再各自移开，切口就是真切口。
- `impact(age)`：定格式的受力曲线。约 0.12 秒到达峰值，0.2 秒回弹，0.38 秒后归零。只在受力的那一下动。
- `<Panes count piece>{画面}</Panes>`：把同一份画面裁成斜向窗格，每格用 `piece(j)` 给出位移和旋转，带透视飞走；原来的接缝可以另外画出来留在原处。

完整的示例场景见 `assets/GlyphStudy.example.tsx`：受力传导、斜线切开分离、窗格碎裂三段，都按拍子触发。更多讲解见 [references/techniques.md](references/techniques.md)。

## 已测
- 导出脚本对 Arial Black 的输出，和原小样里的数据逐字段一致。等宽英文字体、中文字体（`--height em`）都能导出。
- 在 remotion-animate 模板里渲染了受力前、峰值、回弹后、切开、碎裂中的静帧，几种效果都按预期出现；中文字形也能正常绘制。

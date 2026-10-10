---
name: video-verify
description: 成片导出后做技术核验：逐帧解码确认完整、尺寸、帧率、时长、像素格式和色彩标注；给了参考音频时，在多个时间点测音画偏移（毫秒），并检查结尾是否静音；再出一张均匀取样的总览图。每次导出成片或母版后、上传前使用。
---

# 成片核验

依赖：`pip install -r requirements.txt`（av、numpy、Pillow）。从本技能目录运行。

总览图和 JSON 报告的输出目录由调用的 AI 自行选择并准备，保存时用 --sheet、--json 显式传入路径，建议使用绝对路径。只读取标准输出时不必创建结果文件。

```sh
python scripts/verify.py 成片.mp4 [--reference-audio 原曲.mp3] [--sheet 总览.jpg] [--samples 20] [--json 结果.json]
```

打印一份 JSON，各项含义：
- `frames_decoded`、`frames_declared`：实际解码出的帧数，和文件里声明的帧数。两者不一致时，会多一条 `warning`。
- `size`、`fps`、`duration_s`、`pix_fmt`：尺寸、帧率、时长、像素格式。
- `color`：色彩标注，包括 range、space、primaries、transfer，写法和 ffprobe 一致。`unknown` 表示文件里没写这一项，播放器只能自己猜。
- `audio_offset_ms`：在几个时间点上，成片音轨相对参考音频的偏移。正数表示成片的声音晚。各点一致说明整体平移了，各点不一致说明中途有漂移或有接缝。
- `tail_after_reference_s`、`tail_rms`：参考音频结束之后，成片还剩多长、响度多大，用来检查结尾是否静音。`body_rms` 是正片段的响度，作对比用。
- `--sheet`：按时间均匀取样，拼成一张总览图，每张上标出时间和帧号。打开看一眼，就能确认画面没有黑场、没有错段。

## 读结果
- 音画偏移一般要求在 1 帧以内（24 fps 时约 42 毫秒）。超出时，先确认导出时音频是不是重新编码过、片头有没有被裁掉。
- 偏移是靠互相关测出来的，参考音频要有变化（正常的音乐、人声都可以）。纯音、节拍器这类周期性的声音会让结果在几个周期之间跳来跳去，测不准。
- 色彩：网络发布的母版通常应是 `yuv420p`、range 为 `tv`、四项都是 `bt709`，做法见 video-master。
- 这些只是技术检查。节奏顺不顺、画面好不好，仍然要原速看、原速听。

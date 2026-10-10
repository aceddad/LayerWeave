---
name: audio-cues
description: 把一首歌用 Demucs 分成鼓、贝斯、人声、其他几轨，再从各轨提取"事件"并拟合拍子网格，得到卡点表：每一下鼓、每个音符和字的时间、帧号、第几小节第几拍、强弱，以及每轨逐帧的响度包络。做动画卡点、让画面跟节奏、检查画面是否落在拍子上时使用。
---

# 分轨与卡点表

从本技能目录运行。

分轨输出目录和卡点表的 --out 前缀由调用的 AI 按项目选择，先准备好目录，再显式传入，建议使用绝对路径。

依赖：`pip install -r requirements.txt`（demucs、librosa、numpy、scipy、soundfile）。Demucs 依赖 PyTorch，PyTorch 的版本要和 NumPy 匹配：NumPy 2 需要 PyTorch 2.3 及以上；用较旧的 PyTorch 时，要配 NumPy 1.x，否则会报 `Numpy is not available`。

## 1. 分轨（Demucs）

```sh
python -m demucs -n htdemucs -d cpu -j 2 -o 输出文件夹 歌曲.mp3
```

- 得到 4 轨：drums、bass、other、vocals，放在 `输出文件夹/htdemucs/歌曲名/` 下。用 `-n htdemucs_6s` 会多分出 guitar 和 piano。
- 首次运行会下载模型。用环境变量 `TORCH_HOME` 可以指定模型缓存的位置；`TEMP`/`TMP` 可以指定临时文件的位置。系统盘空间紧张时，可以把两者都指到别的盘。
- CPU 上，一首 3 分半的歌大约要 4 分钟。

## 2. 卡点表

```sh
python scripts/cues.py 分轨文件夹 [--fps 24] [--out 前缀]
```

- 输出 `前缀_cues.csv`，列为 time、frame、stem、kind、strength、bar、beat、sixteenth；以及 `前缀_cues.json`，里面有拍子网格、全部事件和每轨逐帧包络。包络可以直接用来驱动动画"跟节奏"。
- 鼓分成 kick（150 Hz 以下）、snare（150 Hz–2 kHz 的起音）、hat（6 kHz 以上）。贝斯和其他乐器给音符起点。人声给字（音节）、乐句开头（前面空出 0.4 秒以上）、长音（持续 0.5 秒以上）。
- 拍子网格用底鼓的真实起音来拟合：先由间隔估出大概的 BPM，再在 ±2% 范围内细搜 BPM 和相位。这比按整首混音来估更准。
- `beat0` 是小节头的位置：在 4 拍里取底鼓落得最多的那一拍。

## 已知情况
- 拍子网格：在真实歌曲上，用两种独立方法得到的结果一致；在合成的 124 BPM 测试曲上，测得 123.999 BPM，拍的相位误差在 3 毫秒以内。
- 小节头：底鼓每拍都有（four-on-the-floor）时，4 拍打成平手，小节头会落在任意一拍上。拍本身是准的，但"第几拍"可能整体错位，这时需要按歌曲结构人工核对。
- 各轨的起音检测（snare、hat、音符、字）没有用标准答案验证过。宽频的噪声类音色可能被同时计入 snare 和 hat。把它们当作参考；关键的卡点要回到音频确认。

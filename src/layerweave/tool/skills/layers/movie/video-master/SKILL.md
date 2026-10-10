---
name: video-master
description: 用 ffmpeg 把渲染导出的视频转成网络发布用的母版：yuv420p 限定范围、bt709 的矩阵、原色和传递特性都写好标注，H.264 高质量编码、faststart；也包括分段拼接、只替换其中一段（补丁段），以及用 ffprobe 核对标注。导出成片之后、上传之前使用，或者某个平台上颜色发生偏移时使用。
---

# 转码与出母版（ffmpeg）

需要 ffmpeg 和 ffprobe（7 及以上版本）。下面的命令都在 POSIX shell 里写；Windows 的 PowerShell 要把续行符 `\` 换成反引号。

母版和补丁成片的输出目录由调用的 AI 自行选择并准备；将示例中的输出文件名替换为包含目录的实际路径，建议使用绝对路径。

## 为什么要转
网页渲染器（例如 Remotion）导出的视频常常是 `yuvj420p`：全范围、bt601 矩阵，而且不写色彩标注。很多平台和播放器会按 bt709 限定范围来解读，于是颜色发生偏移。品红、青色这类饱和色最明显。

## 出母版

```sh
ffmpeg -hide_banner -y -i 导出.mp4 \
  -vf "scale=in_range=full:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p,setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709" \
  -c:v libx264 -preset slow -crf 14 -tune animation -profile:v high \
  -c:a copy -movflags +faststart 母版.mp4
```

- `scale=...`：真正转换像素的那一步，把全范围 bt601 换成限定范围 bt709。源文件已经是限定范围的话，把 `in_range` 改成 `tv`；源的矩阵是 bt709 的话，把 `in_color_matrix` 改成 `bt709`。
- `setparams=...`：把四项色彩标注写进帧里。新版 ffmpeg 的编码器以帧上带的属性为准，只在输出端写 `-color_primaries bt709 -color_trc bt709` 时，原色和传递特性可能不会写进文件（ffprobe 会显示 unknown），所以用 setparams。
- `-tune animation` 适合动画和平涂画面；实拍素材去掉这一项。`-crf 14` 质量很高，体积也大，平台还会再压一遍；体积要紧时可以放宽到 18 左右。
- 音频不重新编码时用 `-c:a copy`；需要转格式时用 `-c:a aac -b:a 320k`。

## 只替换其中一段（补丁段）
只重渲改动过的那一段，再和原片拼起来，同时转好色彩：

```sh
SC="scale=in_range=full:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p,setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709"
ffmpeg -hide_banner -y -t 补丁起点秒 -i 原片.mp4 -i 补丁段.mp4 -ss 补丁终点秒 -i 原片.mp4 -i 原片.mp4 \
  -filter_complex "[0:v]$SC[a];[1:v]$SC[b];[2:v]$SC[c];[a][b][c]concat=n=3:v=1:a=0[v]" \
  -map "[v]" -map 3:a -c:v libx264 -preset slow -crf 14 -tune animation -profile:v high -c:a copy -movflags +faststart 新母版.mp4
```

- 把 `-t`、`-ss` 写在输入前面，每段的时间戳都会从 0 开始，concat 才能无缝接上。
- 补丁段的起止要落在整帧上（时间 = 帧号 ÷ 帧率）。音频直接用原片的整条音轨，不参与拼接。
- 拼完用 [video-verify](../video-verify/SKILL.md) 核对总帧数和音画偏移。

## 核对标注

```sh
ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt,color_range,color_space,color_primaries,color_transfer -of default=nw=1 母版.mp4
```

期望看到：`pix_fmt=yuv420p`、`color_range=tv`，其余三项都是 `bt709`。

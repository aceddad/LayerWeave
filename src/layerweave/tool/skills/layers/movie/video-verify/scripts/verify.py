"""成片技术核验：解码是否完整、尺寸、帧率、时长、色彩标注；给了参考音频时，再测音画偏移和结尾静音；并出一张均匀取样的总览图。
只做技术检查，不代替原速看听。

python scripts/verify.py 成片.mp4 [--reference-audio 原曲.mp3] [--sheet 总览.jpg] [--samples 20] [--json 结果.json]
"""
import argparse
import json
import os

import av
import numpy as np
from PIL import Image, ImageDraw

SR = 48000
# FFmpeg 的色彩枚举值 → 名字（与 ffprobe 的写法一致）；unknown 表示文件里没有写标注
RANGES = {0: "unknown", 1: "tv", 2: "pc"}
SPACES = {0: "gbr", 1: "bt709", 2: "unknown", 4: "fcc", 5: "bt470bg", 6: "smpte170m", 7: "smpte240m", 9: "bt2020nc", 10: "bt2020c"}
PRIMARIES = {1: "bt709", 2: "unknown", 4: "bt470m", 5: "bt470bg", 6: "smpte170m", 7: "smpte240m", 9: "bt2020", 12: "smpte432"}
TRANSFERS = {1: "bt709", 2: "unknown", 4: "gamma22", 5: "gamma28", 6: "smpte170m", 8: "linear", 13: "iec61966-2-1",
             14: "bt2020-10", 15: "bt2020-12", 16: "smpte2084", 18: "arib-std-b67"}


def _name(value, table):
    if value is None:
        return "unknown"
    if hasattr(value, "name"):
        return str(value.name).lower()
    return table.get(int(value), str(value))


def mono_audio(path):
    container = av.open(path)
    if not container.streams.audio:
        return None
    resampler = av.AudioResampler(format="flt", layout="mono", rate=SR)
    chunks = []
    for frame in container.decode(audio=0):
        for out in resampler.resample(frame):
            chunks.append(out.to_ndarray().ravel())
    return np.concatenate(chunks) if chunks else None


def offsets(film, reference, duration, points=5, window=1.0, search=0.1):
    """在几个时间点上，用互相关测成片音轨相对参考音频的偏移（毫秒；正数表示成片晚）。"""
    span, pad = int(window * SR), int(search * SR)
    usable = min(len(film), len(reference)) / SR - window - search
    result = []
    for at in np.linspace(search + 1, max(search + 1, usable - 1), points):
        start = int(at * SR)
        segment = reference[start:start + span]
        window_audio = film[start - pad:start + span + pad]
        if len(segment) < span or len(window_audio) < span + 2 * pad or segment.std() < 1e-4:
            continue
        corr = np.correlate(window_audio, segment, "valid")
        result.append({"at_s": round(float(at), 2), "offset_ms": round((int(np.argmax(corr)) - pad) / SR * 1000, 2)})
    return result


def main():
    p = argparse.ArgumentParser(description="成片技术核验")
    p.add_argument("video")
    p.add_argument("--reference-audio", help="原曲或定稿音频；给了就测音画偏移和结尾静音")
    p.add_argument("--sheet", help="总览图输出路径（jpg）")
    p.add_argument("--samples", type=int, default=20, help="总览图取样张数，均匀分布")
    p.add_argument("--json", help="结果另存为 JSON")
    a = p.parse_args()

    container = av.open(a.video)
    stream = container.streams.video[0]
    ctx = stream.codec_context
    fps = float(stream.average_rate)
    report = {"size": [ctx.width, ctx.height], "fps": fps, "pix_fmt": ctx.pix_fmt,
              "color": {"range": _name(ctx.color_range, RANGES), "space": _name(ctx.colorspace, SPACES),
                        "primaries": _name(ctx.color_primaries, PRIMARIES), "transfer": _name(ctx.color_trc, TRANSFERS)}}
    declared = int(stream.frames or 0)
    decoded = sum(1 for _ in container.decode(video=0))   # 逐帧解码一遍，确认没有坏帧、不提前结束
    report.update(frames_decoded=decoded, frames_declared=declared or None, duration_s=round(decoded / fps, 3))
    if declared and declared != decoded:
        report["warning"] = f"声明 {declared} 帧，实际解码 {decoded} 帧"

    if a.sheet:
        picks = sorted(set(int(round(x)) for x in np.linspace(0, decoded - 1, a.samples)))
        thumbs = {}
        container = av.open(a.video)
        for i, frame in enumerate(container.decode(video=0)):
            if i in picks:
                thumbs[i] = frame.to_image().resize((480, int(480 * ctx.height / ctx.width)))
        w, h, cols = 480, int(480 * ctx.height / ctx.width), 5
        sheet = Image.new("RGB", (w * cols, h * ((len(picks) + cols - 1) // cols)), "#222")
        draw = ImageDraw.Draw(sheet)
        for k, i in enumerate(picks):
            x, y = (k % cols) * w, (k // cols) * h
            sheet.paste(thumbs[i], (x, y))
            s = i / fps
            draw.text((x + 6, y + 4), f"{int(s // 60)}:{s % 60:05.2f}  f{i}", fill="yellow")
        sheet.save(a.sheet, quality=86)
        report["sheet"] = a.sheet

    film = mono_audio(a.video)
    report["audio"] = film is not None
    if film is not None and a.reference_audio:
        reference = mono_audio(a.reference_audio)
        report["audio_offset_ms"] = offsets(film, reference, decoded / fps)
        ref_end = len(reference) / SR
        tail = film[int(ref_end * SR):]
        body = film[int(min(20, ref_end * 0.1) * SR):int(ref_end * 0.9 * SR)]
        report["reference_duration_s"] = round(ref_end, 3)
        report["tail_after_reference_s"] = round(len(tail) / SR, 3)
        report["tail_rms"] = round(float(np.sqrt((tail ** 2).mean())), 6) if len(tail) else 0.0
        report["body_rms"] = round(float(np.sqrt((body ** 2).mean())), 6) if len(body) else None

    text = json.dumps(report, ensure_ascii=False, indent=1)
    print(text)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as handle:
            handle.write(text)


if __name__ == "__main__":
    main()

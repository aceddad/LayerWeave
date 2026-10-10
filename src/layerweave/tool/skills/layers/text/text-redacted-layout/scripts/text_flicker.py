"""找文字层闪烁：把"带字的成片"和"不带字的底片"逐帧做差，得到每帧文字的像素面积。
面积在相邻帧之间忽有忽无（A → 几乎 0 → A，或 0 → A → 0）就是闪烁。只输出数字，不输出画面。

python scripts/text_flicker.py 底片.mp4 带字版.mp4 [另一个带字版.mp4 ...] [--threshold 40] [--min-area 300]
两个文件要同尺寸、同帧率、逐帧对齐（同一个工程分别导出带字和不带字的版本）。
"""
import argparse

import av
import numpy as np


def areas(base, text, threshold):
    a, b = av.open(base), av.open(text)
    fps = float(b.streams.video[0].average_rate)
    out = []
    for fa, fb in zip(a.decode(video=0), b.decode(video=0)):
        x = np.asarray(fa.to_image().convert("L").resize((480, 270)), dtype=np.int16)
        y = np.asarray(fb.to_image().convert("L").resize((480, 270)), dtype=np.int16)
        out.append(int((np.abs(x - y) > threshold).sum()))
    return np.array(out), fps


def main():
    p = argparse.ArgumentParser(description="文字层闪烁扫描")
    p.add_argument("base", help="不带文字的底片")
    p.add_argument("texts", nargs="+", help="带文字的版本，可以多个")
    p.add_argument("--threshold", type=int, default=40, help="像素灰度差超过它才算文字像素（0–255）")
    p.add_argument("--min-area", type=int, default=300, help="两侧至少有这么多文字像素才判断（按 480×270 计）")
    a = p.parse_args()
    for path in a.texts:
        ar, fps = areas(a.base, path, a.threshold)
        print(f"== {path}  frames={len(ar)}")
        flick = []
        for i in range(1, len(ar) - 1):
            lo, hi = ar[i], min(ar[i - 1], ar[i + 1])
            if hi > a.min_area and lo < hi * 0.35:                       # 中间一帧明显少：掉帧式闪烁
                flick.append((i, "drop", ar[i - 1], ar[i], ar[i + 1]))
            elif ar[i] > a.min_area and max(ar[i - 1], ar[i + 1]) < ar[i] * 0.35 and min(ar[i - 1], ar[i + 1]) > 0:
                flick.append((i, "spike", ar[i - 1], ar[i], ar[i + 1]))  # 中间一帧明显多：残影式闪烁
        print("suspect frames:", len(flick))
        for i, kind, before, now, after in flick[:40]:
            print(f"  {i / fps:7.2f}s f{i} {kind}: {before} -> {now} -> {after}")


if __name__ == "__main__":
    main()

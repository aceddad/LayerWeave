"""嘴型变体 → 只取嘴的那一小块，对齐、调色后贴回原图，保证换嘴时脸的其他部分一像素都不动。
用法：python -X utf8 scripts/lip_patch.py 原图.png 变体.png 输出.png cx cy rx ry [--alpha]
cx cy rx ry：嘴部椭圆（原图像素）。先在嘴周围（不含嘴）用模板匹配找变体相对原图的偏移，再按椭圆羽化贴回。
--alpha：原图是透明图时，输出沿用原图的透明通道。"""
import sys

import numpy as np
from PIL import Image, ImageFilter

base_p, var_p, out_p, cx, cy, rx, ry = sys.argv[1:8]
cx, cy, rx, ry = int(cx), int(cy), int(rx), int(ry)
use_alpha = "--alpha" in sys.argv
base = Image.open(base_p).convert("RGBA")
var = Image.open(var_p).convert("RGBA").resize(base.size)
B = np.asarray(base, dtype=np.float32)[..., :3]
V = np.asarray(var, dtype=np.float32)[..., :3]
# 对齐：取嘴周围 3 倍大小的区域（挖掉嘴本身），在 ±40 像素内找最小差
R = 3
SR = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--search=")), 40))
x0, x1, y0, y1 = cx - rx * R, cx + rx * R, cy - ry * R, cy + ry * R
yy, xx = np.mgrid[y0:y1, x0:x1]
ring = (((xx - cx) / (rx * 1.3)) ** 2 + ((yy - cy) / (ry * 1.6)) ** 2) > 1
AL = np.asarray(base, dtype=np.float32)[..., 3]
if use_alpha:
    ring &= AL[y0:y1, x0:x1] > 250
g = lambda a: a.mean(axis=2)
Bg = g(B)
Vg = g(V)
best = (1e18, 0, 0)
for dy in range(-SR, SR + 1, 2):
    for dx in range(-SR, SR + 1, 2):
        d = np.abs(Bg[y0:y1, x0:x1] - Vg[y0 + dy:y1 + dy, x0 + dx:x1 + dx])[ring].mean()
        if d < best[0]:
            best = (d, dx, dy)
_, bx, by = best
for dy in range(by - 2, by + 3):
    for dx in range(bx - 2, bx + 3):
        d = np.abs(Bg[y0:y1, x0:x1] - Vg[y0 + dy:y1 + dy, x0 + dx:x1 + dx])[ring].mean()
        if d < best[0]:
            best = (d, dx, dy)
_, dx, dy = best
print("偏移", dx, dy, "残差", round(best[0], 2))
shifted = np.roll(np.roll(V, -dy, axis=0), -dx, axis=1)
# 调色：在环上让均值、方差一致
Vs = shifted.copy()
for c in range(3):
    b, v = B[y0:y1, x0:x1, c][ring], shifted[y0:y1, x0:x1, c][ring]
    Vs[..., c] = (shifted[..., c] - v.mean()) / (v.std() + 1e-6) * b.std() + b.mean()
# 羽化椭圆
H, W = Bg.shape
m = Image.new("L", (W, H), 0)
from PIL import ImageDraw
ImageDraw.Draw(m).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
m = np.asarray(m.filter(ImageFilter.GaussianBlur(max(rx, ry) * 0.25)), dtype=np.float32)[..., None] / 255
if use_alpha:
    m = m * (AL[..., None] / 255) ** 4
out = B * (1 - m) + np.clip(Vs, 0, 255) * m
a = np.asarray(base, dtype=np.float32)[..., 3:] if use_alpha else np.full((H, W, 1), 255, np.float32)
Image.fromarray(np.concatenate([out, a], axis=2).astype(np.uint8), "RGBA" if use_alpha else "RGBA").convert("RGBA" if use_alpha else "RGB").save(out_p)
print("写好", out_p)

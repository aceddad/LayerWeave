"""把一张图（或其中一块）转成网点画：亮处大点、暗处无点，交错排列，透明或纯色底。
同时可以导出每颗点的坐标和半径，供动画代码一颗颗画（聚拢、散开、逐颗出现）。

python scripts/halftone.py 输入.png 输出.png [--crop x0 y0 x1 y1] [--size 1920x1080] [--cell 14]
                           [--color #FF2E88] [--background 透明|#000000] [--dots 点.json]
                           [--black 0.18] [--range 0.7] [--gamma 1.3] [--invert] [--blur 1.5]
"""
import argparse
import json

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFilter


def luminance(path, crop, size, blur, black, span, gamma, invert):
    image = Image.open(path).convert("L")
    if crop:
        image = image.crop(tuple(crop))
    image = image.resize(size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(blur))
    lum = np.asarray(image).astype(np.float32) / 255
    if invert:
        lum = 1 - lum
    return np.clip((lum - black) / span, 0, 1) ** gamma   # 拉开对比：亮部成为大点，暗部消失


def dots(lum, cell, scale=0.62, minimum=0.6):
    height, width = lum.shape
    found = []
    for cy in range(cell // 2, height, cell):
        offset = (cy // cell % 2) * cell // 2                # 隔行错开半格
        for cx in range(cell // 2 + offset, width, cell):
            r = float(lum[min(cy, height - 1), min(cx, width - 1)]) * cell * scale
            if r > minimum:
                found.append([cx, cy, round(r, 1)])
    return found


def size_arg(text):
    w, h = text.lower().split("x")
    return int(w), int(h)


def main():
    p = argparse.ArgumentParser(description="图片转网点画")
    p.add_argument("input"); p.add_argument("output")
    p.add_argument("--crop", nargs=4, type=int, metavar=("X0", "Y0", "X1", "Y1"), help="先裁出这一块再转换")
    p.add_argument("--size", type=size_arg, default=(1920, 1080), help="输出尺寸，默认 1920x1080")
    p.add_argument("--cell", type=int, default=14, help="网格间距（像素），越大点越粗")
    p.add_argument("--color", default="#FF2E88", help="点的颜色")
    p.add_argument("--background", default="transparent", help="transparent 或颜色，例如 #000000")
    p.add_argument("--dots", help="另存每颗点的 [x, y, 半径] 列表（JSON）")
    p.add_argument("--black", type=float, default=0.18, help="亮度低于它的地方不出点（0–1）")
    p.add_argument("--range", type=float, default=0.7, dest="span", help="对比拉伸的范围（0–1）")
    p.add_argument("--gamma", type=float, default=1.3, help="大于 1 时，中间调的点变小")
    p.add_argument("--invert", action="store_true", help="反相：暗处出大点（白底黑点的效果）")
    p.add_argument("--blur", type=float, default=1.5, help="转换前的高斯模糊半径，去掉细碎噪点")
    a = p.parse_args()

    lum = luminance(a.input, a.crop, a.size, a.blur, a.black, a.span, a.gamma, a.invert)
    found = dots(lum, a.cell)
    fill = ImageColor.getrgb(a.color) + (255,)
    background = (0, 0, 0, 0) if a.background == "transparent" else ImageColor.getrgb(a.background) + (255,)
    out = Image.new("RGBA", a.size, background)
    draw = ImageDraw.Draw(out)
    for cx, cy, r in found:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)
    out.save(a.output)
    if a.dots:
        with open(a.dots, "w", encoding="utf-8") as handle:
            json.dump(found, handle, separators=(",", ":"))
    print(json.dumps({"output": a.output, "dots": len(found), "cell": a.cell, "size": list(a.size)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

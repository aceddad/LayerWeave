"""把几张图放到同一张网点网格上，导出每一格在每张图里的半径。
同一格在不同图里一一对应，动画里就能在两张图之间逐点过渡（例如闭眼 → 睁眼、一张画渐变成另一张）。

python scripts/halftone_grid.py 输出.json 图1.png 图2.png [...] [--crop x0 y0 x1 y1] [--size 1920x1080] [--cell 14]
                               [--black 0.18] [--range 0.7] [--gamma 1.3] [--invert] [--blur 1.5]
输出：{"cell", "cols", "rows", "frames": [[半径×10 取整, ...], ...]}，每张图一组，按行优先排列；奇数行错开半格。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from halftone import luminance, size_arg  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="多张图共用一张网点网格")
    p.add_argument("output"); p.add_argument("images", nargs="+")
    p.add_argument("--crop", nargs=4, type=int, metavar=("X0", "Y0", "X1", "Y1"))
    p.add_argument("--size", type=size_arg, default=(1920, 1080))
    p.add_argument("--cell", type=int, default=14)
    p.add_argument("--black", type=float, default=0.18)
    p.add_argument("--range", type=float, default=0.7, dest="span")
    p.add_argument("--gamma", type=float, default=1.3)
    p.add_argument("--invert", action="store_true")
    p.add_argument("--blur", type=float, default=1.5)
    a = p.parse_args()

    width, height = a.size
    cols, rows = width // a.cell, height // a.cell
    frames = []
    for path in a.images:
        lum = luminance(path, a.crop, a.size, a.blur, a.black, a.span, a.gamma, a.invert)
        radii = []
        for j in range(rows):
            for i in range(cols):
                cx = i * a.cell + a.cell // 2 + (j % 2) * a.cell // 2
                cy = j * a.cell + a.cell // 2
                r = float(lum[min(cy, height - 1), min(cx, width - 1)]) * a.cell * 0.62
                radii.append(int(round(r * 10)) if r > 0.6 else 0)
        frames.append(radii)
        print(f"{path}: {sum(1 for r in radii if r)} 颗点", file=sys.stderr)
    with open(a.output, "w", encoding="utf-8") as handle:
        json.dump({"cell": a.cell, "cols": cols, "rows": rows, "frames": frames}, handle, separators=(",", ":"))
    print(json.dumps({"output": a.output, "images": len(frames), "cols": cols, "rows": rows}, ensure_ascii=False))


if __name__ == "__main__":
    main()

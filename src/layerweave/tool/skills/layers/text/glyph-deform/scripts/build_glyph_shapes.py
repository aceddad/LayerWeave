"""把字体里的真实字形轮廓导出成可变形的点列（JSON），供 GlyphWord 组件逐点弯曲、切开、拉伸。

python scripts/build_glyph_shapes.py 字体.ttf 输出.json 单词1 [单词2 ...] [--height cap|em] [--curve-steps 20] [--max-segment 50]

坐标约定（与 GlyphWord.tsx 一致）：
- 高度单位：参考高度 = 1000。`--height cap` 用大写字母高度（拉丁字母合适），`--height em` 用整个字身（中日韩文字合适）。
- y 向下，0 在参考高度的顶边；圆形字母会略微超出 0..1000（字体原有的过冲）。
- 每个字形的点从它自己的墨迹左边缘起算；glyph.x 把这个左边缘放进单词里。单词宽度取外侧墨迹范围。
- 字间距来自字体自己的步进宽度和字偶距（kerning），不是等宽格子。
- 曲线被细分成小直线段，直线段也按最大长度切开，这样逐点变形时轮廓会连续弯曲，而不是只移动拐角。
"""
import argparse
import json
import math
import sys

from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

REFERENCE = 1000


class FlatOutlinePen(BasePen):
    """把轮廓压平成闭合点列；曲线按 curve_steps 细分，直线按 max_segment 切开。"""

    def __init__(self, glyph_set, left, top, scale, curve_steps, max_segment):
        super().__init__(glyph_set)
        self.left, self.top, self.scale = left, top, scale
        self.curve_steps, self.max_segment = curve_steps, max_segment
        self.contours, self.points = [], []
        self.current = self.start = (0.0, 0.0)

    def append(self, point):
        mapped = [round((point[0] - self.left) * self.scale, 2), round((self.top - point[1]) * self.scale, 2)]
        if not self.points or mapped != self.points[-1]:
            self.points.append(mapped)
        self.current = point

    def _moveTo(self, point):
        if self.points:
            self._closePath()
        self.start = point
        self.append(point)

    def _lineTo(self, point):
        begin = self.current
        steps = max(1, math.ceil(math.dist(begin, point) * self.scale / (self.max_segment - 0.02)))
        for i in range(1, steps + 1):
            a = i / steps
            self.append((begin[0] + (point[0] - begin[0]) * a, begin[1] + (point[1] - begin[1]) * a))

    def _qCurveToOne(self, control, end):
        begin = self.current
        for i in range(1, self.curve_steps + 1):
            a, b = i / self.curve_steps, 1 - i / self.curve_steps
            self.append((b * b * begin[0] + 2 * b * a * control[0] + a * a * end[0],
                         b * b * begin[1] + 2 * b * a * control[1] + a * a * end[1]))

    def _curveToOne(self, c1, c2, end):
        begin = self.current
        for i in range(1, self.curve_steps + 1):
            a, b = i / self.curve_steps, 1 - i / self.curve_steps
            self.append((b ** 3 * begin[0] + 3 * b * b * a * c1[0] + 3 * b * a * a * c2[0] + a ** 3 * end[0],
                         b ** 3 * begin[1] + 3 * b * b * a * c1[1] + 3 * b * a * a * c2[1] + a ** 3 * end[1]))

    def _closePath(self):
        self._lineTo(self.start)
        if len(self.points) >= 4:
            self.contours.append(self.points)
        self.points = []

    _endPath = _closePath


def kerning_pairs(font):
    """读取水平字偶距：GPOS kern 的 PairPos（格式 1、2）里的 XAdvance；没有时退回旧式 kern 表。"""
    pairs = {}
    if "GPOS" in font and font["GPOS"].table.FeatureList:
        table = font["GPOS"].table
        indices = {i for record in table.FeatureList.FeatureRecord if record.FeatureTag == "kern"
                   for i in record.Feature.LookupListIndex}
        for index in indices:
            lookup = table.LookupList.Lookup[index]
            subtables = lookup.SubTable
            if lookup.LookupType == 9:   # 扩展查找：取出里面真正的子表
                subtables = [s.ExtSubTable for s in subtables]
            for sub in subtables:
                if getattr(sub, "LookupType", 2) != 2 or not sub.ValueFormat1 & 4:
                    continue
                if sub.Format == 1:
                    for first, pair_set in zip(sub.Coverage.glyphs, sub.PairSet):
                        for record in pair_set.PairValueRecord:
                            key = (first, record.SecondGlyph)
                            pairs[key] = pairs.get(key, 0) + (record.Value1.XAdvance or 0)
                elif sub.Format == 2:
                    class1, class2 = sub.ClassDef1.classDefs, sub.ClassDef2.classDefs
                    firsts = sub.Coverage.glyphs
                    seconds = font.getGlyphOrder()
                    for first in firsts:
                        row = sub.Class1Record[class1.get(first, 0)]
                        for second in seconds:
                            value = row.Class2Record[class2.get(second, 0)].Value1
                            if value is not None and value.XAdvance:
                                key = (first, second)
                                pairs.setdefault(key, value.XAdvance)
        if pairs:
            return pairs, "GPOS kern"
    if "kern" in font:
        for table in font["kern"].kernTables:
            if getattr(table, "coverage", 1) & 1:
                for key, value in table.kernTable.items():
                    pairs[key] = pairs.get(key, 0) + value
        return pairs, "kern table"
    return pairs, "none"


def build(font_path, words, height, curve_steps, max_segment):
    font = TTFont(font_path)
    glyph_set, cmap = font.getGlyphSet(), font.getBestCmap()
    os2 = font["OS/2"] if "OS/2" in font else None
    if height == "cap":
        ref = getattr(os2, "sCapHeight", 0) or 0
        if ref <= 0:
            sys.exit("这个字体没有大写字母高度（sCapHeight）；中日韩字体请用 --height em")
        top = ref
    else:
        ascent = getattr(os2, "sTypoAscender", 0) or font["hhea"].ascent
        descent = getattr(os2, "sTypoDescender", 0) or font["hhea"].descent
        ref, top = ascent - descent, ascent
    scale = REFERENCE / ref
    kern, kern_source = kerning_pairs(font)
    missing = sorted({c for c in "".join(words) if ord(c) not in cmap and not c.isspace()})
    if missing:
        sys.exit("字体里没有这些字：" + " ".join(missing))

    outlines = {}
    for char in sorted(set("".join(words))):
        name = cmap.get(ord(char))
        if name is None:
            continue
        bounds = BoundsPen(glyph_set)
        glyph_set[name].draw(bounds)
        advance = font["hmtx"][name][0]
        if bounds.bounds is None:   # 空格等没有墨迹的字
            outlines[char] = {"name": name, "left": 0, "width": 0, "advance": advance, "contours": []}
            continue
        left, _, right, _ = bounds.bounds
        pen = FlatOutlinePen(glyph_set, left, top, scale, curve_steps, max_segment)
        glyph_set[name].draw(pen)
        outlines[char] = {"name": name, "left": left, "width": (right - left) * scale, "advance": advance, "contours": pen.contours}

    data = {"source": {"font": font["name"].getDebugName(1), "unitsPerEm": font["head"].unitsPerEm,
                       "height": height, "reference": REFERENCE, "kerning": kern_source,
                       "curveSteps": curve_steps, "maxSegment": max_segment,
                       "coordinates": "y 向下；0 在参考高度顶边；glyph.x 放置该字墨迹左边缘；单词宽度为外侧墨迹范围"},
            "words": {}}
    for word in words:
        glyphs, pen_x, previous = [], 0.0, None
        for char in word:
            shape = outlines[char]
            if previous is not None:
                pen_x += kern.get((previous, shape["name"]), 0)
            if shape["contours"]:
                glyphs.append({"char": char, "x": (pen_x + shape["left"]) * scale,
                               "width": round(shape["width"], 2), "contours": shape["contours"]})
            pen_x += shape["advance"]
            previous = shape["name"]
        left = min(g["x"] for g in glyphs)
        right = max(g["x"] + g["width"] for g in glyphs)
        for g in glyphs:
            g["x"] = round(g["x"] - left, 2)
        data["words"][word] = {"width": round(right - left, 2), "height": REFERENCE, "glyphs": glyphs}
    return data


def main():
    p = argparse.ArgumentParser(description="导出可变形的字形轮廓")
    p.add_argument("font"); p.add_argument("output"); p.add_argument("words", nargs="+")
    p.add_argument("--height", choices=("cap", "em"), default="cap", help="参考高度：cap=大写字母高度，em=整个字身（中日韩用）")
    p.add_argument("--curve-steps", type=int, default=20, help="每段曲线细分成几段")
    p.add_argument("--max-segment", type=float, default=50, help="直线段的最大长度（参考高度 1000 下）")
    a = p.parse_args()
    data = build(a.font, a.words, a.height, a.curve_steps, a.max_segment)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    with open(a.output, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    for word, shape in data["words"].items():
        points = sum(len(c) for g in shape["glyphs"] for c in g["contours"])
        print(f"{word}: 宽 {shape['width']:.0f}（高 1000），{len(shape['glyphs'])} 个字形，{points} 个点")
    print(f"字偶距：{data['source']['kerning']}；输出 {a.output}（{len(text.encode('utf-8')):,} 字节）")


if __name__ == "__main__":
    main()

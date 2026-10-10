"""涂黑字体：把字体里每个可见字形换成一个方块，但保留原来的字宽（advance width）和字距。
排版、断行、沿路径长度与原字体完全一致，只是字认不出来——用来在不显示歌词的情况下检查歌词层的版式。
用法：python make_redacted_font.py <输入.ttf> <输出.ttf>"""
import sys
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen

src, dst = sys.argv[1], sys.argv[2]
f = TTFont(src)
upm = f["head"].unitsPerEm
os2 = f["OS/2"] if "OS/2" in f else None
x_h = getattr(os2, "sxHeight", 0) or int(upm * 0.5)
cap = getattr(os2, "sCapHeight", 0) or int(upm * 0.7)
cmap = f.getBestCmap()
glyf, hmtx = f["glyf"], f["hmtx"]

done = set()
for code, name in cmap.items():
    ch = chr(code)
    if ch.isspace() or name in done or name not in glyf.glyphs:
        continue
    adv, lsb = hmtx[name]
    if adv <= 0:
        continue
    top = cap if (ch.isupper() or ch.isdigit()) else x_h
    if not ch.isalnum():
        top = int(x_h * 0.45)  # 标点：小方块
    pen = TTGlyphPen(None)
    x0, x1 = int(adv * 0.1), int(adv * 0.9)
    pen.moveTo((x0, 0))
    pen.lineTo((x0, top))
    pen.lineTo((x1, top))
    pen.lineTo((x1, 0))
    pen.closePath()
    glyf[name] = pen.glyph()
    hmtx[name] = (adv, x0)
    done.add(name)
f.save(dst)
print("redacted", len(done), "glyphs ->", dst)

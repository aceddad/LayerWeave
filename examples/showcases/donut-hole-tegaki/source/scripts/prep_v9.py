"""v9 用的素材：按素材目录编号取图，透明图裁到内容边界，记下它在原构图里的位置（舞台 1920×1080 坐标）。
用法：python -X utf8 scripts/prep_v9.py  → 05_素材/v9/NNNN.webp、src/data/v9_assets.json
背景图存成舞台尺寸的 1.5 倍（推近时不糊）；透明图按原分辨率裁切（舞台坐标 = 原像素 × 1920/原宽）。"""
import json
from pathlib import Path

from PIL import Image

WS = Path("D:/AiDefaultWorkSpace/claude")
PROJ = WS / "01_项目/2026-10_手书_甜甜圈洞_重开"
OUT = PROJ / "05_素材/v9"
OUT.mkdir(exist_ok=True)
items = {i["id"]: i for i in json.loads((PROJ / "05_素材/素材目录/目录_标注.json").read_text(encoding="utf-8"))}

def rng(a, b):
    return list(range(a, b + 1))

IDS = (rng(1, 109) + rng(110, 127) + rng(1036, 1042) + rng(1242, 1259) + rng(1269, 1314) + rng(306, 313)
       + [191, 192, 193, 194, 1080, 1078, 1339])
# 额外：生成的嘴型变体（存在才处理）
EXTRA = {f"g{k}": PROJ / f"05_素材/_候选/v9/{k}.png" for k in ("050_m0", "050_m1", "047_m1", "047_m2", "055_m1", "055_m2")}

manifest = json.loads((PROJ / "03_草稿/网页原型/src/data/v9_assets.json").read_text(encoding="utf-8")) if (PROJ / "03_草稿/网页原型/src/data/v9_assets.json").exists() else {}

def put(key, path):
    dst = OUT / f"{key}.webp"
    im = Image.open(path)
    W, H = im.size
    k = 1920 / W if W <= 3840 else 0.5          # 横长图（5760 宽）：舞台宽 2880
    alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    if alpha:
        im = im.convert("RGBA")
        bb = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox() or (0, 0, W, H)
        crop = im.crop(bb)
        # 透明图存原分辨率，但最长边不超过 3000
        s = min(1, 3000 / max(crop.size))
        if s < 1:
            crop = crop.resize((round(crop.width * s), round(crop.height * s)), Image.LANCZOS)
        if not dst.exists() or dst.stat().st_mtime < path.stat().st_mtime:
            crop.save(dst, quality=90, method=5)
        box = [bb[0] * k, bb[1] * k, (bb[2] - bb[0]) * k, (bb[3] - bb[1]) * k]
    else:
        im = im.convert("RGB")
        sw, sh = W * k, H * k
        s = min(1, (sw * 1.5) / W)
        if not dst.exists() or dst.stat().st_mtime < path.stat().st_mtime:
            (im.resize((round(W * s), round(H * s)), Image.LANCZOS) if s < 1 else im).save(dst, quality=88, method=5)
        box = [0, 0, sw, sh]
    manifest[key] = {"box": [round(v, 1) for v in box], "alpha": alpha}

for i in IDS:
    put(f"{i:04d}", WS / items[i]["path"])
for key, p in EXTRA.items():
    if p.exists():
        put(key, p)
(PROJ / "03_草稿/网页原型/src/data/v9_assets.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=0), encoding="utf-8")
print(len(manifest), "张 →", OUT)

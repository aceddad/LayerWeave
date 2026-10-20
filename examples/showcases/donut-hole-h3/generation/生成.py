"""H3 演示：按镜头表准备首尾帧、提交 H3（2K）、抽帧检查。
用法：python -X utf8 生成.py 阶段 [镜头号 …]
  帧   — 从 astra 交付取关键帧，存成 JPEG（透明人物叠到底色 / 背景上，横长图裁右侧 16:9）
  视频 — 提交 H3，4 路并行；已有的 mp4 跳过（花钱：2K 0.15 元/秒）
  检查 — 每段抽 8 帧拼一张图（03_草稿/检查/）
  接入 — 1080p、全关键帧，给网页原型用（05_素材/视频_接入/）"""
import importlib.util
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
WS = Path("D:/AiDefaultWorkSpace/claude")
ASTRA = WS / "01_项目/2026-10_手书_甜甜圈洞_重开/05_素材/astra交付/v6"
H3 = WS / ".claude/skills/gen-video/scripts/h3.py"
FF = WS / "02_素材库/工具/ffmpeg/bin/ffmpeg.exe"
FR, PR, VID, CHK = HERE / "首尾帧", HERE / "提示词", PROJ / "05_素材/视频", HERE / "检查"
spec = importlib.util.spec_from_file_location("t", HERE / "镜头表.py")
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)


def find(name):
    if name.startswith("补:"):
        return HERE / "关键帧补图" / f"{name[2:]}.png"
    for d in ("delivery", "composites"):
        p = ASTRA / d / f"{name}.png"
        if p.exists():
            return p
    raise FileNotFoundError(name)


def frame(desc, crop=None):
    """'名字' / '透明名+#色' / '透明名+背景名' → RGB 图"""
    if "+" in desc:
        fg, bg = desc.split("+")
        fgi = Image.open(find(fg)).convert("RGBA")
        base = Image.new("RGBA", fgi.size, bg) if bg.startswith("#") else Image.open(find(bg)).convert("RGBA").resize(fgi.size)
        base.alpha_composite(fgi)
        im = base.convert("RGB")
    else:
        im = Image.open(find(desc)).convert("RGB")
    if im.width / im.height > 2.0:                          # 横长图：取右侧（舞台所在）16:9
        h = im.height; w = round(h * 16 / 9)
        im = im.crop((im.width - w, 0, im.width, h)) if crop == "right" else im.crop(((im.width - w) // 2, 0, (im.width + w) // 2, h))
    if im.width > 3840:
        im = im.resize((3840, round(3840 * im.height / im.width)), Image.LANCZOS)
    return im


def prep(n):
    s = T.SHOTS[n]
    for key in ("first", "last"):
        if key in s:
            frame(s[key], s.get("crop")).save(FR / f"{n:02d}_{key}.jpg", quality=93)
    (PR / f"{n:02d}.txt").write_text(T.STYLE + T.FIXED + s["prompt"], encoding="utf-8")
    return n, "ok"


def submit(n):
    s = T.SHOTS[n]
    out = VID / f"镜{n:02d}.mp4"
    if out.exists():
        return n, "已有"
    cmd = ["python", "-X", "utf8", str(H3), "submit", str(out), str(PR / f"{n:02d}.txt"), "--first", str(FR / f"{n:02d}_first.jpg"),
           "--duration", str(s["dur"]), "--resolution", "2K"]
    if "last" in s:
        cmd += ["--last", str(FR / f"{n:02d}_last.jpg")]
    for attempt in range(3):
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = (p.stdout + p.stderr).strip().splitlines()[-1:] or [""]
        if out.exists():
            return n, tail[0][:120]
        if "429" not in p.stdout + p.stderr and "并发" not in p.stdout + p.stderr:
            return n, "失败 " + tail[0][:200]
    return n, "失败（并发）"


def check(n):
    v = VID / f"镜{n:02d}.mp4"
    if not v.exists():
        return n, "没有视频"
    tmp = CHK / f"_{n:02d}"
    tmp.mkdir(exist_ok=True)
    subprocess.run([str(FF), "-y", "-loglevel", "error", "-i", str(v), "-vf", "fps=2,scale=480:-1", str(tmp / "%02d.jpg")])
    fs = sorted(tmp.glob("*.jpg"))
    fs = [fs[round(i * (len(fs) - 1) / 7)] for i in range(8)] if len(fs) >= 8 else fs
    ims = [Image.open(f) for f in fs]
    w, h = ims[0].size
    sheet = Image.new("RGB", (w * 4, h * 2))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % 4) * w, (i // 4) * h))
    sheet.save(CHK / f"镜{n:02d}.jpg", quality=82)
    for f in tmp.glob("*.jpg"):
        f.unlink()
    tmp.rmdir()
    return n, "ok"


def adapt(n):
    """接入：缩到 1080p、轻锐化、每帧都是关键帧（浏览器按 t 逐帧拨时间要准）、去掉声音"""
    v = VID / f"镜{n:02d}.mp4"
    out = PROJ / "05_素材/视频_接入" / f"镜{n:02d}.mp4"
    if not v.exists():
        return n, "没有视频"
    if out.exists() and out.stat().st_mtime > v.stat().st_mtime:
        return n, "已有"
    subprocess.run([str(FF), "-y", "-loglevel", "error", "-i", str(v), "-vf", "scale=1920:1080:flags=lanczos,unsharp=5:5:0.6", "-an",
                    "-c:v", "libx264", "-crf", "18", "-g", "1", "-pix_fmt", "yuv420p", str(out)])
    return n, "ok"


if __name__ == "__main__":
    st = sys.argv[1]
    want = [int(x) for x in sys.argv[2:]] or [n for n, s in T.SHOTS.items() if s["kind"] in ("pair", "single")]
    for d in (FR, PR, VID, CHK):
        d.mkdir(parents=True, exist_ok=True)
    fn = {"帧": prep, "视频": submit, "检查": check, "接入": adapt}[st]
    with ThreadPoolExecutor(4 if st == "视频" else 6) as ex:
        for n, r in ex.map(fn, want):
            print(n, r, flush=True)

"""视图的性能门槛（view_bench）：用无界面浏览器量几件用户感受得到的事，和门槛比，超过的标出来。

门槛（2026-10-14 量手书项目时定的，0.13–0.14 的优化就是照着它们做的）：
- 打开：从开始加载到画布上出现对象 ≤ 2 秒；
- 点选对象：按下到画面画出来（事件计时），10 次的中位 ≤ 120 毫秒；
- 拖画板、放大后平移、放大后平移（有插件画格子）：帧间隔的第 95 百分位 ≤ 33 毫秒（每秒 30 帧以上）。

不给数据库时造一个合成项目：800 个对象，构成照手书（文字一半、图片三成多、批注一成、几段音频），两块画板，
图片和音频由这里生成，不依赖任何人的文件。也可以给一个真实的库（只读，不写任何东西）。
条件照用户的电脑：1536×760、Windows 缩放 125%；浏览器关掉扩展、同步、后台联网。笔记本显卡空闲会降频，单次数字能差一倍，
所以默认量 3 轮取中位；--baseline 给另一份网页构建（比如改之前的），两份每轮交替量，看改动是变快还是变慢。

python -m layerweave.tool.builtin.view.bench [DATABASE --project 1] [--objects 800] [--rounds 3] [--baseline 网页目录] [--json]
"""
import argparse
from array import array
from contextlib import closing
import json
import math
from pathlib import Path
import random
from statistics import median
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
from urllib.request import urlopen
import wave
import zlib

from layerweave.support.api import initialize_database, open_database, run_operation, transaction

from .data import find_ffmpeg
from .note import _note_layer
from .notes import OBJECT_REF
from .plugins import add_plugin
from .screenshot import QUIET, DevTools, _devtools_port, find_browser
from .server import WEB_ROOT, make_server

# 名字、单位、门槛（不超过就算过）
GATES = {
    "open": ("打开到出现对象", "秒", 2.0),
    "click": ("点选对象（中位）", "毫秒", 120),
    "board_drag": ("拖画板：帧间隔 p95", "毫秒", 33),
    "zoom_pan": ("放大后平移：帧间隔 p95", "毫秒", 33),
    "zoom_pan_plugin": ("放大后平移，插件画格子：帧间隔 p95", "毫秒", 33),
}
WIDTH, HEIGHT, DPR = 1536, 760, 1.25

# ---------- 合成项目 ----------
# 手书的构成（2026-10-14 数的）：文字 407、图片 282、批注 82、视频 26、音频 5。视频要 ffmpeg 才造得出来，这里并进图片
MIX = (("text", 0.52), ("image", 0.37), ("note", 0.10), ("audio", 0.01))
LENGTH = 240.0   # 时间轴多长（秒）：每层的对象首尾相接铺满它，和手书一样是一首歌的长度；对象越多每个越短
BOARDS = (("成片", {"text": 4, "image": 4, "audio": 1}), ("分镜", {"text": 2, "image": 2}))


def _png(width, height, seed):
    """一张渐变的 PNG（不压缩也行，这里压一下，和真实的缩略图差不多大）。"""
    rng = random.Random(seed)
    r0, g0, b0 = rng.randrange(256), rng.randrange(256), rng.randrange(256)
    raw = b"".join(b"\x00" + bytes(v for x in range(width) for v in ((r0 + x) & 255, (g0 + 2 * y) & 255, (b0 + x + y) & 255))
                   for y in range(height))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def _wav(path, seconds=20, rate=8000):
    samples = array("h", (int(6000 * math.sin(2 * math.pi * 220 * i / rate) * (0.5 + 0.5 * math.sin(i / rate))) for i in range(seconds * rate)))
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(samples.tobytes())


def make_synthetic(folder, objects=800, seed=7):
    """在 folder 里造 bench.sqlite3 和 media/。返回 (数据库, 项目编号, 各种对象的个数)。"""
    folder = Path(folder)
    media = folder / "media"
    media.mkdir(parents=True, exist_ok=True)
    images = []
    for i in range(24):
        (media / f"img{i}.png").write_bytes(_png(256, 144, seed + i))
        images.append(f"media/img{i}.png")
    _wav(media / "tone.wav")
    rng = random.Random(seed)
    counts = {kind: max(1, round(objects * share)) for kind, share in MIX}
    database = initialize_database(folder / "bench.sqlite3")
    axis = {"unit": "秒", "precision": 0.001}
    with closing(open_database(database)) as c:
        with transaction(c) as w:
            project = w.create("project", {"name": f"合成 {objects} 个对象"})["id"]
            layers = {"text": [], "image": [], "audio": []}
            for name, kinds in BOARDS:
                root = w.create("layer", {"name": name, "type": "text", "config_ref": "layers/text.toml", "axis": axis}, project_id=project)["id"]
                for kind, n in kinds.items():
                    for i in range(n):
                        layers[kind].append(w.create("layer", {"name": f"{kind}{len(layers[kind]) + 1}", "type": kind, "config_ref": f"layers/{kind}.toml",
                                                               "father": root, "axis": axis}, project_id=project)["id"])
            ids = []
            for kind in ("text", "image", "audio"):
                span = LENGTH / math.ceil(counts[kind] / len(layers[kind]))
                for i in range(counts[kind]):
                    layer = layers[kind][i % len(layers[kind])]
                    begin = round(i // len(layers[kind]) * span, 3)
                    info = {"text": {"text": f"第 {i} 条说明：" + "字" * rng.randint(4, 30)},
                            "image": {"source": images[i % len(images)]},
                            "audio": {"source": "media/tone.wav"}}[kind]
                    ids.append(w.create("object", {"config_ref": f"objects/{kind}.toml", "name": f"{kind} {i}", "layer": layer, "begin": begin,
                                                   "end": round(begin + span * 0.9, 3), "information": info, "tips": ""}, project_id=project)["id"])
            for _ in range(len(ids) // 10):   # 一些关联
                a, b = rng.sample(ids, 2)
                w.create("bind", {"source_kind": "object", "source_project_id": project, "source_id": a,
                                  "target_kind": "object", "target_project_id": project, "target_id": b, "tips": ""})

        def notes(write):
            layer = _note_layer(write, project)
            for i in range(counts["note"]):
                note = write.create("object", {"config_ref": OBJECT_REF, "name": "", "layer": layer["id"], "begin": i, "end": i + 1,
                                               "information": {"text": f"批注 {i}", "status": "open" if i % 3 else "done",
                                                               "author": "用户" if i % 2 else "Claude"}, "tips": ""}, project_id=project)
                write.create("bind", {"source_kind": "object", "source_project_id": project, "source_id": note["id"],
                                      "target_kind": "object", "target_project_id": project, "target_id": rng.choice(ids), "tips": ""})
        result = run_operation(c, notes)
        if not result["ok"]:
            raise RuntimeError(f"造批注失败：{result.get('error')}")
    return database, project, counts


# 量"插件画格子"用的插件：文字格子底下画一条（和样板插件「字数」一样的画法）
PLUGIN_JS = """// view_bench 写的插件：文字格子底下画一条，量插件画格子以后平移还顺不顺
export default () => ({label: '量', block: {kinds: ['text'], draw(ctx, o, {width, height}) {
  ctx.fillStyle = 'hsl(' + (o.id * 37 % 120) + ', 75%, 42%)'; ctx.fillRect(0, height - Math.max(3, height * 0.14), width * ((o.id % 10) + 1) / 10, height);
}}});
"""

# ---------- 页面里的测量 ----------
FIRST_OBJ = """(() => { const seen = new MutationObserver(() => { if (document.querySelector('.obj')) { window.__firstObj = performance.now(); seen.disconnect(); } });
  seen.observe(document, {subtree: true, childList: true}); })()"""
EVENTS_ON = """(() => { window.__ev = []; window.__in = null;
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__ev.push([e.name, e.startTime, e.duration]); }).observe({type: 'event', durationThreshold: 16});
  addEventListener('pointerdown', (e) => { window.__in = e.timeStamp; }, {capture: true}); return true; })()"""
# 按下以后最长的那次事件计时（输入到下一次画出来）；比 16 毫秒短的浏览器不报，记 16
EVENT_TOP = """(() => { const t = window.__in; const d = window.__ev.filter((e) => t != null && e[1] >= t - 1).map((e) => e[2]);
  window.__ev = []; window.__in = null; return d.length ? Math.max(...d) : 16; })()"""
FRAMES_ON = """(() => { window.__f = []; let last = performance.now();
  const tick = (t) => { window.__f.push(t - last); last = t; if (window.__rec) requestAnimationFrame(tick); };
  window.__rec = true; requestAnimationFrame(tick); return true; })()"""
FRAMES_OFF = "(() => { window.__rec = false; return window.__f.slice(1); })()"
VISIBLE_OBJ = """(() => { const els = [...document.querySelectorAll('.obj')].filter((el) => { const r = el.getBoundingClientRect();
    return r.width > 16 && r.height > 8 && r.left > 0 && r.top > 60 && r.right < innerWidth - 360 && r.bottom < innerHeight - 20; });
  const el = els[Math.floor(els.length * %s)]; if (!el) return null; const r = el.getBoundingClientRect();
  const x = r.left + Math.min(r.width / 2, 30), y = r.top + r.height / 2, hit = document.elementFromPoint(x, y);
  return hit && (hit === el || el.contains(hit)) ? [x, y] : null; })()"""
BOARD_TITLE = """(() => { const t = [...document.querySelectorAll('.bhead b')].find((b) => { const r = b.getBoundingClientRect();
  return r.top > 50 && r.bottom < innerHeight - 60 && r.left > 0 && r.left < innerWidth - 500; });
  if (!t) return null; const r = t.getBoundingClientRect(); return [r.left + 20, r.top + r.height / 2]; })()"""
PANE = """(() => { for (let y = 80; y < innerHeight - 60; y += 16) for (let x = 20; x < innerWidth - 380; x += 16) {
  const el = document.elementFromPoint(x, y); if (el && el.classList.contains('react-flow__pane')) return [x, y]; } return null; })()"""
# 图片最多的那条轨道的中间：对着它放大（没有图片就对着画布中间）
AIM = """(() => { const rows = new Map();
  for (const o of document.querySelectorAll('.obj.image')) { const t = o.closest('.track'); rows.set(t, (rows.get(t) || 0) + 1); }
  const best = [...rows.entries()].sort((a, b) => b[1] - a[1])[0];
  if (!best) return [(innerWidth - 360) * 0.45, innerHeight * 0.5];
  const r = best[0].getBoundingClientRect(); return [Math.min(r.left + r.width * 0.45, innerWidth - 400), r.top + r.height / 2]; })()"""
SCENE = """(() => { const vis = (el) => { const r = el.getBoundingClientRect(); return r.right > 0 && r.left < innerWidth - 340 && r.bottom > 40 && r.top < innerHeight; };
  return {缩放: +(document.querySelector('.react-flow__viewport')?.style.transform.match(/scale\\(([\\d.]+)\\)/)?.[1] ?? 0),
          格子: [...document.querySelectorAll('.obj')].filter(vis).length,
          图: [...document.querySelectorAll('.obj.image canvas, .obj.image img')].filter(vis).length,
          插件画的格子: [...document.querySelectorAll('.obj canvas.plugin-paint')].filter(vis).length}; })()"""
GPU = """(() => { const gl = document.createElement('canvas').getContext('webgl'); if (!gl) return '没有 WebGL';
  const x = gl.getExtension('WEBGL_debug_renderer_info'); return x ? gl.getParameter(x.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER); })()"""


def _ev(tab, expression):
    result = tab.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    if "exceptionDetails" in result:
        raise RuntimeError(result["exceptionDetails"].get("exception", {}).get("description", "页面里的脚本出错"))
    return result.get("result", {}).get("value")


def _p95(frames):
    frames = sorted(frames)
    return round(frames[int(len(frames) * 0.95)], 1) if frames else None


def _press(tab, x, y):
    tab.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    tab.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1, buttons=1)


def _drag(tab, start, step, moves):
    """从 start 每 16 毫秒挪一步，松手以后再等几帧（拼接判断、换细节档也算在里面）；返回帧间隔。"""
    x, y = start
    _ev(tab, FRAMES_ON)
    _press(tab, x, y)
    for i in range(1, moves + 1):
        tab.call("Input.dispatchMouseEvent", type="mouseMoved", x=x + i * step[0], y=y + i * step[1], button="left", buttons=1)
        time.sleep(0.016)
    tab.call("Input.dispatchMouseEvent", type="mouseReleased", x=x + moves * step[0], y=y + moves * step[1], button="left", clickCount=1)
    time.sleep(0.3)
    return _ev(tab, FRAMES_OFF) or []


def _warm(tab):
    """先空拖一下画布、不量：笔记本显卡空闲时降频，页面停下来以后的第一下拖动总是慢（不管画面里有什么，2026-10-15 量过：
    第一下 p95 28–48 毫秒，紧接着的 7 毫秒），量的应该是视图本身，不是显卡醒过来的那一下。"""
    spot = _ev(tab, PANE)
    if spot:
        _drag(tab, spot, (8, 0), 12)
        _drag(tab, _ev(tab, PANE) or spot, (-8, 0), 12)


def _open(tab, url):
    tab.call("Page.navigate", url=url)
    deadline = time.time() + 60
    while time.time() < deadline:
        first = _ev(tab, "window.__firstObj ?? null")
        if first is not None:
            time.sleep(2.5)   # 缩略图、波形下完再量别的
            return round(first / 1000, 2)
        time.sleep(0.05)
    return None


def _zoom_pan(tab, moves, want_painted=False):
    """对着图片最多的轨道滚轮放大到 1.6 倍，等格子里的东西画好，在原地附近左右上下各拖一次。"""
    aim = _ev(tab, AIM)
    for _ in range(16):
        tab.call("Input.dispatchMouseEvent", type="mouseWheel", x=aim[0], y=aim[1], deltaX=0, deltaY=-120)
        time.sleep(0.25)
        if _ev(tab, SCENE)["缩放"] >= 1.6:
            break
    time.sleep(2.0)
    if want_painted:
        deadline = time.time() + 5
        while time.time() < deadline and not _ev(tab, SCENE)["插件画的格子"]:
            time.sleep(0.2)
    scene = _ev(tab, SCENE)
    _warm(tab)
    frames, spot = [], _ev(tab, PANE) or aim
    for step in ((-12, 0), (12, 0), (0, -6), (0, 6)):
        frames += _drag(tab, spot, step, moves)
        spot = _ev(tab, PANE) or spot
    return _p95(frames), scene


def _session(browser, plain_url, plugin_url, clicks, moves):
    """开一个干净的无界面浏览器，量一轮。"""
    out = {}
    with tempfile.TemporaryDirectory(prefix="lw-bench-browser-", ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen([browser, "--headless=new", "--hide-scrollbars", "--mute-audio", "--no-first-run", "--no-default-browser-check",
                                    f"--user-data-dir={profile}", *QUIET, "--remote-debugging-port=0", f"--window-size={WIDTH},{HEIGHT}", "about:blank"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        root = tab = None
        try:
            port, path = _devtools_port(profile, time.time() + 30)
            root = DevTools(f"ws://127.0.0.1:{port}{path}")
            with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
                target = next(t for t in json.loads(response.read()) if t.get("type") == "page")
            tab = DevTools(target["webSocketDebuggerUrl"], timeout=60)
            tab.call("Emulation.setDeviceMetricsOverride", width=WIDTH, height=HEIGHT, deviceScaleFactor=DPR, mobile=False)
            tab.call("Page.enable")   # 不开的话，下面这段不会在新页面里跑
            tab.call("Page.addScriptToEvaluateOnNewDocument", source=FIRST_OBJ)
            out["open"] = _open(tab, plain_url)
            out["gpu"] = _ev(tab, GPU)
            # 点选：画面上不同位置的对象各点一下
            _ev(tab, EVENTS_ON)
            times = []
            for i in range(clicks):
                spot = _ev(tab, VISIBLE_OBJ % (0.05 + 0.9 * i / max(1, clicks - 1)))
                if not spot:
                    continue
                _press(tab, *spot)
                tab.call("Input.dispatchMouseEvent", type="mouseReleased", x=spot[0], y=spot[1], button="left", clickCount=1)
                time.sleep(0.6)
                times.append(_ev(tab, EVENT_TOP))
            out["click"] = round(median(times)) if times else None
            out["click_all"] = [round(t) for t in times]
            # 拖画板：往右平着拖 600 像素。斜着拖会经过下面那块画板，有时出拼接提示、有时不出，同一份构建量出来 28–70 毫秒两样
            _warm(tab)
            title = _ev(tab, BOARD_TITLE)
            out["board_drag"] = _p95(_drag(tab, title, (15, 0), moves * 4 // 3)) if title else None
            # 放大平移在重新打开的页面上量（record=0，刚才拖过的画板回到原位）：和下面"插件画格子"那一项是同一个画面，只差插件
            _open(tab, plain_url)
            out["zoom_pan"], out["scene"] = _zoom_pan(tab, moves)
            _open(tab, plugin_url)
            out["zoom_pan_plugin"], out["scene_plugin"] = _zoom_pan(tab, moves, want_painted=True)
        finally:
            if tab:
                tab.close()
            if root:
                try:
                    root.call("Browser.close")
                except (RuntimeError, OSError):
                    pass
                root.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
    return out


# ---------- 汇总 ----------
def _width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text, width):
    return text + " " * max(0, width - _width(text))


def summarize(runs, baseline_runs=None):
    """每一项取各轮的中位，和门槛比。runs：每轮一个 dict（_session 的结果）。"""
    rows = []
    for key, (label, unit, gate) in GATES.items():
        values = [r.get(key) for r in runs]
        got = [v for v in values if v is not None]
        value = round(median(got), 2 if unit == "秒" else 1) if got else None
        row = {"key": key, "label": label, "unit": unit, "gate": gate, "value": value, "rounds": values,
               "ok": value is not None and value <= gate}
        if baseline_runs is not None:
            base = [r.get(key) for r in baseline_runs if r.get(key) is not None]
            row["baseline"] = round(median(base), 2 if unit == "秒" else 1) if base else None
            row["baseline_rounds"] = [r.get(key) for r in baseline_runs]
        rows.append(row)
    return rows


def describe(result, color=False):
    red, end = ("\033[31m", "\033[0m") if color else ("", "")
    fmt = lambda v, unit: "量不到" if v is None else (f"{v:.2f} 秒" if unit == "秒" else f"{v:.0f} 毫秒")
    lines = [result["title"]]
    has_base = any("baseline" in row for row in result["rows"])
    for row in result["rows"]:
        verdict = "通过" if row["ok"] else "超过门槛" if row["value"] is not None else "没量到"
        rounds = " / ".join("—" if v is None else (f"{v:.2f}" if row["unit"] == "秒" else f"{v:.0f}") for v in row["rounds"])
        line = (f"  {_pad(row['label'], 36)}{_pad(fmt(row['value'], row['unit']), 10)}门槛 {_pad(fmt(row['gate'], row['unit']), 10)}"
                + (f"基线 {_pad(fmt(row.get('baseline'), row['unit']), 10)}" if has_base else "") + f"{_pad(verdict, 10)}各轮 {rounds}")
        lines.append(line if row["ok"] else red + line + end)
    lines.append("全部通过。" if result["passed"] else red + "有超过门槛的项：先看最近的改动；数字忽高忽低时多量几轮（--rounds 5）。" + end)
    return "\n".join(lines)


def bench(database=None, project_id=None, *, objects=800, rounds=3, baseline=None, browser=None, clicks=10, moves=30):
    """量 rounds 轮（有 baseline 时和它每轮交替），返回每一项的中位、门槛和判定。不给 database 时造合成项目。"""
    browser = find_browser(browser)
    if browser is None:
        raise FileNotFoundError("找不到 Chrome、Edge 或 Chromium：用 --browser 或环境变量 LAYERWEAVE_BROWSER 指定浏览器路径")
    if baseline is not None and not (Path(baseline) / "index.html").is_file():
        raise ValueError(f"基线目录里没有 index.html：{baseline}（要的是一份构建好的视图网页，比如旧版本的 view/web）")
    with tempfile.TemporaryDirectory(prefix="lw-bench-", ignore_cleanup_errors=True) as temp:
        temp = Path(temp)
        if database is None:
            database, project_id, counts = make_synthetic(temp / "project", objects)
            what = f"合成 {objects} 个对象（文字 {counts['text']}、图片 {counts['image']}、批注 {counts['note']}、音频 {counts['audio']}）"
        else:
            database, project_id = Path(database), project_id or 1
            if not database.is_file():
                raise FileNotFoundError(f"数据库不存在：{database}")
            what = f"{database.name} 的项目 {project_id}"
        # 插件画格子那一项：另一份本机清单，链接上面那个小插件
        (temp / "plugin").mkdir()
        (temp / "plugin" / "plugin.js").write_text(PLUGIN_JS, encoding="utf-8")
        add_plugin(temp / "plugin" / "plugin.js", name="bench", root=temp / "state-plugin")
        servers, variants = [], []
        try:
            for name, web in (("现在", None), *((("基线", baseline),) if baseline is not None else ())):
                urls = []
                for state in ("state", "state-plugin"):
                    server, url = make_server(database, state_root=temp / state, record_state=False, web_root=web)
                    threading.Thread(target=server.serve_forever, daemon=True).start()
                    servers.append(server)
                    urls.append(f"{url}?project={project_id}&record=0")
                variants.append((name, *urls))
            runs = {name: [] for name, *_ in variants}
            for _ in range(rounds):
                for name, plain, plugin in variants:
                    runs[name].append(_session(browser, plain, plugin, clicks, moves))
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
    rows = summarize(runs["现在"], runs.get("基线"))
    gpu = next((r.get("gpu") for r in runs["现在"] if r.get("gpu")), "?")
    title = (f"view_bench：{what}，{rounds} 轮取中位{'（和基线交替）' if baseline else ''}；{Path(browser).stem}，显卡 {gpu}，"
             f"{WIDTH}×{HEIGHT} 缩放 {DPR:g}，缩略图{'用 ffmpeg 缩' if find_ffmpeg() else '用原图（没有 ffmpeg）'}")
    result = {"title": title, "rows": rows, "passed": all(row["ok"] for row in rows), "runs": runs, "web": str(WEB_ROOT),
              "baseline": str(baseline) if baseline else None}
    return {**result, "text": describe(result)}


COMMANDS = [{
    "name": "view_bench",
    "summary": "视图的性能门槛：用无界面浏览器量打开、点选、拖画板、放大后平移（也量有插件画格子时），和门槛比，超过的标红。改了视图以后跑",
    "entrypoint": "layerweave.tool.builtin.view.bench:bench",
    "cli": "python -m layerweave.tool.builtin.view.bench",
    "read_only": True,
    "context": [],
    "parameters": {
        "database": {"type": "string", "description": "量这个库（只读）；省略时造一个合成项目"},
        "project_id": {"type": "integer", "description": "给了库时量哪个项目，默认 1"},
        "objects": {"type": "integer", "default": 800, "description": "合成项目的对象数（构成照手书）"},
        "rounds": {"type": "integer", "default": 3, "description": "量几轮取中位；数字忽高忽低时多量几轮"},
        "baseline": {"type": "string", "description": "另一份视图网页的目录（构建好的 view/web，比如改之前的），和现在的每轮交替量"},
        "browser": {"type": "string", "description": "浏览器路径；省略时自动找 Chrome、Edge、Chromium"},
    },
    "returns": "rows（每一项：label、unit、gate 门槛、value 各轮中位、rounds 各轮、ok；有基线时还有 baseline）、passed、title、runs（每轮的原始数字）、text。",
    "examples": [{"cli": "python -m layerweave.tool.builtin.view.bench"},
                 {"cli": "python -m layerweave.tool.builtin.view.bench --baseline D:/old/view/web --rounds 5"},
                 {"cli": "python -m layerweave.tool.builtin.view.bench DATABASE --project 1"}],
    "notes": ["门槛：打开 ≤ 2 秒；点选中位 ≤ 120 毫秒；拖画板、放大后平移的帧间隔 p95 ≤ 33 毫秒。有超过的退出码是 1。",
              "只读：起只监听本机的临时服务和独立配置的无界面浏览器（关掉扩展、同步），量完都关掉；合成项目放在临时目录，量完删掉。",
              "一轮大约半分钟。笔记本显卡空闲会降频，单次数字能差一倍，所以看中位；比较改动用 --baseline 交替量。",
              "每次量拖动之前先空拖一下不量：显卡空闲以后的第一下总是慢，和视图的代码无关。"],
}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图的性能门槛", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path, nargs="?", help="量这个库（只读）；省略时造一个合成项目")
    p.add_argument("--project", type=int, help="给了库时量哪个项目，默认 1")
    p.add_argument("--objects", type=int, default=800, help="合成项目的对象数")
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--baseline", type=Path, help="另一份视图网页的目录，和现在的交替量")
    p.add_argument("--browser")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    a = p.parse_args()
    try:
        result = bench(a.database, a.project, objects=a.objects, rounds=a.rounds, baseline=a.baseline, browser=a.browser)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"没有量成：{error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if a.json else describe(result, color=sys.stdout.isatty()))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

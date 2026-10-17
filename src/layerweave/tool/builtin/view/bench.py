"""视图的性能门槛（view_bench）：用无界面浏览器量几件用户感受得到的事，和门槛比，超过的标出来。

默认参考门槛（应结合当前设备与基线评估）：
- 打开：从开始加载到首个对象进入 DOM ≤ 2 秒（不是已绘制或可操作时间）；
- 点选对象：按下到画面画出来（事件计时），10 次的中位 ≤ 120 毫秒；
- 拖画板、放大后平移：活跃拖动的 rAF 间隔 p95 ≤ 33 毫秒；另记最长帧和样本数。
  （0.23.0 以前还有"放大后平移，插件画格子"一项，随插件画格子一起去掉了。）

不给数据库时造一个合成项目：800 个对象，采用文字、图片、批注与音频的混合构成，两块画板，
图片和音频由这里生成，不依赖任何人的文件。也可以给一个真实的库（只读，不写任何东西）。
默认测量条件：1536×760、设备缩放 125%；浏览器关掉扩展、同步、后台联网。输入按有限的 60 Hz 节拍发送，
记录实际输入和移动；空场景标无效。默认 3 轮；--baseline 交替并反转先后顺序（ABBAAB）。

python -m layerweave.tool.builtin.view.bench [DATABASE --project 1] [--objects 800] [--rounds 3] [--baseline 网页目录] [--json]
"""
import argparse
from array import array
from contextlib import closing
import json
import hashlib
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
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import wave
import zlib

from layerweave.support.api import initialize_database, open_database, run_operation, transaction

from .data import find_ffmpeg
from .note import _note_layer
from .notes import OBJECT_REF
from .screenshot import QUIET, DevTools, _devtools_port, find_browser
from .server import WEB_ROOT, make_server

# 名字、单位、门槛（不超过就算过）
GATES = {
    "open": ("首个对象进入 DOM", "秒", 2.0),
    "click": ("点选对象（中位）", "毫秒", 120),
    "board_drag": ("拖画板：帧间隔 p95", "毫秒", 33),
    "zoom_pan": ("放大后平移：帧间隔 p95", "毫秒", 33),
}
WIDTH, HEIGHT, DPR = 1536, 760, 1.25

# ---------- 合成项目 ----------
# 可复现的合成素材比例；视频需 FFmpeg，此处以图片代表媒体对象
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


# ---------- 页面里的测量 ----------
FIRST_OBJ = """(() => { const seen = new MutationObserver(() => { if (document.querySelector('.obj')) { window.__firstObj = performance.now(); seen.disconnect(); } });
  seen.observe(document, {subtree: true, childList: true}); })();"""
# A callback timestamp is not a presentation timestamp. Keep the two clocks separate:
# active intervals use rAF timestamps; first/release callback delays use performance.now.
MEASURE_INIT = """
(() => {
  window.__benchDrag = {armed:false, active:false};
  addEventListener('pointerdown', e => {
    const m=window.__benchDrag; if(m.armed){m.active=true;m.start=performance.now();m.down=[e.clientX,e.clientY];}
  }, true);
  addEventListener('pointermove', e => {
    const m=window.__benchDrag;if(m.active)m.pointers.push([performance.now(),e.timeStamp,e.clientX,e.clientY]);
  }, true);
  const finish = e => {const m=window.__benchDrag;if(m.active){m.active=false;m.end=performance.now();m.up=[e.clientX,e.clientY];}};
  addEventListener('pointerup', finish, true);
  addEventListener('pointercancel', finish, true);
})();
"""
DRAG_ON = """
(() => {
  const m=window.__benchDrag={armed:true,active:false,frames:[],pointers:[]};
  let last=null;
  const tick=t=>{
    if(window.__benchDrag!==m||!m.armed)return;
    if(m.active){if(last!==null)m.frames.push(t-last);else m.first_callback_ms=performance.now()-m.start;last=t;}
    else {last=null;if(m.end!==undefined&&m.release_callback_ms===undefined)m.release_callback_ms=performance.now()-m.end;}
    requestAnimationFrame(tick);
  };requestAnimationFrame(tick);return true;
})()
"""
DRAG_OFF = "(() => {const m=window.__benchDrag;m.armed=false;return m;})()"
EVENTS_ON = """(() => { window.__ev = []; window.__in = null;
  new PerformanceObserver(l => {for(const e of l.getEntries())window.__ev.push([e.name,e.startTime,e.duration,e.interactionId]);})
    .observe({type:'event',durationThreshold:16});
  addEventListener('pointerdown', e=>{window.__in=e.timeStamp;}, {capture:true});return true;})()"""
EVENT_TOP = """(() => {const t=window.__in;const d=window.__ev.filter(e=>t!=null&&e[1]>=t-1).map(e=>e[2]);
  window.__ev=[];window.__in=null;return d.length?Math.max(...d):16;})()"""
# These DOM readers work with both the old per-object canvas and shared media tiles.
DOM_HELPERS = r"""
const flow=document.querySelector('.flow'), bounds=flow?.getBoundingClientRect();
const visible=el=>{const r=el.getBoundingClientRect();return bounds&&r.width>0&&r.height>0&&r.right>bounds.left&&r.left<bounds.right&&r.bottom>bounds.top&&r.top<bounds.bottom;};
const point=el=>{
  if(!el||!visible(el))return null;const r=el.getBoundingClientRect();
  const l=Math.max(r.left,bounds.left),right=Math.min(r.right,bounds.right);
  const t=Math.max(r.top,bounds.top),bottom=Math.min(r.bottom,bounds.bottom);
  const w=right-l,h=bottom-t;if(w<=0||h<=0)return null;
  // Minimum-width objects can overlap their neighbor at overview zoom. Try the
  // exposed strip as well as the center; never click an occluding object instead.
  const preferred=Math.max(l+w*.05,Math.min(r.left+Math.min(r.width/2,30),right-w*.05));
  const xs=[...new Set([preferred,l+w*.05,l+w*.25,l+w*.5,l+w*.75,right-w*.05])];
  const ys=[t+h*.5,t+h*.25,t+h*.75,t+h*.05,bottom-h*.05];
  for(const y of ys)for(const x of xs){const hit=document.elementFromPoint(x,y);
    if(hit&&(hit===el||el.contains(hit)))return [x,y];
  }return null;
};
const viewport=()=>{const m=new DOMMatrixReadOnly(getComputedStyle(document.querySelector('.react-flow__viewport')).transform);return {x:m.e,y:m.f,zoom:m.a};};
const drawn=el=>{
  if(el.dataset.mediaState)return el.dataset.mediaState==='ready';
  return [...el.querySelectorAll('canvas')].some(c=>c.width>0&&c.height>0&&(c.width!==300||c.height!==150))
    ||[...el.querySelectorAll('img')].some(i=>i.complete&&i.naturalWidth>0);
};
"""
VISIBLE_OBJ = "(() => {" + DOM_HELPERS + """
  const els=[...document.querySelectorAll('.obj')].filter(el=>{
    const r=el.getBoundingClientRect();return r.width>=6&&r.height>=8&&point(el);
  });const el=els[Math.min(els.length-1,Math.floor(els.length*%s))];return el?{id:el.dataset.id,point:point(el)}:null;
})()"""
BOARD_TITLE = "(() => {" + DOM_HELPERS + """
  for(const el of document.querySelectorAll('.bhead b')){const p=point(el);if(p)return p;}return null;
})()"""
BOARD_ANCHOR = "(() => {" + DOM_HELPERS + """
  const el=[...document.querySelectorAll('.bhead b')].find(e=>visible(e));
  if(!el)return null;const r=el.getBoundingClientRect(),node=el.closest('.react-flow__node');
  return {id:node.dataset.id,point:[r.left+Math.min(r.width/2,20),r.top+r.height/2],
    safe:[bounds.left+140,bounds.top+140],width:bounds.width,height:bounds.height};
})()"""
PANE = "(() => {" + DOM_HELPERS + """
  if(!bounds)return null;
  for(let y=bounds.top+70;y<bounds.bottom-70;y+=24)for(let x=bounds.left+70;x<bounds.right-70;x+=24){
    const el=document.elementFromPoint(x,y);if(el?.classList.contains('react-flow__pane'))return [x,y];
  }return null;
})()"""
FLOW_CENTER = "(() => {" + DOM_HELPERS + "return bounds?[bounds.left+bounds.width*.45,bounds.top+bounds.height*.55]:null;})()"
SCENE = "(() => {" + DOM_HELPERS + """
  const objects=[...document.querySelectorAll('.obj')],shown=objects.filter(visible);
  return {缩放:bounds?viewport().zoom:0,格子:shown.length,
    图:shown.filter(el=>el.classList.contains('image')&&drawn(el)).length,
    objects:objects.length,canvas:document.querySelectorAll('.flow canvas').length,
    visible_images:shown.filter(el=>el.classList.contains('image')&&!el.classList.contains('missing')).length,
    failed_media:shown.filter(el=>el.dataset.mediaState==='failed').length,
    viewport:bounds?viewport():null,
    nodes:[...document.querySelectorAll('.react-flow__node')].map(el=>{
      const m=new DOMMatrixReadOnly(getComputedStyle(el).transform);return {id:el.dataset.id,x:m.e,y:m.f};
    })};
})()"""
READY = " (async () => {" + DOM_HELPERS + """
  const frames=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
  await frames();
  // Camera settling is 120 ms. Waiting here does not replace waiting for media work.
  await new Promise(r=>setTimeout(r,150));
  const started=performance.now();
  if(typeof window.__layerweavePaintIdle==='function'){
    const completed=await Promise.race([window.__layerweavePaintIdle().then(()=>true),new Promise(r=>setTimeout(()=>r(false),12000))]);
    await frames();
    const state=window.__layerweavePaintState?.();
    return {ok:completed&&!state?.pending,method:'paint_queue',state,elapsed_ms:performance.now()-started};
  }
  // Older baseline builds do not expose a queue. This is an explicitly weaker DOM
  // readiness check, not a claim that hidden media or arbitrary plugin promises settled.
  let stable=null,last='';
  while(performance.now()-started<12000){
    await frames();
    const els=[...document.querySelectorAll('.obj')].filter(visible);
    const media=els.filter(el=>el.querySelector('canvas,img'));
    const signature=media.map(el=>el.dataset.id+':'+drawn(el)).join('|');
    if(media.every(drawn)&&signature===last){stable??=performance.now();if(performance.now()-stable>=150)return {ok:true,method:'legacy_visible_dom',elapsed_ms:performance.now()-started};}
    else stable=null;
    last=signature;
  }
  return {ok:false,method:'legacy_visible_dom',reason:'可见媒体未完成',elapsed_ms:performance.now()-started};
})()"""
GPU = """(() => {const gl=document.createElement('canvas').getContext('webgl');if(!gl)return '没有 WebGL';
  const x=gl.getExtension('WEBGL_debug_renderer_info');return x?gl.getParameter(x.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);})()"""


class BenchTools(DevTools):
    """Finite queued inputs; keep errors that the screenshot client's call discards."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors = []

    def _message(self):
        message = super()._message()
        if "error" in message:
            self.errors.append(message)
        return message

    def send(self, method, **params):
        self.counter += 1
        self._send(1, json.dumps({"id": self.counter, "method": method, "params": params}).encode())


def _ev(tab, expression):
    result = tab.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    if "exceptionDetails" in result:
        raise RuntimeError(result["exceptionDetails"].get("exception", {}).get("description", "页面里的脚本出错"))
    return result.get("result", {}).get("value")


def _p95(frames):
    frames = sorted(frames)
    return round(frames[int(len(frames) * 0.95)], 1) if frames else None


def _frame_stats(frames):
    return {"p95_ms": _p95(frames), "max_ms": round(max(frames), 1) if frames else None,
            "sample_count": len(frames), "over_33_ms": sum(f > 33 for f in frames)}


def _press(tab, x, y, *, button="left", buttons=1):
    tab.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    tab.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button=button, clickCount=1, buttons=buttons)


def _send_moves(tab, start, step, moves, *, button="left", buttons=1):
    """A finite 60 Hz schedule, independent of page acknowledgements."""
    origin = time.perf_counter()
    sent = []
    for i in range(1, moves + 1):
        delay = origin + i / 60 - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        tab.send("Input.dispatchMouseEvent", type="mouseMoved", x=start[0] + i * step[0],
                 y=start[1] + i * step[1], button=button, buttons=buttons)
        sent.append((time.perf_counter() - origin) * 1000)
    return sent


def _measure_drag(tab, start, step, moves, *, pan=False):
    before = _ev(tab, SCENE)
    errors = len(tab.errors)
    _ev(tab, DRAG_ON)
    # React Flow's nopan nodes reject left-button panning even with Space. Its
    # normal middle-button gesture works on both nodes and pane in old/new builds.
    button, buttons = ("middle", 4) if pan else ("left", 1)
    activation = [0, 0]
    _press(tab, *start, button=button, buttons=buttons)
    scheduled_start, scheduled_step = start, step
    if not pan:
        dx, dy = step[0] * moves, step[1] * moves
        length = math.hypot(dx, dy)
        if length:
            distance = min(4, length / 2)
            activation = [dx / length * distance, dy / length * distance]
            scheduled_start = [start[0] + activation[0], start[1] + activation[1]]
            scheduled_step = [(dx - activation[0]) / moves, (dy - activation[1]) / moves]
            # Cross the drag threshold with a small, recorded step. Without
            # this, a short smoke run's first 50 px move can become its origin.
            tab.call("Input.dispatchMouseEvent", type="mouseMoved", x=scheduled_start[0],
                     y=scheduled_start[1], button=button, buttons=buttons)
            _ev(tab, "new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(true))))")
    sent = _send_moves(tab, scheduled_start, scheduled_step, moves, button=button, buttons=buttons)
    tab.call("Input.dispatchMouseEvent", type="mouseReleased", x=start[0] + moves * step[0],
             y=start[1] + moves * step[1], button=button, clickCount=1)
    # Keep release work outside active frame p95, but record its first callback.
    _ev(tab, "new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(true))))")
    measured = _ev(tab, DRAG_OFF)
    ready = _ev(tab, READY)
    after = _ev(tab, SCENE)
    frames = measured.get("frames", [])
    return {"active": _frame_stats(frames), "frames_ms": frames,
            "first_callback_ms": measured.get("first_callback_ms"),
            "release_callback_ms": measured.get("release_callback_ms"),
            "active_ms": measured.get("end", 0) - measured.get("start", 0),
            "pointers": measured.get("pointers", []), "actual_pointer_events": len(measured.get("pointers", [])),
            "sent_moves_ms": sent, "before": before, "after": after, "ready": ready,
            "cdp_errors": tab.errors[errors:], "input_displacement": [step[0] * moves, step[1] * moves],
            "activation_displacement": activation, "button": button}


def _drag(tab, start, step, moves):
    """Active-only frame intervals; tab must use BenchTools to queue finite input."""
    return _measure_drag(tab, start, step, moves)["frames_ms"]


def _pan(tab, delta, moves=12):
    spot = _ev(tab, FLOW_CENTER)
    if not spot:
        raise RuntimeError("没有可平移的画布")
    return _measure_drag(tab, spot, (delta[0] / moves, delta[1] / moves), moves, pan=True)


def _warm(tab):
    """Warm steady-motion measurement separately from the first interaction."""
    _pan(tab, (30, 0), 8)
    _pan(tab, (-30, 0), 8)


def _scene_issue(scene, *, images=False):
    if not scene or not scene.get("格子"):
        return "视口内没有对象，不能以空画面的帧间隔判通过"
    if scene.get("failed_media", 0):
        return "可见媒体绘制失败"
    if images and not scene.get("图"):
        return "视口内没有已画好的图片"
    return None


def _motion_issue(measured, *, board_id=None):
    if measured.get("cdp_errors"):
        return "浏览器拒绝了部分输入"
    if not measured["ready"].get("ok"):
        return "松手后绘制未完成"
    if not measured["active"]["sample_count"] or not measured["actual_pointer_events"]:
        return "没有测到有效拖动帧或输入"
    before, after = measured["before"], measured["after"]
    problem = _scene_issue(before) or _scene_issue(after)
    if problem:
        return problem
    a, b = before["viewport"], after["viewport"]
    dx, dy = measured["input_displacement"]
    if board_id is not None:
        if any(abs(a[k] - b[k]) > 0.1 for k in ("x", "y", "zoom")):
            return "拖画板时发生边缘自动平移；本次不是纯画板拖动"
        old = next((n for n in before["nodes"] if n["id"] == board_id), None)
        new = next((n for n in after["nodes"] if n["id"] == board_id), None)
        if old is None or new is None:
            return "目标画板消失或被拼接"
        actual = [(new["x"] - old["x"]) * a["zoom"], (new["y"] - old["y"]) * a["zoom"]]
    else:
        if abs(a["zoom"] - b["zoom"]) > 0.001:
            return "平移过程中缩放发生变化"
        if before["nodes"] != after["nodes"]:
            return "本次移动了画板而不是平移视口"
        actual = [b["x"] - a["x"], b["y"] - a["y"]]
    measured["actual_displacement"] = actual
    if any(abs(got - wanted) > 10 for got, wanted in zip(actual, (dx, dy))):
        return "实际移动距离与输入不符"
    return None


def _open(tab, url):
    previous = _ev(tab, "performance.timeOrigin")
    tab.call("Page.navigate", url=url)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            document = _ev(tab, "({origin:performance.timeOrigin,first:window.__firstObj??null})")
        except RuntimeError as error:
            if "context" not in str(error).lower():
                raise
            time.sleep(0.05)
            continue
        if document["origin"] != previous and document["first"] is not None:
            ready = _ev(tab, READY)
            return {"first_object_dom_s": round(document["first"] / 1000, 2), "ready": ready}
        time.sleep(0.05)
    return {"first_object_dom_s": None, "ready": {"ok": False, "reason": "没有对象进入 DOM"}}


def _focus_url(url, object_id):
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["focus"] = str(object_id)
    return urlunsplit(parts._replace(query=urlencode(query)))


def _anchor(tab, *, image=False, text=False):
    selector = ".obj.image:not(.missing)" if image else ".obj.text" if text else ".obj"
    return _ev(tab, "(() => {const els=[...document.querySelectorAll(" + json.dumps(selector) +
               ")];if(!els.length)return null;const track=els[0].closest('.track');"
               "const row=els.filter(el=>el.closest('.track')===track);return row[Math.floor(row.length/2)].dataset.id;})()")


def _target_expression(object_id):
    return "(() => {" + DOM_HELPERS + "const el=document.querySelector(" + json.dumps('.obj[data-id="' + str(object_id) + '"]') + r""");
      if(!el||!bounds)return null;const r=el.getBoundingClientRect(),hit=point(el);
      const names=[...el.closest('.react-flow__node').querySelectorAll('.names.stick')].map(n=>n.getBoundingClientRect())
        .filter(n=>n.bottom>r.top&&n.top<r.bottom&&n.right>bounds.left&&n.left<bounds.right);
      const coveredUntil=Math.max(bounds.left,...names.map(n=>n.right));
      const safeLeft=Math.max(bounds.left+60,coveredUntil+40),safeRight=bounds.right-100;
      const cx=r.left+Math.min(r.width/2,30),cy=r.top+r.height/2;
      const safeX=safeLeft<safeRight?(safeLeft+safeRight)/2:null,safeY=bounds.top+bounds.height*.4;
      // Zooming around a narrow object can grow the sticky name column over it.
      // Reveal it with a real pan before continuing, without hiding the column.
      const reveal=!hit&&safeX!==null?[safeX-cx,safeY-cy]:null;
      return {point:hit,width:r.width,height:r.height,reveal_delta:reveal,covered_until:coveredUntil};
    })()"""


def _target(tab, object_id):
    return _ev(tab, _target_expression(object_id))


def _focus(tab, url, *, image=False, text=False):
    chosen = _anchor(tab, image=image, text=text)
    if chosen is None:
        return None, {"ok": False, "reason": "没有所需类型的对象"}
    opened = _open(tab, _focus_url(url, chosen))
    if not opened["ready"]["ok"]:
        return None, opened["ready"]
    # Use an actual object's hit point for every wheel, not the empty middle of a row.
    reveals = 0
    for _ in range(28):
        target = _target(tab, chosen)
        if not target or not target["point"]:
            delta = target.get("reveal_delta") if target else None
            if delta and any(abs(value) > 1 for value in delta) and reveals < 3:
                _pan(tab, delta)
                reveals += 1
                continue
            return None, {"ok": False, "reason": "指定对象没有可命中的可见位置"}
        zoom = _ev(tab, SCENE)["缩放"]
        if zoom >= 1.6 and target["width"] >= 8 and target["height"] >= 8:
            return chosen, _ev(tab, READY)
        if zoom >= 3.99:
            return None, {"ok": False, "reason": "最大缩放下仍无法点选对象"}
        tab.call("Input.dispatchMouseEvent", type="mouseWheel", x=target["point"][0],
                 y=target["point"][1], deltaX=0, deltaY=-120)
        time.sleep(0.04)
    return None, {"ok": False, "reason": "未能对准可见对象"}


def _board_drag(tab, moves):
    anchor = _ev(tab, BOARD_ANCHOR)
    if not anchor:
        return None, {"valid": False, "reason": "没有可拖动的画板标题"}
    # Move the camera through the normal middle-button interaction. The product keeps
    # auto-pan enabled; keep this test's entire path away from its activation edges.
    _pan(tab, (anchor["safe"][0] - anchor["point"][0], anchor["safe"][1] - anchor["point"][1]))
    _warm(tab)
    anchor = _ev(tab, BOARD_ANCHOR)
    if not anchor or not _ev(tab, BOARD_TITLE):
        return None, {"valid": False, "reason": "无法把画板标题放进视口内部"}
    distance = min(400, max(40, anchor["width"] - 300))
    result = _measure_drag(tab, anchor["point"], (distance / moves, 0), moves)
    reason = _motion_issue(result, board_id=anchor["id"])
    result.update(valid=reason is None, reason=reason)
    return (result["active"]["p95_ms"] if reason is None else None), result


def _zoom_pan(tab, url, moves):
    has_images = _anchor(tab, image=True) is not None
    _, ready = _focus(tab, url, image=has_images, text=not has_images)
    scene = _ev(tab, SCENE)
    issue = None if ready["ok"] else ready.get("reason", "媒体绘制未完成")
    issue = issue or _scene_issue(scene, images=has_images)
    if issue:
        return None, scene, {"valid": False, "reason": issue, "ready": ready}
    _warm(tab)
    runs = []
    # Modest local excursions keep a populated neighborhood in view at large zoom.
    for delta in ((-80, 0), (80, 0), (0, -40), (0, 40)):
        run = _pan(tab, delta, moves)
        issue = _motion_issue(run)
        issue = issue or _scene_issue(run["before"], images=has_images)
        issue = issue or _scene_issue(run["after"], images=has_images)
        runs.append(run)
        if issue:
            return None, scene, {"valid": False, "reason": issue, "runs": runs}
    frames = [frame for run in runs for frame in run["frames_ms"]]
    stats = _frame_stats(frames)
    return stats["p95_ms"], scene, {"valid": True, "active": stats, "runs": runs, "ready": ready}


def _session(browser, plain_url, clicks, moves):
    """One fresh browser profile; normal UI mode throughout."""
    out = {"diagnostics": {}}
    with tempfile.TemporaryDirectory(prefix="lw-bench-browser-", ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen([browser, "--headless=new", "--hide-scrollbars", "--mute-audio", "--no-first-run", "--no-default-browser-check",
                                    f"--user-data-dir={profile}", *QUIET, "--remote-debugging-port=0", f"--window-size={WIDTH},{HEIGHT}", "about:blank"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        root = tab = None
        try:
            port, path = _devtools_port(profile, time.time() + 30)
            root = DevTools(f"ws://127.0.0.1:{port}{path}")
            out["browser"] = root.call("Browser.getVersion")
            with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
                target = next(t for t in json.loads(response.read()) if t.get("type") == "page")
            tab = BenchTools(target["webSocketDebuggerUrl"], timeout=60)
            tab.call("Emulation.setDeviceMetricsOverride", width=WIDTH, height=HEIGHT, deviceScaleFactor=DPR, mobile=False)
            tab.call("Page.enable")
            tab.call("Page.addScriptToEvaluateOnNewDocument", source=FIRST_OBJ + "\n;\n" + MEASURE_INIT)
            opened = _open(tab, plain_url)
            out["open"] = opened["first_object_dom_s"]
            out["diagnostics"]["open"] = opened
            out["gpu"] = _ev(tab, GPU)
            _, ready = _focus(tab, plain_url, text=_anchor(tab, text=True) is not None)
            _ev(tab, EVENTS_ON)
            times, chosen_ids = [], []
            if ready["ok"]:
                for i in range(clicks):
                    spot = _ev(tab, VISIBLE_OBJ % (0.05 + 0.9 * i / max(1, clicks - 1)))
                    if not spot:
                        continue
                    _press(tab, *spot["point"])
                    tab.call("Input.dispatchMouseEvent", type="mouseReleased", x=spot["point"][0], y=spot["point"][1], button="left", clickCount=1)
                    _ev(tab, READY)
                    selected = _ev(tab, "document.querySelector('.obj.sel')?.dataset.id")
                    if selected == spot["id"]:
                        times.append(_ev(tab, EVENT_TOP))
                        chosen_ids.append(selected)
            out["click"] = round(median(times)) if times else None
            out["click_all"] = [round(t) for t in times]
            out["diagnostics"]["click"] = {"sample_count": len(times), "object_ids": chosen_ids,
                                           "first_ms": times[0] if times else None, "max_ms": max(times) if times else None,
                                           "valid": bool(times), "ready": ready}
            # Reload: selection/links produced by the click test must not alter drag work.
            _open(tab, plain_url)
            out["board_drag"], out["diagnostics"]["board_drag"] = _board_drag(tab, max(8, moves))
            _open(tab, plain_url)
            out["zoom_pan"], out["scene"], out["diagnostics"]["zoom_pan"] = _zoom_pan(tab, plain_url, moves)
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
        values = [r.get(key) if r.get("diagnostics", {}).get(key, {}).get("valid", True) else None for r in runs]
        got = [v for v in values if v is not None]
        value = round(median(got), 2 if unit == "秒" else 1) if got else None
        row = {"key": key, "label": label, "unit": unit, "gate": gate, "value": value, "rounds": values,
               "valid_rounds": len(got), "invalid_rounds": len(values) - len(got),
               "ok": bool(values) and len(got) == len(values) and value is not None and value <= gate}
        row["status"] = "invalid" if row["invalid_rounds"] or not values else "passed" if row["ok"] else "exceeded"
        row["issues"] = [r.get("diagnostics", {}).get(key, {}).get("reason") or "本轮没有有效样本"
                         for r, v in zip(runs, values) if v is None]
        active = [r.get("diagnostics", {}).get(key, {}).get("active", {}) for r in runs]
        row["sample_counts"] = [a.get("sample_count") for a in active]
        row["max_ms"] = [a.get("max_ms") for a in active]
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
        verdict = "测量无效" if row.get("status") == "invalid" else "通过" if row["ok"] else "超过门槛" if row["value"] is not None else "没量到"
        rounds = " / ".join("—" if v is None else (f"{v:.2f}" if row["unit"] == "秒" else f"{v:.0f}") for v in row["rounds"])
        line = (f"  {_pad(row['label'], 36)}{_pad(fmt(row['value'], row['unit']), 10)}门槛 {_pad(fmt(row['gate'], row['unit']), 10)}"
                + (f"基线 {_pad(fmt(row.get('baseline'), row['unit']), 10)}" if has_base else "") + f"{_pad(verdict, 10)}各轮 {rounds}")
        lines.append(line if row["ok"] else red + line + end)
        if row.get("issues"):
            lines.append("    " + "；".join(dict.fromkeys(row["issues"])))
        if any(n is not None for n in row.get("sample_counts", [])):
            lines.append("    活跃帧样本数 " + " / ".join("—" if n is None else str(n) for n in row["sample_counts"])
                         + "；各轮最长帧 " + " / ".join("—" if n is None else f"{n:g} ms" for n in row["max_ms"]))
    lines.append("全部通过。" if result["passed"] else red + "有超过门槛或无效的项；先核对场景，再比较改动（--baseline；必要时 --rounds 5）。" + end)
    return "\n".join(lines)


def _run_order(variants, rounds):
    """AB / BA / AB gives each build the same count and alternates first position."""
    return [item for index in range(rounds) for item in (variants if index % 2 == 0 else variants[::-1])]


def _web_digest(directory):
    digest = hashlib.sha256()
    for path in sorted(Path(directory).rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(directory)).replace("\\", "/").encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def bench(database=None, project_id=None, *, objects=800, rounds=3, baseline=None, browser=None, clicks=10, moves=120):
    """量 rounds 轮（有 baseline 时和它每轮交替），返回每一项的中位、门槛和判定。不给 database 时造合成项目。"""
    if rounds < 1 or clicks < 1 or moves < 1:
        raise ValueError("rounds、clicks 和 moves 必须大于 0")
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
        servers, variants = [], []
        try:
            for name, web in (("现在", None), *((("基线", baseline),) if baseline is not None else ())):
                server, url = make_server(database, state_root=temp / "state", record_state=False, web_root=web)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                servers.append(server)
                variants.append((name, f"{url}?project={project_id}&record=0"))
            runs = {name: [] for name, *_ in variants}
            order = _run_order(variants, rounds)
            for name, plain in order:
                runs[name].append(_session(browser, plain, clicks, moves))
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
    rows = summarize(runs["现在"], runs.get("基线"))
    gpu = next((r.get("gpu") for r in runs["现在"] if r.get("gpu")), "?")
    title = (f"view_bench：{what}，{rounds} 轮取中位{'（和基线交替）' if baseline else ''}；{Path(browser).stem}，显卡 {gpu}，"
             f"{WIDTH}×{HEIGHT} 缩放 {DPR:g}，缩略图{'用 ffmpeg 缩' if find_ffmpeg() else '用原图（没有 ffmpeg）'}")
    result = {"title": title, "rows": rows, "passed": all(row["ok"] for row in rows), "runs": runs, "web": str(WEB_ROOT),
              "baseline": str(baseline) if baseline else None,
              "method_version": 2, "order": [name for name, *_ in order],
              "input_hz": 60, "moves": moves, "normal_mode": True,
              "web_sha256": _web_digest(WEB_ROOT), "baseline_sha256": _web_digest(baseline) if baseline else None}
    return {**result, "text": describe(result)}


COMMANDS = [{'name': 'view_bench',
  'summary': '视图的性能门槛：用无界面浏览器量打开、点选、拖画板、放大后平移，和门槛比，超过的标红。改了视图以后跑',
  'entrypoint': 'layerweave.tool.builtin.view.bench:bench',
  'cli': 'python -m layerweave.tool.builtin.view.bench',
  'read_only': True,
  'context': [],
  'returns': 'rows（四项，门槛不变；0.23.0 随插件画格子一起去掉了第五项，增加 status/invalid_rounds/sample_counts/max_ms）、passed、runs（含 '
             'diagnostics：活跃帧、输入与实际位移、松手回调、就绪方式）、order、构建 hash、text。回调时机不是实际像素呈现时延。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.view.bench'},
               {'cli': 'python -m layerweave.tool.builtin.view.bench --baseline D:/old/view/web --rounds 5'},
               {'cli': 'python -m layerweave.tool.builtin.view.bench DATABASE --project 1'}],
  'notes': ['门槛：首个对象进入 DOM ≤ 2 秒；点选中位 ≤ 120 毫秒；活跃拖动帧间隔 p95 ≤ 33 毫秒。有超过或无效的退出码是 1。',
            '只读：起只监听本机的临时服务和独立配置的无界面浏览器（关掉扩展、同步），量完都关掉；合成项目放在临时目录，量完删掉。',
            '按 60 Hz 发送有限输入，浏览器可能合并事件；报告实际事件数。基线顺序 ABBAAB，原始数据保留最长帧和样本数。',
            '热身用于稳定连续拖动对照，不推断显卡频率。点选首个样本另外记录；正常模式等待媒体队列，旧构建使用明确标记的较弱 DOM 就绪检查。',
            '标题先移入视口内部，保留产品自动平移；测量时若视口仍变动则标无效。空视口、图片没画好都不能通过。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': ['string', 'null'], 'description': '量这个库（只读）；省略时造一个合成项目'},
                                  'project_id': {'type': ['integer', 'null'], 'description': '给了库时量哪个项目，默认 1'},
                                  'objects': {'type': 'integer', 'default': 800, 'description': '合成项目的对象数（构成照手书）'},
                                  'rounds': {'type': 'integer', 'default': 3, 'description': '量几轮取中位；数字忽高忽低时多量几轮'},
                                  'baseline': {'type': ['string', 'null'],
                                               'description': '另一份视图网页的目录（构建好的 view/web，比如改之前的），和现在的每轮交替量'},
                                  'browser': {'type': ['string', 'null'],
                                              'description': '浏览器路径；省略时自动找 Chrome、Edge、Chromium'}},
                   'additionalProperties': False,
                   'required': []},
  'mcp': {'enabled': False, 'group': 'view', 'reason': '驻留服务或开发性能测量请使用现有 CLI'},
  'cli_mapping': {'project_id': ['project']},
  'cli_only': ['json']}]


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

"""给 AI 用的视图截图：在后台起一个只读视图服务，用无界面浏览器打开同一个页面，存成 PNG。
AI 看到的就是用户在视图里看到的：画板的排版用用户那份（拼接、拆分、位置都一样）。
截图用的页面不记录"正在看哪儿"，也不改排版，不会覆盖用户的状态。
页面把图片、视频封面、波形都加载完才举手，截图工具通过浏览器调试接口等到它再拍，不会拍到还没出图的空色块。

python -m layerweave.tool.builtin.view.screenshot DATABASE PROJECT_ID 输出.png
       [--view canvas|完整插件ID，如 layerweave.cuts] [--board 根层编号] [--begin 起点 --end 终点] [--layers 1 字幕 画面/原画] [--playhead 位置] [--select 对象编号]
       [--focus 对象编号] [--note 批注编号] [--link 用户复制的链接] [--changes 最近几次操作] [--notes | --side 侧栏] [--links] [--full-page]
       [--width 1600 --height 900] [--browser 浏览器路径] [--wait-ms 20000]
"""
import argparse
import base64
from contextlib import closing
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

from layerweave.support.api import read_record

from .data import open_readonly, order_layers
from .fold import read_folds
from .plugins import require_plugin
from .plugin_manifest import LINK_KEYS, OWN_KEYS, PARAM, check_params, read_manifest
from .server import make_server

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_browser(explicit=None):
    """依次找：--browser、环境变量 LAYERWEAVE_BROWSER、REMOTION_BROWSER_EXECUTABLE、常见安装位置、PATH。"""
    for value in (explicit, os.environ.get("LAYERWEAVE_BROWSER"), os.environ.get("REMOTION_BROWSER_EXECUTABLE")):
        if value and Path(value).is_file():
            return value
    for value in CANDIDATES:
        if Path(value).is_file():
            return value
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge"):
        if found := shutil.which(name):
            return found
    return None


# 新建的配置目录照样会被浏览器用系统账号自动登录、把扩展同步进来（Edge 会这样：2026-10-14 在无界面浏览器的日志里看到了用户的扩展在跑，
# 一并出现过画面停止出帧、输入事件等不到应答）。截图只要一个干净的页面：扩展、同步、后台联网都关掉
QUIET = ["--disable-extensions", "--disable-sync", "--disable-background-networking", "--disable-component-update"]


def _remaining(deadline, maximum=30):
    if deadline is None:
        return maximum
    remaining = deadline - time.time()
    if remaining <= 0:
        raise TimeoutError("截图超过整体等待预算；未把未完成画面作为结果返回")
    return min(maximum, remaining)


class DevTools:
    """浏览器调试接口（Chrome DevTools Protocol）的最小客户端：一条只连本机的 WebSocket，按编号收发 JSON。"""

    def __init__(self, url, timeout=30, *, deadline=None):
        self.deadline, self.timeout = deadline, timeout
        parts = urlparse(url)
        self.sock = socket.create_connection((parts.hostname, parts.port), timeout=_remaining(deadline, timeout))
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {parts.path} HTTP/1.1\r\nHost: {parts.hostname}:{parts.port}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            if self.deadline is not None:
                self.sock.settimeout(_remaining(self.deadline, self.timeout))
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("浏览器调试接口拒绝了连接")
            head += chunk
        head, self.buffer = head.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"浏览器调试接口拒绝了连接：{head[:120]!r}")
        self.counter = 0

    def _exact(self, size):
        while len(self.buffer) < size:
            if self.deadline is not None:
                self.sock.settimeout(_remaining(self.deadline, self.timeout))
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise RuntimeError("浏览器调试接口断开了")
            self.buffer += chunk
        data, self.buffer = self.buffer[:size], self.buffer[size:]
        return data

    def _send(self, opcode, payload):
        mask = os.urandom(4)
        size = len(payload)
        head = bytes([0x80 | opcode])
        if size < 126:
            head += bytes([0x80 | size])
        elif size < 1 << 16:
            head += bytes([0x80 | 126]) + struct.pack(">H", size)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", size)
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _message(self):
        parts = []
        while True:
            first, second = self._exact(2)
            size = second & 0x7F
            if size == 126:
                size = struct.unpack(">H", self._exact(2))[0]
            elif size == 127:
                size = struct.unpack(">Q", self._exact(8))[0]
            mask = self._exact(4) if second & 0x80 else None
            payload = self._exact(size)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            opcode = first & 0x0F
            if opcode == 0x9:
                self._send(0xA, payload)
                continue
            if opcode == 0x8:
                raise RuntimeError("浏览器调试接口关闭了连接")
            parts.append(payload)
            if first & 0x80:
                return json.loads(b"".join(parts))

    def call(self, method, **params):
        if self.deadline is not None:
            self.sock.settimeout(_remaining(self.deadline, self.timeout))
        self.counter += 1
        self._send(0x1, json.dumps({"id": self.counter, "method": method, "params": params}).encode())
        while True:
            message = self._message()
            if message.get("id") == self.counter:
                if "error" in message:
                    raise RuntimeError(f"{method} 失败：{message['error'].get('message')}")
                return message.get("result", {})

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def _devtools_port(profile, deadline):
    """浏览器用 --remote-debugging-port=0 自己挑端口，写在配置目录的 DevToolsActivePort 里。"""
    path = Path(profile) / "DevToolsActivePort"
    while time.time() < deadline:
        try:
            lines = path.read_text(encoding="utf-8").split()
            if len(lines) >= 2:
                return int(lines[0]), lines[1]
        except (OSError, ValueError):
            pass
        time.sleep(0.2)
    raise RuntimeError("浏览器没有打开调试接口：确认 --browser 指向 Chrome、Edge 或 Chromium")


def resolve_layers(database, project_id, items):
    """--layers 的每一项：编号，或层名，或带上级的路径（"画面/原画"，从任意一级往下写都行）。
    重名又没写路径时报错，列出候选让人选；网页地址里只用编号。"""
    with closing(open_readonly(database)) as connection:
        rows = order_layers(read_record(connection, "layer", project_id=project_id))
    by_id = {row["id"]: row for row in rows}

    def path(row):
        names, seen = [], set()
        while row is not None and row["id"] not in seen:
            seen.add(row["id"])
            names.append(row["name"] or "")
            row = by_id.get(row["father"])
        return list(reversed(names))

    out = []
    for item in items:
        text = str(item).strip()
        if text.isdigit():
            if int(text) not in by_id:
                raise ValueError(f"项目 {project_id} 里没有层 #{text}")
            out.append(int(text))
            continue
        want = [part for part in text.split("/") if part]
        found = [row for row in rows if want and path(row)[-len(want):] == want]
        if not found:
            raise ValueError(f"没有叫「{text}」的层")
        if len(found) > 1:
            listed = "；".join(f"#{row['id']} {'/'.join(path(row))}" for row in found)
            raise ValueError(f"叫「{text}」的层有 {len(found)} 个：{listed}。写编号，或者带上级写成 上级/名字")
        out.append(found[0]["id"])
    return out


def page_params(pairs):
    """--param 名字=值：原样放进页面地址，给插件页面用（比如一览、预览的 page=3）。名字只能是小写字母、数字、下划线"""
    out = {}
    for pair in pairs or ():
        key, sep, value = str(pair).partition("=")
        if not sep or not PARAM.fullmatch(key):
            raise ValueError(f"--param 要写成 名字=值，名字用小写字母、数字、下划线：{pair}")
        if key in OWN_KEYS:
            raise ValueError(f"--param 不能用视图自己的参数名 {key}：用对应的选项（比如 --{key}）")
        out[key] = value
    return out


def link_query(link, project_id):
    """保留宿主位置和插件参数，剔除链接中的运行/截图控制字段。"""
    query = {key: values[-1] for key, values in parse_qs(urlparse(str(link)).query, keep_blank_values=True).items() if values}
    if "project" in query and str(query["project"]) != str(project_id):
        raise ValueError(f"链接是项目 {query['project']} 的，参数给的是项目 {project_id}")
    plugin_target = query.get("view", "canvas") != "canvas" or query.get("side", "now") not in ("now", "changes", "notes", "walk")
    return {key: value for key, value in query.items() if key in LINK_KEYS or (plugin_target and key not in OWN_KEYS and PARAM.fullmatch(key))}


def capture(database, project_id, output, *, view=None, board=None, begin=None, end=None, layers=None, playhead=None,
            select=None, focus=None, note=None, link=None, changes=None, notes=False, side=None, links=False, full_page=False,
            tree=False, params=None, lang=None, width=1600, height=900, browser=None, wait_ms=20000, state_root=None,
            timeout_ms=60000):
    if timeout_ms <= 0:
        raise ValueError("timeout_ms 必须大于零")
    overall_deadline = time.time() + timeout_ms / 1000
    query = link_query(link, project_id) if link else {}   # 先检查参数，再找浏览器、起服务
    if lang is not None and lang not in ("zh", "en"):
        raise ValueError("lang 需要 zh 或 en")
    query["lang"] = lang or (query.get("lang") if query.get("lang") in ("zh", "en") else "zh")
    extra = page_params(params)
    layer_ids = resolve_layers(database, project_id, layers) if layers else None
    view = view or query.get("view") or "canvas"
    warnings = []
    if view != "canvas":
        row = require_plugin(view, slot="page", root=state_root)
        view = row["id"]
        if (Path(row["root"]) / "plugin.json").is_file():
            values = {k: v for k, v in query.items() if k not in OWN_KEYS}
            warnings = check_params(read_manifest(row["root"])["params"], {**values, **extra})
    side = side or ("notes" if notes else None) or query.get("side")
    if side and side not in ("now", "changes", "notes", "walk"):
        side = require_plugin(side, slot="side", root=state_root)["id"]
    browser = find_browser(browser)
    if browser is None:
        raise FileNotFoundError("找不到 Chrome、Edge 或 Chromium：用 --browser 或环境变量 LAYERWEAVE_BROWSER 指定浏览器路径")
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    query.update({"project": project_id, "view": view, "record": 0, "capture": 1})
    if links:
        query["links"] = 1
    query["tree"] = int(tree)
    if side:
        query["side"] = side
    if full_page and view != "canvas":
        query["full"] = 1
    for key, value in (("board", board), ("begin", begin), ("end", end), ("playhead", playhead), ("select", select),
                       ("focus", focus), ("note", note), ("changes", changes)):
        if value is not None:
            query[key] = value
    query.update(extra)
    if layer_ids:
        query["layers"] = ",".join(str(i) for i in layer_ids)
    server, url = make_server(database, state_root=state_root, record_state=False)
    page = url + "?" + urlencode(query)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if output.exists():
        output.unlink()   # 这是调用方指定的输出文件；先删掉，失败时不会把旧图当成新图
    try:
        # 独立的浏览器配置，不碰用户正在用的浏览器
        with tempfile.TemporaryDirectory(prefix="layerweave-shot-", ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio",
                                        "--no-first-run", "--no-default-browser-check", f"--user-data-dir={profile}", *QUIET,
                                        "--remote-debugging-port=0", f"--window-size={width},{height}", "about:blank"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                ready = _shoot(profile, page, output, width, height, wait_ms, "full" in query,
                               overall_deadline=overall_deadline)
            finally:
                try:
                    process.wait(timeout=min(2, max(0.05, overall_deadline-time.time())))
                except subprocess.TimeoutExpired:
                    process.kill()
    finally:
        server.shutdown()
        server.server_close()
    with closing(open_readonly(database)) as connection:   # 截图是 AI 这边：AI 折叠的收成细条，用户折叠的照常展开并标出
        folded = read_folds(connection, project_id)
    return {"output": str(output), "page": page, "browser": browser, "size": [width, height], "ready": ready, "folded": folded, "issues": warnings}


def _shoot(profile, page, output, width, height, wait_ms, full_page=False, *, overall_deadline=None):
    port, browser_path = _devtools_port(profile, time.time() + _remaining(overall_deadline, 30))
    root = DevTools(f"ws://127.0.0.1:{port}{browser_path}", deadline=overall_deadline)
    try:
        with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=_remaining(overall_deadline, 10)) as response:
            target = next(t for t in json.loads(response.read()) if t.get("type") == "page")
        tab = DevTools(target["webSocketDebuggerUrl"], deadline=overall_deadline)
        try:
            tab.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False)
            tab.call("Page.navigate", url=page)
            ready, deadline = False, time.time() + _remaining(overall_deadline, wait_ms / 1000)
            while not ready and time.time() < deadline:
                time.sleep(0.25)
                result = tab.call("Runtime.evaluate", expression="({ready:window.__layerweaveReady===true,error:window.__layerweaveError})", returnByValue=True)
                state = result.get("result", {}).get("value") or {}
                if state.get("error"):
                    raise RuntimeError(state["error"])
                ready = state.get("ready") is True
            if not ready:
                raise RuntimeError(f"页面在 {wait_ms} 毫秒内尚未画完，没有生成截图")
            if full_page:   # 整页：把窗口拉到内容的高度再拍（最多 16000 像素）
                result = tab.call("Runtime.evaluate", expression="document.documentElement.scrollHeight", returnByValue=True)
                tall = min(16000, max(height, int(result.get("result", {}).get("value") or height)))
                tab.call("Emulation.setDeviceMetricsOverride", width=width, height=tall, deviceScaleFactor=1, mobile=False)
                time.sleep(0.5)
            result = tab.call("Runtime.evaluate", expression="window.__layerweaveError || null", returnByValue=True)
            if result.get("result", {}).get("value"):
                raise RuntimeError(result["result"]["value"])
            image = base64.b64decode(tab.call("Page.captureScreenshot", format="png")["data"])
            _remaining(overall_deadline)
            output.write_bytes(image)
        finally:
            tab.close()
        return ready
    finally:
        try:
            root.deadline = time.time() + 2  # 即使主预算耗尽，也给自己的浏览器一个有界关闭机会。
            root.call("Browser.close")
        except (RuntimeError, OSError):
            pass   # 浏览器关闭时会直接断开连接
        root.close()


COMMANDS = [{'name': 'view_screenshot',
  'summary': '把视图页面截成 PNG：整张画布、某一块画板（可指定时间范围）、接缝页或一览网格；可以对准对象或批注、按用户复制的链接拍、标出最近的改动、画出关系线',
  'entrypoint': 'layerweave.tool.builtin.view.screenshot:capture',
  'cli': 'python -m layerweave.tool.builtin.view.screenshot',
  'read_only': True,
  'context': ['database', 'project_id'],
  'returns': 'output、page（截图用的页面地址）、browser、size、ready（成功时为 '
             'True；未就绪、目标插件不可用或运行失败时报错，不生成替代截图）、issues（插件参数提醒）、folded（两边的折叠 [{layer, user, user_tips, ai, '
             'ai_tips}]：AI 折叠的在图里只是一条细条；用户折叠的照常画出，标着「用户折叠了」）。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.view.screenshot DATABASE 1 shots/all.png',
                'arguments': {'output': 'output/view.png'}},
               {'cli': 'python -m layerweave.tool.builtin.view.screenshot DATABASE 1 shots/t10.png --board 1 '
                       '--begin 8 --end 14 --playhead 10'},
               {'cli': 'python -m layerweave.tool.builtin.view.screenshot DATABASE 1 shots/note42.png --note '
                       '42'},
               {'cli': 'python -m layerweave.tool.builtin.view.screenshot DATABASE 1 shots/user.png --link '
                       '"http://127.0.0.1:8765/?project=1&board=1&begin=8&end=14&select=16"'},
               {'cli': 'python -m layerweave.tool.builtin.view.screenshot DATABASE 1 shots/changes.png '
                       '--changes 5'},
               {'cli': 'python -m layerweave.tool.builtin.view.screenshot DATABASE 1 shots/cuts.png --view '
                       'layerweave.cuts --full-page'}],
  'notes': ['截图页面不记录状态、不改排版；用户正在看哪儿请用 view_state，画板怎么排请用 view_layout。',
            '用户贴来视图链接时用 --link；读到一条批注想看它指哪儿时用 --note。',
            '只读：起一个只监听本机的临时服务和一个独立配置的无界面浏览器，截完都关掉。',
            '左右接续的画板上，begin、end、playhead 用画板上的连续时间；view_layout 的 offset 是每一段的起点。',
            '接缝页列出同一条轨道里前后相接的图片和视频：上一段的最后一帧和下一段的第一帧并排，用来查衔接；--board、--begin、--end 可以缩小范围。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string',
                                               'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'project_id': {'type': 'integer', 'description': '明确的项目编号'},
                                  'output': {'type': 'string', 'description': '由 AI 指定的 PNG 输出路径'},
                                  'lang': {'type': ['string', 'null'],
                                           'description': '截图语言；显式值优先于链接，默认 zh',
                                           'enum': ['zh', 'en']},
                                  'view': {'type': ['string', 'null'],
                                           'description': 'canvas（画布）、layerweave.assets（选装一览：按种类列出所有对象），或插件的页面，比如 '
                                                          'layerweave.cuts（选装接缝插件：前后相接的画面并排）；省略时是画布，给了 link '
                                                          '时按链接'},
                                  'board': {'type': ['integer', 'null'],
                                            'description': '只拍这个根层所在的画板；省略时拍整张画布'},
                                  'begin': {'type': ['number', 'null'],
                                            'description': '画板显示的起点，用这块画板的单位；和 end 一起用'},
                                  'end': {'type': ['number', 'null'], 'description': '画板显示的终点'},
                                  'layers': {'type': ['array', 'null'],
                                             'description': '只显示这些层：编号、层名，或带上级的路径（画面/原画）；重名时报错并列出候选',
                                             'items': {}},
                                  'playhead': {'type': ['number', 'null'],
                                               'description': '播放头位置（落在 board 指定的画板上，省略 board '
                                                              '时是第一块）；右侧会列出这一刻每层的内容'},
                                  'select': {'type': ['integer', 'null'], 'description': '选中并展开详情的对象编号'},
                                  'focus': {'type': ['integer', 'null'],
                                            'description': '把镜头移到这个对象上（放在画面左上三分之一处）'},
                                  'note': {'type': ['integer', 'null'],
                                           'description': '对准这条批注（回复也行，按它所在的楼）：镜头框住楼主指的对象、层或那一段时间并高亮，右侧打开批注列表、标出这一楼'},
                                  'link': {'type': ['string', 'null'],
                                           'description': '用户在视图里点「复制链接」得到的地址；按它拍同一个位置（画板、范围、播放头、选中的对象、对准的批注）。其他参数会覆盖链接里的同名设置'},
                                  'changes': {'type': ['integer', 'null'],
                                              'description': '标出最近这么多次操作改过的对象和删除、移动前的位置，右侧列出改动'},
                                  'notes': {'type': 'boolean',
                                            'description': '右侧打开批注列表（画布上的批注标记总是显示）',
                                            'default': False},
                                  'side': {'type': ['string', 'null'],
                                           'description': '右侧打开哪一栏：now（此刻）、changes、notes、walk，或者插件的侧栏（插件在清单里的名字，view_plugin '
                                                          '列出来的那个）；notes 同 --notes'},
                                  'links': {'type': 'boolean',
                                            'description': '画出全部关系线（bind）；不画时只画选中对象的',
                                            'default': False},
                                  'full_page': {'type': 'boolean',
                                                'description': '接缝页、一览页按内容高度截整页（最多 16000 像素）',
                                                'default': False},
                                  'tree': {'type': 'boolean',
                                           'description': '画布左边打开目录树（项目的层：对象数、谁折叠的、几楼批注没处理）',
                                           'default': False},
                                  'params': {'type': ['object', 'null'],
                                             'additionalProperties': True,
                                             'description': '插件参数对象；数组、布尔等直接使用 JSON 值，由适配器转换现有插件参数'},
                                  'width': {'type': 'integer', 'default': 1600},
                                  'height': {'type': 'integer', 'default': 900},
                                  'browser': {'type': ['string', 'null'],
                                              'description': '浏览器路径；省略时自动查找 Chrome、Edge、Chromium'},
                                  'wait_ms': {'type': 'integer',
                                              'description': '最多等页面把图片、视频封面、波形加载完多久',
                                              'default': 20000},
                                  'timeout_ms': {'type': 'integer',
                                                 'minimum': 1,
                                                 'default': 60000,
                                                 'description': '浏览器启动至抓图的整体预算；默认60秒，关闭阶段另有短暂清理时间'},
                                  'state_root': {'type': ['string', 'null'],
                                                 'description': '视图设置、插件与缓存目录，省略沿用本机默认位置'}},
                   'additionalProperties': False,
                   'required': ['database', 'output', 'project_id']},
  'mcp': {'route': 'query',
          'group': 'view',
          'database': 'path',
          'paths': ['browser', 'output', 'state_root'],
          'handler': 'layerweave.tool.builtin.view.mcp:look',
          'omit': ['output'],
          'exposure': 'direct',
          'output': 'image',
          'variants': [{'route': 'admin',
                        'handler': 'layerweave.tool.builtin.view.mcp:save_screenshot',
                        'omit': [],
                        'exposure': 'routed',
                        'output': 'file',
                        'command': 'view_screenshot_save',
                        'paths': ['browser', 'output', 'state_root'],
                        'summary': '将视图截图保存到指定的新文件，默认不覆盖已有目标',
                        'returns': 'output 为实际绝对路径；另有 size、ready、saved=true 与 issues。',
                        'notes': ['明确提供输出路径；目标已存在时报告冲突，不覆盖。']}],
          'summary': '查看当前画布或指定插件页面，直接返回图片；不保存到指定文件',
          'returns': '图片内容块；result 包含 size/ready/saved=false/issues，不包含持久化输出路径。',
          'notes': ['只读取项目和用户视图状态；内部可能生成可重建媒体缓存。', 'params 直接传插件参数对象；需要保存时使用 view_screenshot_save。'],
          'open_world': True},
  'cli_mapping': {'params': ['param']}}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图截图（给 AI 看）", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int); p.add_argument("output", type=Path)
    p.add_argument("--lang", choices=("zh", "en"), help="截图语言；覆盖链接中的 lang，默认中文")
    p.add_argument("--view", help="canvas（画布）、layerweave.assets（选装一览）或插件的页面（比如 layerweave.cuts 接缝）；省略时是画布，给了 --link 时按链接")
    p.add_argument("--board", type=int, help="只拍这个根层所在的画板")
    p.add_argument("--begin", type=float); p.add_argument("--end", type=float)
    p.add_argument("--layers", nargs="+", help="编号、层名或 上级/名字"); p.add_argument("--playhead", type=float); p.add_argument("--select", type=int)
    p.add_argument("--focus", type=int, help="把镜头移到这个对象上"); p.add_argument("--changes", type=int, help="标出最近几次操作的改动")
    p.add_argument("--note", type=int, help="对准这条批注：框住它指的地方，右侧标出这一楼")
    p.add_argument("--link", help="用户在视图里点「复制链接」得到的地址：按它拍同一个位置")
    p.add_argument("--notes", action="store_true", help="右侧打开批注列表")
    p.add_argument("--side", help="右侧打开哪一栏：now、changes、notes、walk，或者插件的侧栏（插件的名字）")
    p.add_argument("--links", action="store_true", help="画出全部关系线"); p.add_argument("--full-page", action="store_true", help="接缝、一览页截整页")
    p.add_argument("--tree", action="store_true", help="画布左边打开目录树")
    p.add_argument("--param", action="append", metavar="名字=值", help="给插件页面的地址参数（可以写多次），比如 --view layerweave.assets --param page=3")
    p.add_argument("--width", type=int, default=1600); p.add_argument("--height", type=int, default=900)
    p.add_argument("--browser"); p.add_argument("--wait-ms", type=int, default=20000)
    p.add_argument("--timeout-ms", type=int, default=60000, help="浏览器启动至抓图的整体预算；关闭阶段另有短暂清理时间")
    p.add_argument("--state-root", type=Path, help="视图设置、插件与缓存目录；可用于独立环境")
    a = p.parse_args()
    try:
        result = capture(a.database, a.project_id, a.output, view=a.view, board=a.board, begin=a.begin, end=a.end, layers=a.layers,
                         lang=a.lang, playhead=a.playhead, select=a.select, focus=a.focus, note=a.note, link=a.link, changes=a.changes, notes=a.notes, side=a.side, links=a.links,
                         full_page=a.full_page, tree=a.tree, params=a.param, width=a.width, height=a.height,
                         browser=a.browser, wait_ms=a.wait_ms, timeout_ms=a.timeout_ms, state_root=a.state_root)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"截图失败：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

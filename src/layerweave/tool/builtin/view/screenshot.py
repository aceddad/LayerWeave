"""给 AI 用的视图截图：在后台起一个只读视图服务，用无界面浏览器打开同一个页面，存成 PNG。
AI 看到的就是用户在视图里看到的：画板的排版用用户那份（拼接、拆分、位置都一样）。
截图用的页面不记录"正在看哪儿"，也不改排版，不会覆盖用户的状态。
页面把图片、视频封面、波形都加载完才举手，截图工具通过浏览器调试接口等到它再拍，不会拍到还没出图的空色块。

python -m layerweave.tool.builtin.view.screenshot DATABASE PROJECT_ID 输出.png
       [--view canvas|cuts|assets] [--board 根层编号] [--begin 起点 --end 终点] [--layers 1 5] [--playhead 位置] [--select 对象编号]
       [--focus 对象编号] [--changes 最近几次操作] [--notes] [--links] [--full-page]
       [--width 1600 --height 900] [--browser 浏览器路径] [--wait-ms 20000]
"""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen

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


class DevTools:
    """浏览器调试接口（Chrome DevTools Protocol）的最小客户端：一条只连本机的 WebSocket，按编号收发 JSON。"""

    def __init__(self, url, timeout=30):
        parts = urlparse(url)
        self.sock = socket.create_connection((parts.hostname, parts.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {parts.path} HTTP/1.1\r\nHost: {parts.hostname}:{parts.port}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
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


def capture(database, project_id, output, *, view="canvas", board=None, begin=None, end=None, layers=None, playhead=None,
            select=None, focus=None, changes=None, notes=False, links=False, full_page=False, width=1600, height=900, browser=None,
            wait_ms=20000, state_root=None):
    browser = find_browser(browser)
    if browser is None:
        raise FileNotFoundError("找不到 Chrome、Edge 或 Chromium：用 --browser 或环境变量 LAYERWEAVE_BROWSER 指定浏览器路径")
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    server, url = make_server(database, state_root=state_root, record_state=False)
    query = {"project": project_id, "view": view if view in ("assets", "cuts") else "canvas", "record": 0, "capture": 1}
    if links:
        query["links"] = 1
    if notes:
        query["side"] = "notes"
    if full_page and view in ("assets", "cuts"):
        query["full"] = 1
    for key, value in (("board", board), ("begin", begin), ("end", end), ("playhead", playhead), ("select", select),
                       ("focus", focus), ("changes", changes)):
        if value is not None:
            query[key] = value
    if layers:
        query["layers"] = ",".join(str(i) for i in layers)
    page = url + "?" + urlencode(query)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if output.exists():
        output.unlink()   # 这是调用方指定的输出文件；先删掉，失败时不会把旧图当成新图
    try:
        # 独立的浏览器配置，不碰用户正在用的浏览器
        with tempfile.TemporaryDirectory(prefix="layerweave-shot-", ignore_cleanup_errors=True) as profile:
            process = subprocess.Popen([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio",
                                        "--no-first-run", "--no-default-browser-check", f"--user-data-dir={profile}",
                                        "--remote-debugging-port=0", f"--window-size={width},{height}", "about:blank"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                ready = _shoot(profile, page, output, width, height, wait_ms, "full" in query)
            finally:
                try:
                    process.wait(timeout=10)   # Edge 的启动器早就退出了；真正的浏览器由 Browser.close 关掉
                except subprocess.TimeoutExpired:
                    process.kill()
    finally:
        server.shutdown()
        server.server_close()
    return {"output": str(output), "page": page, "browser": browser, "size": [width, height], "ready": ready}


def _shoot(profile, page, output, width, height, wait_ms, full_page=False):
    port, browser_path = _devtools_port(profile, time.time() + 30)
    root = DevTools(f"ws://127.0.0.1:{port}{browser_path}")
    try:
        with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
            target = next(t for t in json.loads(response.read()) if t.get("type") == "page")
        tab = DevTools(target["webSocketDebuggerUrl"])
        try:
            tab.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False)
            tab.call("Page.navigate", url=page)
            ready, deadline = False, time.time() + wait_ms / 1000
            while not ready and time.time() < deadline:
                time.sleep(0.25)
                result = tab.call("Runtime.evaluate", expression="window.__layerweaveReady === true", returnByValue=True)
                ready = result.get("result", {}).get("value") is True
            if full_page:   # 整页：把窗口拉到内容的高度再拍（最多 16000 像素）
                result = tab.call("Runtime.evaluate", expression="document.documentElement.scrollHeight", returnByValue=True)
                tall = min(16000, max(height, int(result.get("result", {}).get("value") or height)))
                tab.call("Emulation.setDeviceMetricsOverride", width=width, height=tall, deviceScaleFactor=1, mobile=False)
                time.sleep(0.5)
            output.write_bytes(base64.b64decode(tab.call("Page.captureScreenshot", format="png")["data"]))
        finally:
            tab.close()
        return ready
    finally:
        try:
            root.call("Browser.close")
        except (RuntimeError, OSError):
            pass   # 浏览器关闭时会直接断开连接
        root.close()


COMMANDS = [{
    "name": "view_screenshot",
    "summary": "把视图页面截成 PNG：整张画布、某一块画板（可指定时间范围）、接缝页或素材网格；可以对准对象、标出最近的改动、画出关系线",
    "entrypoint": "layerweave.tool.builtin.view.screenshot:capture",
    "cli": "python -m layerweave.tool.builtin.view.screenshot",
    "read_only": True,
    "context": ["database", "project_id"],
    "parameters": {
        "output": {"type": "string", "required": True, "description": "由 AI 指定的 PNG 输出路径"},
        "view": {"type": "string", "description": "canvas（画布）、cuts（接缝：前后相接的画面并排）或 assets（素材网格）", "default": "canvas"},
        "board": {"type": "integer", "description": "只拍这个根层所在的画板；省略时拍整张画布"},
        "begin": {"type": "number", "description": "画板显示的起点，用这块画板的单位；和 end 一起用"},
        "end": {"type": "number", "description": "画板显示的终点"},
        "layers": {"type": "array", "description": "只显示这些层"},
        "playhead": {"type": "number", "description": "播放头位置（落在 board 指定的画板上，省略 board 时是第一块）；右侧会列出这一刻每层的内容"},
        "select": {"type": "integer", "description": "选中并展开详情的对象编号"},
        "focus": {"type": "integer", "description": "把镜头移到这个对象上（放在画面左上三分之一处）"},
        "changes": {"type": "integer", "description": "标出最近这么多次操作改过的对象和删除、移动前的位置，右侧列出改动"},
        "notes": {"type": "boolean", "description": "右侧打开批注列表（画布上的批注标记总是显示）", "default": False},
        "links": {"type": "boolean", "description": "画出全部关系线（bind）；不画时只画选中对象的", "default": False},
        "full_page": {"type": "boolean", "description": "接缝页、素材页按内容高度截整页（最多 16000 像素）", "default": False},
        "width": {"type": "integer", "default": 1600}, "height": {"type": "integer", "default": 900},
        "browser": {"type": "string", "description": "浏览器路径；省略时自动查找 Chrome、Edge、Chromium"},
        "wait_ms": {"type": "integer", "description": "最多等页面把图片、视频封面、波形加载完多久", "default": 20000},
    },
    "returns": "output、page（截图用的页面地址）、browser、size、ready（页面是否在等待时间内加载完；False 时图里可能缺缩略图）。",
    "examples": [{"cli": "python -m layerweave.tool.builtin.view.screenshot DATABASE 1 shots/all.png"},
                 {"cli": "python -m layerweave.tool.builtin.view.screenshot DATABASE 1 shots/t10.png --board 1 --begin 8 --end 14 --playhead 10"},
                 {"cli": "python -m layerweave.tool.builtin.view.screenshot DATABASE 1 shots/changes.png --changes 5"},
                 {"cli": "python -m layerweave.tool.builtin.view.screenshot DATABASE 1 shots/cuts.png --view cuts --full-page"}],
    "notes": ["截图页面不记录状态、不改排版；用户正在看哪儿请用 view_state，画板怎么排请用 view_layout。",
              "只读：起一个只监听本机的临时服务和一个独立配置的无界面浏览器，截完都关掉。",
              "左右接续的画板上，begin、end、playhead 用画板上的连续时间；view_layout 的 offset 是每一段的起点。",
              "接缝页列出同一条轨道里前后相接的图片和视频：上一段的最后一帧和下一段的第一帧并排，用来查衔接；--board、--begin、--end 可以缩小范围。"],
}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图截图（给 AI 看）", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int); p.add_argument("output", type=Path)
    p.add_argument("--view", choices=("canvas", "cuts", "assets"), default="canvas")
    p.add_argument("--board", type=int, help="只拍这个根层所在的画板")
    p.add_argument("--begin", type=float); p.add_argument("--end", type=float)
    p.add_argument("--layers", type=int, nargs="+"); p.add_argument("--playhead", type=float); p.add_argument("--select", type=int)
    p.add_argument("--focus", type=int, help="把镜头移到这个对象上"); p.add_argument("--changes", type=int, help="标出最近几次操作的改动")
    p.add_argument("--notes", action="store_true", help="右侧打开批注列表")
    p.add_argument("--links", action="store_true", help="画出全部关系线"); p.add_argument("--full-page", action="store_true", help="接缝、素材页截整页")
    p.add_argument("--width", type=int, default=1600); p.add_argument("--height", type=int, default=900)
    p.add_argument("--browser"); p.add_argument("--wait-ms", type=int, default=20000)
    a = p.parse_args()
    try:
        result = capture(a.database, a.project_id, a.output, view=a.view, board=a.board, begin=a.begin, end=a.end, layers=a.layers,
                         playhead=a.playhead, select=a.select, focus=a.focus, changes=a.changes, notes=a.notes, links=a.links,
                         full_page=a.full_page, width=a.width, height=a.height,
                         browser=a.browser, wait_ms=a.wait_ms)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"截图失败：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

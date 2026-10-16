"""预览插件在真实浏览器里：会动的 SVG 停在不同时刻、GIF 按真实帧取、静图写明不会动。只用临时项目，不记录状态。"""
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import threading
import time
import unittest
from urllib.request import urlopen
from contextlib import closing

from layerweave.support.api import initialize_database, open_database, transaction
from layerweave.tool.builtin.view.bench import _ev, _png
from layerweave.tool.builtin.view.plugins import plugin
from layerweave.tool.builtin.view.server import make_server
from layerweave.tool.builtin.view.screenshot import DevTools, QUIET, _devtools_port, find_browser

AXIS = {"unit": "秒", "precision": .001}
# 2 秒里一个方块从左走到右（SMIL）
SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50">
<rect id="box" x="0" y="10" width="20" height="30" fill="#f40"><animate attributeName="x" from="0" to="80" dur="2s" fill="freeze"/></rect>
<script>document.title = 'should not run'</script></svg>"""


def gif(frames, width=4, height=4, delay_cs=10):
    """最小的多帧 GIF：两色调色板，每帧整块一种颜色。LZW 每两个像素清一次表，码长一直是 3 位"""
    out = bytearray(b"GIF89a" + struct.pack("<HHBBB", width, height, 0x80, 0, 0) + bytes([255, 0, 0, 0, 0, 255]))
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    for color in frames:
        out += b"\x21\xf9\x04\x00" + struct.pack("<H", delay_cs) + b"\x00\x00"
        out += b"\x2c" + struct.pack("<HHHH", 0, 0, width, height) + b"\x00"
        codes, pixels = [], [color] * (width * height)
        for i in range(0, len(pixels), 2):
            codes += [4, *pixels[i:i + 2]]
        codes.append(5)
        bits = value = 0
        data = bytearray()
        for code in codes:
            value |= code << bits
            bits += 3
            while bits >= 8:
                data.append(value & 0xff)
                value >>= 8
                bits -= 8
        if bits:
            data.append(value & 0xff)
        out += b"\x02" + bytes([len(data)]) + data + b"\x00"
    return bytes(out + b"\x3b")


@unittest.skipIf(find_browser() is None, "本机没有浏览器")
class PreviewTests(unittest.TestCase):
    def test_preview_freezes_svg_and_reads_gif_frames(self):
        with tempfile.TemporaryDirectory(prefix="lw-preview-", ignore_cleanup_errors=True) as folder:
            root = Path(folder)
            (root / "move.svg").write_text(SVG, encoding="utf-8")
            (root / "blink.gif").write_bytes(gif([0, 1, 0]))
            database = initialize_database(root / "project.sqlite3")
            with closing(open_database(database)) as connection, transaction(connection) as write:
                project = write.create("project", {"name": "preview"})["id"]
                layer = write.create("layer", {"type": "image", "name": "图", "config_ref": "layers/image.toml", "axis": AXIS}, project_id=project)["id"]
                ids = {name: write.create("object", {"layer": layer, "begin": i * 10, "end": i * 10 + 2, "config_ref": "objects/image.toml",
                                                     "information": {"source": str(root / name)}}, project_id=project)["id"]
                       for i, name in enumerate(("move.svg", "blink.gif"))}
            plugin("on", "preview", root=root / "state")                         # 预览默认关着
            server, url = make_server(database, state_root=root / "state", record_state=False)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            profile = root / "browser"
            process = subprocess.Popen([find_browser(), "--headless=new", "--hide-scrollbars", "--mute-audio",
                "--no-first-run", "--no-default-browser-check", *QUIET, f"--user-data-dir={profile}",
                "--remote-debugging-port=0", "--window-size=1400,900", "about:blank"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            tab = control = None
            try:
                port, ws = _devtools_port(profile, time.time() + 30)
                control = DevTools(f"ws://127.0.0.1:{port}{ws}")
                with urlopen(f"http://127.0.0.1:{port}/json/list") as response:
                    page = next(p for p in json.loads(response.read()) if p.get("type") == "page")
                tab = DevTools(page["webSocketDebuggerUrl"], timeout=45)
                tab.call("Page.enable")

                # SVG：每半秒一张，共 5 张（0–2 秒），方块的位置一张比一张靠右；脚本被拿掉
                tab.call("Page.navigate", url=url + f"?project={project}&record=0&view=preview&object={ids['move.svg']}&step=0.5s")
                self.wait(tab, "document.querySelectorAll('.pv-cell[data-state=ready]').length===5")
                xs = _ev(tab, "[...document.querySelectorAll('.pv-cell #box')].map(r=>Math.round(r.x.animVal.value))")
                self.assertEqual(xs, [0, 20, 40, 60, 80])
                self.assertEqual(_ev(tab, "document.querySelectorAll('.pv-cell script').length"), 0)
                self.assertEqual(_ev(tab, "document.querySelector('.pv-list .pv-item.on').textContent.startsWith('move')"), True)
                self.assertIn("第 1 / 1 页", _ev(tab, "document.querySelector('.pager').textContent"))

                # GIF：逐帧就是真实的三帧，颜色 红 / 蓝 / 红
                tab.call("Page.navigate", url=url + f"?project={project}&record=0&view=preview&object={ids['blink.gif']}")
                if not _ev(tab, "typeof ImageDecoder==='function'"):
                    self.skipTest("浏览器没有 ImageDecoder")
                self.wait(tab, "document.querySelectorAll('.pv-cell[data-state=ready]').length===3")
                colors = _ev(tab, "[...document.querySelectorAll('canvas.pv-cell')].map(c=>{const d=c.getContext('2d').getImageData(c.width>>1,c.height>>1,1,1).data;return d[0]>d[2]?'红':'蓝'})")
                self.assertEqual(colors, ["红", "蓝", "红"])
                self.assertEqual(_ev(tab, "[...document.querySelectorAll('.pv-grid figcaption')].map(f=>f.textContent.split('第 ')[1])"),
                                 ["0 帧", "1 帧", "2 帧"])
            finally:
                if tab:
                    tab.close()
                if control:
                    try:
                        control.call("Browser.close")
                    except (RuntimeError, OSError):
                        pass
                    control.close()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                server.shutdown()
                server.server_close()

    def wait(self, tab, expression):
        deadline = time.time() + 20
        while time.time() < deadline:
            if _ev(tab, "Boolean(" + expression + ")"):
                return
            time.sleep(.05)
        self.fail("页面未达到预期：" + expression + " · " + str(_ev(tab, "document.querySelector('.pv-status')?.textContent")))


if __name__ == "__main__":
    unittest.main()

"""实际浏览器的吸附、取消、点击和拼接；只使用临时项目，不记录用户状态。"""
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from urllib.request import urlopen
from contextlib import closing

from layerweave.support.api import initialize_database, open_database, transaction, read_record
from layerweave.tool.builtin.view.bench import _ev, _png
from layerweave.tool.builtin.view.layout import save_layout, layout_path
from layerweave.tool.builtin.view.server import make_server
from layerweave.tool.builtin.view.screenshot import DevTools, QUIET, _devtools_port, find_browser


@unittest.skipIf(find_browser() is None, "本机没有浏览器")
class ViewInteractionTests(unittest.TestCase):
    def test_drag_snap_cancel_pick_and_merge_without_recording(self):
        with tempfile.TemporaryDirectory(prefix="lw-interaction-", ignore_cleanup_errors=True) as folder:
            root = Path(folder)
            image = root / "image.png"
            image.write_bytes(_png(64, 32, 1))
            database = initialize_database(root / "project.sqlite3")
            with closing(open_database(database)) as connection, transaction(connection) as write:
                project = write.create("project", {"name": "drag"})["id"]
                a = write.create("layer", {"type": "image", "name": "A", "config_ref": "layers/image.toml",
                                          "axis": {"unit": "秒", "precision": .001}}, project_id=project)["id"]
                b = write.create("layer", {"type": "image", "name": "B", "config_ref": "layers/image.toml",
                                          "axis": {"unit": "秒", "precision": .001}}, project_id=project)["id"]
                objects = [write.create("object", {"layer": layer, "begin": 0, "end": 10, "config_ref": "objects/image.toml",
                                                   "information": {"source": str(image)}}, project_id=project)["id"] for layer in (a, b)]
                write.create("bind", {"source_kind": "object", "source_project_id": project, "source_id": objects[0],
                                      "target_kind": "object", "target_project_id": project, "target_id": objects[1]})
            state = root / "state"
            save_layout(database, project, [{"rows": [[a]], "x": 80, "y": 120, "pps": 10},
                                            {"rows": [[b]], "x": 500, "y": 400, "pps": 10}], root=state)
            with closing(open_database(database)) as connection:
                original = {kind: read_record(connection, kind, project_id=project) for kind in ("view_layout", "view_layout_member")}
            server, url = make_server(database, state_root=state, record_state=False)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            profile = root / "browser"
            process = subprocess.Popen([find_browser(), "--headless=new", "--hide-scrollbars", "--mute-audio",
                "--no-first-run", "--no-default-browser-check", *QUIET, f"--user-data-dir={profile}",
                "--remote-debugging-port=0", "--window-size=1280,900", "about:blank"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            tab = control = None
            try:
                port, ws = _devtools_port(profile, time.time() + 30)
                control = DevTools(f"ws://127.0.0.1:{port}{ws}")
                with urlopen(f"http://127.0.0.1:{port}/json/list") as response:
                    page = next(p for p in json.loads(response.read()) if p.get("type") == "page")
                tab = DevTools(page["webSocketDebuggerUrl"], timeout=45)
                tab.call("Emulation.setDeviceMetricsOverride", width=1280, height=900, deviceScaleFactor=1, mobile=False)
                tab.call("Page.enable")
                tab.call("Page.navigate", url=url + f"?project={project}&record=0&tree=0")
                self.wait(tab, "document.querySelectorAll('.board').length===2 && document.querySelectorAll('.obj').length===2")
                # DOM 和队列短暂空闲不代表懒加载图像已经绘制；后续比较旧/新像素需要明确的初始画面。
                self.wait(tab, "document.querySelectorAll('.obj[data-media-state=ready]').length===2")
                _ev(tab, "(async()=>{await window.__layerweavePaintIdle?.();return true})()")

                def position(key):
                    return _ev(tab, f"(()=>{{const n=document.querySelector('.board[data-key=\"{key}\"]').closest('.react-flow__node');const m=new DOMMatrixReadOnly(getComputedStyle(n).transform);return {{x:m.m41,y:m.m42}};}})()")

                def rect(selector):
                    return _ev(tab, f"(()=>{{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();return {{x:r.x,y:r.y,w:r.width,h:r.height}};}})()")

                def press(x, y):
                    tab.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
                    tab.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", buttons=1, clickCount=1)

                def release(x, y):
                    tab.call("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", clickCount=1)
                    time.sleep(.15)

                def move(x, y, tx, ty):
                    # 先越过拖动启动阈值，避免一次跳几十像素被当成初始抓取位置。
                    distance = max(abs(tx-x), abs(ty-y), 1)
                    tab.call("Input.dispatchMouseEvent", type="mouseMoved", x=x+(tx-x)*4/distance, y=y+(ty-y)*4/distance,
                             button="left", buttons=1)
                    time.sleep(.03)
                    for i in range(1, 13):
                        tab.call("Input.dispatchMouseEvent", type="mouseMoved", x=x+(tx-x)*i/12, y=y+(ty-y)*i/12,
                                 button="left", buttons=1)
                        time.sleep(.01)

                # A 对齐 B 的 x；结束回调的未吸附位置不能冲回去。
                first, second = position(a), position(b)
                zoom = _ev(tab, "new DOMMatrixReadOnly(getComputedStyle(document.querySelector('.react-flow__viewport')).transform).m11")
                head = rect(f'.board[data-key="{a}"] .bhead b')
                x, y = head["x"]+5, head["y"]+head["h"]/2
                tx = x+(second["x"]+5-first["x"])*zoom
                press(x, y); move(x, y, tx, y); release(tx, y)
                self.assertAlmostEqual(position(a)["x"], second["x"], delta=.1)

                # 新位置点击：对象选择、关系线、播放头仍按当前坐标解释。
                block = rect(f'.obj[data-id="{objects[0]}"]')
                px, py = block["x"]+block["w"]/2, block["y"]+block["h"]/2
                press(px, py); release(px, py)
                self.wait(tab, f"document.querySelector('.obj[data-id=\"{objects[0]}\"]').classList.contains('sel')")
                self.wait(tab, "document.querySelector('.react-flow__edge-path')")
                error = _ev(tab, f"(()=>{{const o=document.querySelector('.obj[data-id=\"{objects[0]}\"]').getBoundingClientRect();const p=document.querySelector('.board[data-key=\"{a}\"] .playhead').getBoundingClientRect();return Math.abs(p.left-(o.left+o.width/2));}})()")
                self.assertLess(error, 3)

                # AI 保留编号更换素材；增量后共享画布必须是新图，而非旧 URL 解码缓存。
                pixel = f"""(()=>{{
                  const o=document.querySelector('.obj[data-id="{objects[0]}"]');
                  const r=o.getBoundingClientRect(), x=r.left+r.width*.25, y=r.top+r.height*.25;
                  for(const c of o.closest('.track').querySelectorAll('.media-tile')){{
                    const q=c.getBoundingClientRect();
                    if(x>=q.left&&x<q.right&&y>=q.top&&y<q.bottom)
                      return [...c.getContext('2d').getImageData(Math.floor((x-q.left)*c.width/q.width),Math.floor((y-q.top)*c.height/q.height),1,1).data];
                  }}return null;
                }})()"""
                # Dragging can replace media tiles asynchronously; wait for the sampled pixel,
                # just as the replacement-image check below waits for its actual drawing.
                self.wait(tab, f"(()=>{{const p={pixel};return p&&p[3]>0;}})()")
                old_pixel = _ev(tab, pixel)
                self.assertIsNotNone(old_pixel)
                other_image = root / "replacement.png"
                other_image.write_bytes(_png(64, 32, 99))
                with closing(open_database(database)) as connection, transaction(connection) as write:
                    write.update("object", objects[0], {"information": {"source": str(other_image)}}, project_id=project)
                self.wait(tab, f"(()=>{{const p={pixel};return p&&p[3]>0&&JSON.stringify(p)!=={json.dumps(json.dumps(old_pixel, separators=(',', ':')))};}})()")
                _ev(tab, "(async()=>{await window.__layerweavePaintIdle();return true})()")
                self.assertNotEqual(_ev(tab, pixel), old_pixel)

                # Escape 撤回，后续 mousemove/mouseup 不得把取消的位置重新提交。
                before = position(a)
                head = rect(f'.board[data-key="{a}"] .bhead b')
                x, y = head["x"]+5, head["y"]+head["h"]/2
                press(x, y); move(x, y, x+50, y+60)
                tab.call("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
                tab.call("Input.dispatchKeyEvent", type="keyUp", key="Escape", code="Escape", windowsVirtualKeyCode=27)
                move(x+50, y+60, x+80, y+70); release(x+80, y+70)
                self.assertEqual(position(a), before)

                # B 的标题拖到 A 的轨道中部，仍能上下拼接。
                head = rect(f'.board[data-key="{b}"] .bhead b')
                track = rect(f'.board[data-key="{a}"] .track')
                x, y = head["x"]+5, head["y"]+head["h"]/2
                tx, ty = track["x"]+track["w"]*.45, track["y"]+track["h"]*.7
                press(x, y); move(x, y, tx, ty); release(tx, ty)
                self.wait(tab, "document.querySelectorAll('.board').length===1")
                self.assertEqual(_ev(tab, "document.querySelectorAll('.obj').length"), 2)
                with closing(open_database(database)) as connection:
                    self.assertEqual({kind: read_record(connection, kind, project_id=project) for kind in original}, original)
                self.assertFalse(layout_path(database, state).exists())
            finally:
                if control:
                    try: control.call("Browser.close")
                    except (RuntimeError, OSError): pass
                    control.close()
                if tab: tab.close()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill()
                server.shutdown(); server.server_close()

    def wait(self, tab, expression):
        deadline = time.time() + 15
        while time.time() < deadline:
            if _ev(tab, "Boolean(" + expression + ")"): return
            time.sleep(.05)
        self.fail("页面未达到预期：" + expression)


if __name__ == "__main__":
    unittest.main()

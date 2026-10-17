"""左边目录树在真实浏览器里：列出层、点层名镜头过去、勾选连同子树、只看勾选的、列对象、收起。只用临时项目，不记录状态。"""
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from urllib.request import urlopen
from contextlib import closing

from layerweave.support.api import initialize_database, open_database, transaction
from layerweave.tool.builtin.view.bench import _ev
from layerweave.tool.builtin.view.server import make_server
from layerweave.tool.builtin.view.screenshot import DevTools, QUIET, _devtools_port, find_browser

AXIS = {"unit": "秒", "precision": .001}


@unittest.skipIf(find_browser() is None, "本机没有浏览器")
class LayerTreeTests(unittest.TestCase):
    def test_tree_lists_flies_picks_filters_and_lists_objects(self):
        with tempfile.TemporaryDirectory(prefix="lw-tree-", ignore_cleanup_errors=True) as folder:
            root = Path(folder)
            database = initialize_database(root / "project.sqlite3")
            with closing(open_database(database)) as connection, transaction(connection) as write:
                project = write.create("project", {"name": "tree"})["id"]

                def layer(name, father=None):
                    data = {"type": "text", "name": name, "config_ref": "layers/text.toml", "axis": AXIS}
                    if father is not None:
                        data["father"] = father
                    return write.create("layer", data, project_id=project)["id"]

                main = layer("成片")
                lyrics, story = layer("歌词", main), layer("故事", main)
                deep = layer("细节", story)
                other = layer("分镜")
                for target, count in ((lyrics, 3), (story, 2), (deep, 1), (other, 4)):
                    for i in range(count):
                        write.create("object", {"layer": target, "begin": i * 10, "end": i * 10 + 8, "name": f"{target}-{i}",
                                                "config_ref": "objects/text.toml", "information": {"text": f"第 {i} 句"}}, project_id=project)
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
                tab.call("Emulation.setDeviceMetricsOverride", width=1400, height=900, deviceScaleFactor=1, mobile=False)
                tab.call("Page.enable")
                tab.call("Page.navigate", url=url + f"?project={project}&record=0")
                self.wait(tab, "document.querySelectorAll('.tree-row').length===5 && document.querySelectorAll('.obj').length===10")

                def click(selector):
                    self.assertTrue(_ev(tab, f"(()=>{{const el=document.querySelector({json.dumps(selector)});if(!el)return false;el.click();return true;}})()"), selector)

                row = lambda layer_id: f".tree-row[data-layer=\"{layer_id}\"]"
                # 根、子层、孙层的次序和深度；数字：自己的 / 连同下面的
                order = _ev(tab, "[...document.querySelectorAll('.tree-row')].map(r=>r.querySelector('.tn').textContent)")
                self.assertEqual(order, ["成片", "歌词", "故事", "细节", "分镜"])
                self.assertEqual(_ev(tab, f"document.querySelector('{row(story)} .tcount').textContent"), "2 / 3")

                # 点层名：镜头过去，画布上那一行被选中（写批注时指向它）
                before = _ev(tab, "getComputedStyle(document.querySelector('.react-flow__viewport')).transform")
                click(f"{row(other)} .tn")
                self.wait(tab, f"document.querySelector('.lname.picked')?.dataset.layers==='{other}'")
                self.wait(tab, f"getComputedStyle(document.querySelector('.react-flow__viewport')).transform!=={json.dumps(before)}")
                top = _ev(tab, f"(()=>{{const p=document.querySelector('.flow').getBoundingClientRect(),r=[...document.querySelectorAll('.lname')].find(e=>e.dataset.layers==='{other}').getBoundingClientRect();return (r.top+r.bottom)/2-p.top-p.height/3}})()")
                self.assertLess(abs(top), 30)

                # 树里收起只在树里：画布上的轨道不变
                tracks = _ev(tab, "document.querySelectorAll('.lname').length")
                click(f"{row(main)} .caret")
                self.wait(tab, "document.querySelectorAll('.tree-row').length===2")
                self.assertEqual(_ev(tab, "document.querySelectorAll('.lname').length"), tracks)
                click(f"{row(main)} .caret")
                self.wait(tab, "document.querySelectorAll('.tree-row').length===5")

                # 勾"故事"连同"细节"；只看勾选的：画布上只剩这两条轨道；再点恢复
                click(f"{row(story)} input")
                self.wait(tab, "document.querySelectorAll('.tree-row.checked').length===2")
                click(".tree-tools button")
                self.wait(tab, f"[...document.querySelectorAll('.lname')].map(e=>e.dataset.layers).sort().join()==={json.dumps(','.join(sorted([str(story), str(deep)])))}")
                self.assertEqual(_ev(tab, "document.querySelectorAll('.obj').length"), 3)
                click(".tree-tools button")
                self.wait(tab, "document.querySelectorAll('.obj').length===10")

                # 列对象，点一个就选中
                click(f"{row(lyrics)} .tcount")
                self.wait(tab, "document.querySelectorAll('.tree-obj').length===3")
                click(".tree-obj")
                self.wait(tab, "document.querySelector('.obj.sel')!==null")

                # 收起整个目录，画布变宽
                width = _ev(tab, "document.querySelector('.flow').clientWidth")
                click(".tree-head button")
                self.wait(tab, f"!document.querySelector('.tree') && document.querySelector('.tree-open') && document.querySelector('.flow').clientWidth>{width}")
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
        deadline = time.time() + 15
        while time.time() < deadline:
            if _ev(tab, "Boolean(" + expression + ")"):
                return
            time.sleep(.05)
        self.fail("页面未达到预期：" + expression)


if __name__ == "__main__":
    unittest.main()

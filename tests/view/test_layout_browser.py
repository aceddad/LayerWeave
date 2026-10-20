"""A real React Flow resize gesture persists once and agrees with the headless layout API."""
from contextlib import closing
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from urllib.request import urlopen

from layerweave.support.api import initialize_database, open_database, transaction, change_cursor
from layerweave.tool.builtin.view.bench import _ev
from layerweave.tool.builtin.view.layout import arrange, save_layout
from layerweave.tool.builtin.view.server import make_server
from layerweave.tool.builtin.view.screenshot import DevTools, QUIET, _devtools_port, find_browser
from layerweave.tool.builtin.view.state import read_state


@unittest.skipIf(find_browser() is None, "本机没有浏览器")
class LayoutBrowserTests(unittest.TestCase):
    def wait(self, tab, expression):
        deadline = time.time()+20
        while time.time()<deadline:
            if _ev(tab, "Boolean("+expression+")"):
                return
            time.sleep(.1)
        self.fail("Browser condition timed out: "+expression)

    def test_resize_persists_once_reloads_and_follows_ai_update(self):
        with tempfile.TemporaryDirectory(prefix="lw-layout-ui-", ignore_cleanup_errors=True) as folder:
            base=Path(folder)
            database=initialize_database(base/"project.sqlite3")
            with closing(open_database(database)) as c, transaction(c) as w:
                project=w.create("project",{"name":"layout"})["id"]
                layer=w.create("layer",{"name":"阅读","type":"text","config_ref":"layers/text.toml",
                    "axis":{"unit":"序号","precision":1}},project_id=project)["id"]
                obj=w.create("object",{"name":"第一段","layer":layer,"begin":0,"end":10,"config_ref":"objects/text.toml",
                    "information":{"text":"一段可以换行阅读的正文。"*30}},project_id=project)["id"]
            save_layout(database,project,[{"rows":[[layer]],"x":30,"y":40,"pps":40}])
            server,url=make_server(database,state_root=base/"state",record_state=True)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            profile=base/"browser"
            process=subprocess.Popen([find_browser(),"--headless=new","--disable-gpu","--hide-scrollbars",
                "--no-first-run","--no-default-browser-check",*QUIET,f"--user-data-dir={profile}",
                "--remote-debugging-port=0","--window-size=1500,1000","about:blank"],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            tab=control=None
            try:
                port,ws=_devtools_port(profile,time.time()+30)
                control=DevTools(f"ws://127.0.0.1:{port}{ws}")
                with urlopen(f"http://127.0.0.1:{port}/json/list") as response:
                    page=next(p for p in json.loads(response.read()) if p.get("type")=="page")
                tab=DevTools(page["webSocketDebuggerUrl"],timeout=45)
                tab.call("Emulation.setDeviceMetricsOverride",width=1500,height=1000,deviceScaleFactor=1,mobile=False)
                tab.call("Page.enable")
                tab.call("Page.navigate",url=url+f"?project={project}&tree=0")
                self.wait(tab,"document.querySelector('.bhead select') && document.querySelector('.react-flow__resize-control.handle')")
                _ev(tab,"(()=>{const s=document.querySelector('.bhead select');s.value='180';s.dispatchEvent(new Event('change',{bubbles:true}));return true;})()")
                self.wait(tab,"parseFloat(document.querySelector('.obj').style.height)>170")
                deadline=time.time()+10
                while time.time()<deadline:
                    result=arrange(database,project)["boards"][0]
                    if result["styles"].get(str(layer),{}).get("lane_height")==180:break
                    time.sleep(.1)
                self.assertEqual(result["styles"][str(layer)]["lane_height"],180)
                with closing(open_database(database)) as c: before=change_cursor(c)
                handle=_ev(tab,"(()=>{const h=[...document.querySelectorAll('.react-flow__resize-control.handle')].map(x=>x.getBoundingClientRect()).sort((a,b)=>(b.x+b.y)-(a.x+a.y))[0];return {x:h.x+h.width/2,y:h.y+h.height/2};})()")
                x,y=handle["x"],handle["y"]
                hit = _ev(tab, f"document.elementFromPoint({x},{y})?.outerHTML.slice(0,700)")
                tab.call("Input.dispatchMouseEvent",type="mouseMoved",x=x,y=y)
                tab.call("Input.dispatchMouseEvent",type="mousePressed",x=x,y=y,button="left",buttons=1,clickCount=1)
                for i in range(1,11):
                    tab.call("Input.dispatchMouseEvent",type="mouseMoved",x=x+22*i,y=y+18*i,button="left",buttons=1)
                    time.sleep(.02)
                tab.call("Input.dispatchMouseEvent",type="mouseReleased",x=x+220,y=y+180,button="left",clickCount=1)
                deadline=time.time()+10
                while time.time()<deadline:
                    with closing(open_database(database)) as c: after=change_cursor(c)
                    if after>before:break
                    time.sleep(.1)
                self.assertEqual(after-before,1,"resize should create one changed style record; "+json.dumps({"handle":handle,"hit":hit,"board":_ev(tab,"document.querySelector('.board').getAttribute('style')")},ensure_ascii=False))
                result=arrange(database,project)["boards"][0]
                visual=_ev(tab,"(()=>{const b=document.querySelector('.board');return {width:parseFloat(b.style.width),height:parseFloat(b.style.height)};})()")
                self.assertGreater(result["height"],248)
                self.assertAlmostEqual(visual["width"],result["width"],delta=1)
                self.assertAlmostEqual(visual["height"],result["height"],delta=1)
                _ev(tab,"window.__beforeLayoutReload=true")
                tab.call("Page.reload",ignoreCache=True)
                self.wait(tab,f"!window.__beforeLayoutReload && document.querySelector('.board') && Math.abs(parseFloat(document.querySelector('.board').style.width)-{result['width']})<1")
                with closing(open_database(database)) as c:self.assertEqual(change_cursor(c),after)
                external=arrange(database,project,"resize",root=layer,width=900,lane_height=96)["boards"][0]
                self.wait(tab,f"Math.abs(parseFloat(document.querySelector('.board').style.height)-{external['height']})<1")
                self.assertAlmostEqual(_ev(tab,"parseFloat(document.querySelector('.board').style.width)"),900,delta=1)
                deadline=time.time()+10
                state=None
                while time.time()<deadline:
                    state=read_state(database,base/"state")
                    if state and state.get("geometry") and abs(state["geometry"][0]["width"]-900)<1:break
                    time.sleep(.1)
                self.assertAlmostEqual(state["geometry"][0]["width"],900,delta=1)
                self.assertIn("zoom",state["viewport"])
            finally:
                if control:
                    try:control.call("Browser.close")
                    except (RuntimeError,OSError):pass
                    control.close()
                if tab:tab.close()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                server.shutdown();server.server_close()

"""Live language switching preserves drafts, plugin instances and project records."""
from contextlib import closing
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from urllib.request import urlopen

from layerweave.support.api import initialize_database, open_database, transaction
from layerweave.tool.builtin.view.bench import _ev
from layerweave.tool.builtin.view.note import add_note
from layerweave.tool.builtin.view.plugins import plugin
from layerweave.tool.builtin.view.server import make_server
from layerweave.tool.builtin.view.screenshot import DevTools, QUIET, _devtools_port, find_browser


@unittest.skipIf(find_browser() is None, "本机没有浏览器")
class LanguageBrowserTests(unittest.TestCase):
    def wait(self, tab, expression):
        deadline = time.time()+20
        while time.time()<deadline:
            if _ev(tab, "Boolean("+expression+")"): return
            time.sleep(.05)
        self.fail(expression + " · " + str(_ev(tab,"document.body.textContent.slice(-2000)")))

    def switch(self, tab, lang):
        _ev(tab, f"(()=>{{const el=document.querySelector('.language');el.value='{lang}';el.dispatchEvent(new Event('change',{{bubbles:true}}));return true;}})()")
        self.wait(tab, f"document.documentElement.lang === '{'zh-CN' if lang=='zh' else lang}'")

    def test_switch_preserves_draft_and_plugin_state(self):
        with tempfile.TemporaryDirectory(prefix="lw-language-",ignore_cleanup_errors=True) as temporary:
            root=Path(temporary);state=root/'state'
            database=initialize_database(root/'project.sqlite3')
            with closing(open_database(database)) as c, transaction(c) as w:
                project=w.create('project',{'name':'中文项目'})['id']
                layer=w.create('layer',{'type':'text','config_ref':'layers/text.toml','name':'用户层','axis':{'unit':'秒'}},project_id=project)['id']
                w.create('object',{'config_ref':'objects/text.toml','layer':layer,'begin':0,'end':2,'information':{'text':'不可翻译的正文'}},project_id=project)
            add_note(database,project,'用户批注',author='中文署名')
            with closing(open_database(database)) as c: before=list(c.iterdump())
            folder=root/'demo';folder.mkdir()
            (folder/'plugin.json').write_text(json.dumps({'format':1,'kind':'view-plugin','publisher':'test','name':'language','version':'1.0.0','label':'示例','description':'示例说明','requires':{'view':'>=0.29.0','host_api':[3]},'slots':['page'],'locales':{'zh':'zh.json','en':'en.json'}}),encoding='utf-8')
            (folder/'README.md').write_text('说明',encoding='utf-8')
            for lang,title in [('zh','示例'),('en','Sample')]:
                (folder/(lang+'.json')).write_text(json.dumps({'messages':{'count':'计数 {n}' if lang=='zh' else 'Count {n}'},'display':{'label':title}}),encoding='utf-8')
            (folder/'plugin.js').write_text("""export default host => {
              window.factories=(window.factories||0)+1;host.addStyle('.language-sample{padding:20px}');
              function Page(){const {t}=host.useI18n();const [n,set]=host.React.useState(1);return host.React.createElement('button',{className:'language-sample',onClick:()=>set(n+1)},t('count',{n}));}
              return {label:'示例',page:Page};
            };""",encoding='utf-8')
            plugin('add',str(folder),root=state)
            server,url=make_server(database,state_root=state)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            profile=root/'browser'
            process=subprocess.Popen([find_browser(),'--headless=new','--mute-audio','--no-first-run','--no-default-browser-check',*QUIET,f'--user-data-dir={profile}','--remote-debugging-port=0','--window-size=1400,900','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            tab=control=None
            try:
                port,ws=_devtools_port(profile,time.time()+30);control=DevTools(f'ws://127.0.0.1:{port}{ws}')
                with urlopen(f'http://127.0.0.1:{port}/json/list') as response: page=next(p for p in json.loads(response.read()) if p.get('type')=='page')
                tab=DevTools(page['webSocketDebuggerUrl'],timeout=45);tab.call('Page.enable')
                tab.call('Page.navigate',url=url+f'?project={project}&side=notes&lang=zh&tree=1')
                self.wait(tab,"document.querySelector('.compose textarea') && window.factories===1")
                _ev(tab,"(()=>{window.documentMarker=123;const el=document.querySelector('.compose textarea');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(el,'未提交草稿');el.dispatchEvent(new Event('input',{bubbles:true}));return true;})()")
                self.switch(tab,'en')
                self.wait(tab,"document.querySelector('.compose textarea').placeholder.includes('Write a note')")
                self.assertEqual(_ev(tab,"document.querySelector('.compose textarea').value"),'未提交草稿')
                self.assertIn('中文署名',_ev(tab,'document.body.textContent'))
                self.assertIn('用户批注',_ev(tab,'document.body.textContent'))
                self.assertEqual(_ev(tab,'window.documentMarker'),123)
                self.assertIn('Sample',_ev(tab,"document.querySelector('.bar .tabs').textContent"))
                for width in (1100,1400):
                    tab.call('Emulation.setDeviceMetricsOverride',width=width,height=900,deviceScaleFactor=1,mobile=False)
                    self.assertTrue(_ev(tab,"[...document.querySelectorAll('.bar button,.bar select')].every(el=>{const r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1})"))
                    if folder_out:=os.environ.get('LW_LANGUAGE_SHOTS'):
                        out=Path(folder_out);out.mkdir(parents=True,exist_ok=True)
                        shot=tab.call('Page.captureScreenshot',format='png')['data'];(out/f'host-en-{width}.png').write_bytes(base64.b64decode(shot))
                _ev(tab,"[...document.querySelectorAll('.bar .tabs button')].find(b=>b.textContent==='Sample').click()")
                self.wait(tab,"document.querySelector('.language-sample')")
                _ev(tab,"document.querySelector('.language-sample').click()")
                self.wait(tab,"document.querySelector('.language-sample').textContent==='Count 2'")
                styles=_ev(tab,'document.querySelectorAll("style").length')
                self.switch(tab,'zh');self.wait(tab,"document.querySelector('.language-sample').textContent==='计数 2'")
                self.switch(tab,'en');self.wait(tab,"document.querySelector('.language-sample').textContent==='Count 2'")
                self.assertEqual(_ev(tab,'window.factories'),1)
                self.assertEqual(_ev(tab,'document.querySelectorAll("style").length'),styles)
                self.assertEqual(_ev(tab,"localStorage.getItem('layerweave.view.locale')"),'en')
                self.assertEqual(_ev(tab,"new URL(location.href).searchParams.get('lang')"),'en')
                with closing(open_database(database)) as c:self.assertEqual(list(c.iterdump()),before)
                tab.call('Page.addScriptToEvaluateOnNewDocument',source="Object.defineProperty(window,'localStorage',{get(){throw Error('storage disabled')}})")
                tab.call('Page.navigate',url=url+f'?project={project}&lang=en&side=notes')
                self.wait(tab,"document.querySelector('.compose textarea') && document.documentElement.lang==='en'")
                self.switch(tab,'zh')
                self.wait(tab,"document.querySelector('.compose textarea').placeholder.includes('写一条批注')")

            finally:
                if tab:tab.close()
                if control:
                    try:control.call('Browser.close')
                    except (OSError,RuntimeError):pass
                    control.close()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill()
                server.shutdown();server.server_close()

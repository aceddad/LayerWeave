"""浏览器验收只用合成插件；官方插件有自己的独立仓库测试。"""
from contextlib import closing
from pathlib import Path
import tempfile
import unittest

from layerweave.support.api import initialize_database, open_database, transaction
from layerweave.tool.builtin.view.plugins import plugin
from layerweave.tool.builtin.view.screenshot import capture, find_browser, link_query


@unittest.skipIf(find_browser() is None, "本机没有浏览器")
class PluginBrowserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.database = initialize_database(self.root / "project.sqlite3")
        with closing(open_database(self.database)) as connection, transaction(connection) as write:
            self.project = write.create("project", {"name": "插件验收"})["id"]
            write.create("layer", {"type": "text", "config_ref": "layers/text.toml", "name": "测试"}, project_id=self.project)

    def add(self, body):
        path = self.root / "sample.js"
        path.write_text(body, encoding="utf-8")
        return plugin("add", str(path), root=self.state)["added"]

    def shot(self, identity, **kwargs):
        return capture(self.database, self.project, self.root / "shot.png", view=identity,
                       width=800, height=600, state_root=self.state, wait_ms=5000, **kwargs)

    def test_nested_module_and_link_params(self):
        identity = plugin("add", str(Path(__file__).parent / "fixtures/view-plugin"), root=self.state)["added"]
        link = f"http://localhost/?project={self.project}&view={identity}&ids=%5B1%2C2%5D&capture=0&record=1"
        query = link_query(link, self.project)
        self.assertEqual(query["ids"], "[1,2]")
        self.assertNotIn("capture", query)
        shot = capture(self.database, self.project, self.root / "shot.png", link=link, params=["ids=[3,4]"],
                       width=800, height=600, state_root=self.state, wait_ms=10000)
        self.assertTrue(shot["ready"])
        self.assertIn("ids=%5B3%2C4%5D", shot["page"])

    def test_load_error_does_not_make_a_canvas_screenshot(self):
        identity = self.add("export default () => { throw new Error('intentional-load-error'); };")
        with self.assertRaisesRegex(RuntimeError, "intentional-load-error"):
            self.shot(identity)
        self.assertFalse((self.root / "shot.png").exists())

    def test_missing_page_is_not_success(self):
        identity = self.add("export default () => ({label: '只有标签'});")
        with self.assertRaisesRegex(RuntimeError, "未提供 page"):
            self.shot(identity)

    def test_render_error_is_not_success(self):
        identity = self.add("export default () => ({label:'坏页面',page:()=>{throw new Error('intentional-render-error')}});")
        with self.assertRaisesRegex(RuntimeError, "intentional-render-error"):
            self.shot(identity)

    def test_never_ready_is_not_success(self):
        identity = self.add("export default host => ({label:'等待',page:()=>host.React.createElement('p',null,'pending')});")
        with self.assertRaisesRegex(RuntimeError, "尚未画完"):
            self.shot(identity)


if __name__ == "__main__":
    unittest.main()

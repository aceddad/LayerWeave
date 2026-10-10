"""视图工具包：只读服务、素材白名单、Range、自动刷新标记、"正在看哪儿"、截图与取帧。"""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from layerweave.support.api import initialize_database, open_database, save_layer, save_object, transaction
from layerweave.models import ImageLayer, Image, TextLayer, Text
from layerweave.tool.builtin.view.data import find_ffmpeg, open_readonly
from layerweave.tool.builtin.view.screenshot import capture, find_browser
from layerweave.tool.builtin.view.server import make_server
from layerweave.tool.builtin.view.state import read_state


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-view-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / "media").mkdir()
        self.png = bytes(range(256)) * 4                       # 内容不必是真图片：服务只按引用提供文件
        (root / "media" / "a.png").write_bytes(self.png)
        self.database = initialize_database(root / "view.sqlite3")
        with closing(open_database(self.database)) as c:
            with transaction(c) as write:
                self.project = write.create("project", {"name": "视图测试"})["id"]
            main = TextLayer(name="主线", axis={"unit": "秒", "precision": 0.001})
            save_layer(c, self.project, main)
            save_object(c, self.project, Text(layer=main.id, begin=0, end=4, information={"text": "第一段"}))
            art = ImageLayer(name="原画", father=main.id)
            save_layer(c, self.project, art)
            self.image = Image(layer=art.id, begin=1, end=3, information={"source": "media/a.png"})
            save_object(c, self.project, self.image)
            self.missing = Image(layer=art.id, begin=3, end=5, information={"source": "media/none.png"})
            save_object(c, self.project, self.missing)
            self.web = Image(layer=art.id, begin=5, end=6, information={"source": "https://example.com/x.png"})
            save_object(c, self.project, self.web)
        self.main_layer, self.art_layer = main.id, art.id
        self.state_root = root / "state"
        self.server, self.url = make_server(self.database, state_root=self.state_root)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def get(self, path, headers=None):
        with urlopen(Request(self.url.rstrip("/") + path, headers=headers or {}), timeout=10) as response:
            return response.status, dict(response.headers), response.read()

    def json(self, path):
        return json.loads(self.get(path)[2])

    def test_project_view_orders_layers_and_marks_media(self):
        self.assertEqual(self.json("/api/projects")[0]["name"], "视图测试")
        data = self.json(f"/api/project/{self.project}")
        self.assertEqual([(l["name"], l["depth"]) for l in data["layers"]], [("主线", 0), ("原画", 1)])
        self.assertEqual(data["unit"], "秒")
        self.assertEqual(data["extent"], [0.0, 6.0])
        media = {o["id"]: o["media"] for o in data["layers"][1]["objects"]}
        self.assertTrue(media[self.image.id]["available"])
        self.assertEqual(media[self.image.id]["url"], f"/media/{self.project}/{self.image.id}")
        self.assertFalse(media[self.missing.id]["available"])
        self.assertIsNone(media[self.web.id]["url"])           # 网址不经本机服务提供
        self.assertEqual(data["layers"][0]["objects"][0]["text"], "第一段")
        with self.assertRaises(HTTPError) as error:
            self.get("/api/project/999")
        self.assertEqual(error.exception.code, 404)

    def test_media_is_whitelisted_and_supports_ranges(self):
        status, headers, body = self.get(f"/media/{self.project}/{self.image.id}")
        self.assertEqual((status, body), (200, self.png))
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        status, headers, body = self.get(f"/media/{self.project}/{self.image.id}", {"Range": "bytes=10-19"})
        self.assertEqual((status, body, headers["Content-Range"]), (206, self.png[10:20], f"bytes 10-19/{len(self.png)}"))
        status, _, body = self.get(f"/media/{self.project}/{self.image.id}", {"Range": "bytes=-5"})
        self.assertEqual((status, body), (206, self.png[-5:]))
        for path in (f"/media/{self.project}/{self.missing.id}", f"/media/{self.project}/999", "/media/999/1"):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.get(path)
            self.assertEqual(error.exception.code, 404)

    def test_static_page_and_capabilities(self):
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("LayerWeave", body.decode("utf-8"))
        self.assertEqual(self.json("/api/capabilities"), {"frames": find_ffmpeg() is not None})

    def test_version_changes_after_another_connection_writes(self):
        before = self.json("/api/version")["version"]
        self.assertEqual(self.json("/api/version")["version"], before)
        with closing(open_database(self.database)) as c:
            save_object(c, self.project, Text(layer=self.main_layer, begin=4, end=5, information={"text": "新的一段"}))
        self.assertNotEqual(self.json("/api/version")["version"], before)

    def test_server_connection_is_read_only(self):
        with closing(open_readonly(self.database)) as c:
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("UPDATE projects SET name = 'x'")

    def test_state_is_recorded_only_when_allowed(self):
        body = json.dumps({"project": self.project, "view": "timeline", "range": [0, 4], "playhead": 2.5,
                           "selected": {"id": self.image.id, "layer": self.art_layer, "name": ""}, "junk": "ignored"}).encode()
        request = Request(self.url + "api/state", data=body, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=10) as response:
            self.assertEqual(json.loads(response.read())["playhead"], 2.5)
        state = read_state(self.database, self.state_root)
        self.assertEqual((state["project"], state["range"], state["selected"]["id"]), (self.project, [0, 4], self.image.id))
        self.assertNotIn("junk", state)
        quiet, url = make_server(self.database, state_root=self.state_root, record_state=False)
        threading.Thread(target=quiet.serve_forever, daemon=True).start()
        try:
            other = json.dumps({"project": self.project, "playhead": 9}).encode()
            with urlopen(Request(url + "api/state", data=other), timeout=10) as response:
                self.assertEqual(json.loads(response.read()), {"recorded": False})
        finally:
            quiet.shutdown(); quiet.server_close()
        self.assertEqual(read_state(self.database, self.state_root)["playhead"], 2.5)

    @unittest.skipIf(find_browser() is None, "本机没有 Chrome、Edge 或 Chromium")
    def test_screenshot_writes_png_without_touching_state(self):
        output = Path(self.temp.name) / "shots" / "t.png"
        result = capture(self.database, self.project, output, playhead=2, width=1000, height=600, wait_ms=2000)
        self.assertTrue(output.is_file())
        self.assertEqual(output.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertIn("record=0", result["page"])
        self.assertIsNone(read_state(self.database, self.state_root))


if __name__ == "__main__":
    unittest.main()

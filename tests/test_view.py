"""视图工具包：只读服务、素材白名单、Range、自动刷新标记、画板排版、"正在看哪儿"、截图与取帧。"""

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
from layerweave.tool.builtin.view.data import axis_key, find_ffmpeg, open_readonly
from layerweave.tool.builtin.view.layout import arrange, chain_offsets, layout_path, merge, reconcile, split
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
            voice = TextLayer(name="旁白", axis={"unit": "s"})            # 和主线同一种单位（写法不同）
            save_layer(c, self.project, voice)
            save_object(c, self.project, Text(layer=voice.id, begin=2, end=8, information={"text": "旁白"}))
            board = TextLayer(name="分镜", axis={"unit": "帧", "precision": 1})
            save_layer(c, self.project, board)
            save_object(c, self.project, Text(layer=board.id, begin=0, end=48, information={"text": "镜头一"}))
        self.main_layer, self.art_layer, self.voice, self.board = main.id, art.id, voice.id, board.id
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
        self.assertEqual([(l["name"], l["depth"], l["root"]) for l in data["layers"]],
                         [("主线", 0, self.main_layer), ("原画", 1, self.main_layer), ("旁白", 0, self.voice), ("分镜", 0, self.board)])
        self.assertEqual([(r["id"], r["unit"], r["key"], r["extent"]) for r in data["roots"]],
                         [(self.main_layer, "秒", "秒", [0, 6]), (self.voice, "s", "秒", [2, 8]), (self.board, "帧", "帧", [0, 48])])
        media = {o["id"]: o["media"] for o in data["layers"][1]["objects"]}
        self.assertTrue(media[self.image.id]["available"])
        self.assertEqual(media[self.image.id]["url"], f"/media/{self.project}/{self.image.id}")
        self.assertFalse(media[self.missing.id]["available"])
        self.assertIsNone(media[self.web.id]["url"])           # 网址不经本机服务提供
        self.assertEqual(data["layers"][0]["objects"][0]["text"], "第一段")
        with self.assertRaises(HTTPError) as error:
            self.get("/api/project/999")
        self.assertEqual(error.exception.code, 404)

    def test_layout_groups_roots_by_unit_and_keeps_user_choices(self):
        self.assertEqual([axis_key(a) for a in ({"unit": "秒"}, {"unit": " Seconds "}, {"unit": "frame"}, {"unit": "拍"}, {}, None)],
                         ["秒", "秒", "帧", "拍", None, None])
        roots = [{"id": 1, "key": "秒", "name": "a", "unit": "秒"}, {"id": 2, "key": "秒", "name": "b", "unit": "s"},
                 {"id": 3, "key": "帧", "name": "c", "unit": "帧"}, {"id": 4, "key": None, "name": "d", "unit": ""},
                 {"id": 5, "key": None, "name": "e", "unit": ""}]
        rows = lambda boards: [b["rows"] for b in boards]
        self.assertEqual(rows(reconcile(roots, None)), [[[1], [2]], [[3]], [[4]], [[5]]])   # 同单位上下拼；没有单位的各占一块
        saved = [{"roots": [2], "x": 10, "y": 20, "pps": 50},                            # 旧格式：一列根
                 {"rows": [[1, 3], [99]], "x": 0, "y": 400}]
        boards = reconcile(roots, saved)                      # 用户拆开的保持拆开；单位不同的被分开；已删除的根被去掉
        self.assertEqual(rows(boards), [[[2]], [[1]], [[3]], [[4]], [[5]]])
        self.assertEqual((boards[0]["x"], boards[0]["y"], boards[0]["pps"]), (10.0, 20.0, 50.0))
        more = roots + [{"id": 6, "key": "秒", "name": "f", "unit": "秒"}]
        self.assertEqual(rows(reconcile(more, saved))[0], [[2], [6]])   # 新根作为新的一行并进同单位的第一块
        merge(boards, roots, 1, 2, "above")
        self.assertEqual(rows(boards)[:2], [[[1], [2]], [[3]]])
        with self.assertRaisesRegex(ValueError, "单位不同"):
            merge(boards, roots, 3, 1)
        with self.assertRaisesRegex(ValueError, "单位不同"):
            merge(boards, roots, 4, 5)                        # 没有单位的根不能拼
        split(boards, 1)
        self.assertEqual(rows(boards)[:3], [[[2]], [[1]], [[3]]])
        with self.assertRaisesRegex(ValueError, "已经单独"):
            split(boards, 1)
        merge(boards, roots, 1, 2, "right")                   # 左右接续：1 接在 2 后面
        self.assertEqual(rows(boards)[0], [[2, 1]])
        boards.append({"rows": [[7], [8]], "x": None, "y": None, "pps": None})
        more = roots + [{"id": 7, "key": "秒", "name": "g", "unit": "秒"}, {"id": 8, "key": "秒", "name": "h", "unit": "秒"}]
        with self.assertRaisesRegex(ValueError, "好几行"):
            merge(boards, more, 7, 2, "left")                 # 多行的画板不能左右接
        merge(boards, more, 7, 1, "below")
        self.assertEqual(rows(boards)[0], [[2, 1], [7], [8]])
        split(boards, 1)                                      # 从接续里拆出：后面的段补上
        self.assertEqual(rows(boards)[0], [[2], [7], [8]])
        self.assertEqual(chain_offsets([1, 2, 3], {1: (0, 16), 2: (0.5, 10), 3: (-1, 5)}), {1: 0, 2: 16, 3: 27})

    def test_layout_is_shared_between_page_and_tool(self):
        url = f"/api/layout/{self.project}"
        layout = self.json(url)
        self.assertEqual([b["rows"] for b in layout["boards"]], [[[self.main_layer], [self.voice]], [[self.board]]])
        self.assertFalse(layout_path(self.database, self.state_root).exists())     # 只读取时不写文件
        before = self.json("/api/version")["layout"]
        result = arrange(self.database, self.project, "split", root=self.voice, state_root=self.state_root)
        ids = lambda result: [[[r["id"] for r in row] for row in b["rows"]] for b in result["boards"]]
        self.assertEqual(ids(result), [[[self.main_layer]], [[self.voice]], [[self.board]]])
        self.assertNotEqual(self.json("/api/version")["layout"], before)          # 网页靠它发现 AI 改了排版
        result = arrange(self.database, self.project, "merge", root=self.voice, target=self.main_layer, side="right",
                         state_root=self.state_root)
        self.assertEqual(ids(result)[0], [[self.main_layer, self.voice]])
        self.assertEqual([r["offset"] for r in result["boards"][0]["rows"][0]], [0, 6])   # 旁白的 0 接在主线结尾（6 秒）
        self.assertIn("从画板 6 起", result["text"])
        boards = [{"rows": [[self.main_layer, self.board], [self.voice]], "x": 5, "y": 6}]  # 网页传来不合规的拼接
        request = Request(self.url + url.lstrip("/"), data=json.dumps({"boards": boards}).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=10) as response:
            saved = json.loads(response.read())["boards"]
        self.assertEqual([b["rows"] for b in saved], [[[self.main_layer], [self.voice]], [[self.board]]])
        self.assertEqual(self.json(url)["boards"], saved)
        with self.assertRaisesRegex(ValueError, "不是这个项目的根层"):
            arrange(self.database, self.project, "split", root=self.art_layer, state_root=self.state_root)
        arrange(self.database, self.project, "reset", state_root=self.state_root)
        self.assertEqual([b["x"] for b in self.json(url)["boards"]], [None, None])

    def test_recent_changes_show_moves_edits_and_deletes(self):
        with closing(open_database(self.database)) as c:
            with transaction(c) as write:
                write.update("object", self.image.id, {"begin": 1.5, "end": 3.5}, project_id=self.project)
            with transaction(c) as write:
                write.update("object", self.missing.id, {"information": {"source": "media/a.png"}}, project_id=self.project)
            with transaction(c) as write:
                write.delete("object", self.web.id, project_id=self.project)
        ops = self.json(f"/api/changes/{self.project}?limit=3")
        self.assertEqual(len(ops), 3)
        delete, edit, move = (op["items"][0] for op in ops)    # 新的在前
        self.assertEqual((delete["action"], delete["id"], delete["after"]), ("delete", self.web.id, None))
        self.assertEqual((delete["before"]["layer"], delete["before"]["begin"], delete["before"]["source"]),
                         (self.art_layer, 5, "https://example.com/x.png"))
        self.assertEqual(edit["fields"], ["information"])
        self.assertEqual(edit["information"], [{"key": "source", "before": "media/none.png", "after": "media/a.png"}])
        self.assertEqual((move["before"]["begin"], move["after"]["begin"], move["fields"]), (1, 1.5, ["begin", "end"]))
        self.assertEqual(len(self.json(f"/api/changes/{self.project}?limit=1")), 1)
        self.assertEqual(self.json("/api/changes/999"), [])

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
            boards = json.dumps({"boards": [{"roots": [self.voice]}]}).encode()
            with urlopen(Request(url + f"api/layout/{self.project}", data=boards), timeout=10) as response:
                self.assertEqual(json.loads(response.read()), {"recorded": False})
        finally:
            quiet.shutdown(); quiet.server_close()
        self.assertEqual(read_state(self.database, self.state_root)["playhead"], 2.5)
        self.assertFalse(layout_path(self.database, self.state_root).exists())

    @unittest.skipIf(find_browser() is None, "本机没有 Chrome、Edge 或 Chromium")
    def test_screenshot_writes_png_without_touching_state(self):
        output = Path(self.temp.name) / "shots" / "t.png"
        result = capture(self.database, self.project, output, board=self.board, playhead=2, focus=self.image.id, changes=3,
                         width=1000, height=600, wait_ms=15000, state_root=self.state_root)
        self.assertTrue(output.is_file())
        self.assertEqual(output.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertIn("record=0", result["page"])
        self.assertIn(f"board={self.board}", result["page"])
        self.assertIn("changes=3", result["page"])
        self.assertTrue(result["ready"])                                           # 页面加载完才拍
        self.assertIsNone(read_state(self.database, self.state_root))
        self.assertFalse(layout_path(self.database, self.state_root).exists())     # 截图页面不改排版


if __name__ == "__main__":
    unittest.main()

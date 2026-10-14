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

from layerweave.support.api import initialize_database, open_database, read_record, run_operation, save_layer, save_object, transaction
from layerweave.models import Audio, ImageLayer, Image, Movie, TextLayer, Text
from layerweave.tool.builtin.view.data import axis_key, extract_frame, find_ffmpeg, open_readonly, project_view, recent_changes
from layerweave.tool.builtin.view.fold import fold
from layerweave.tool.builtin.view.layout import arrange, chain_offsets, layout_path, merge, reconcile, split
from layerweave.tool.builtin.view.note import add_note, list_notes, note, remove_note, threads, update_note, waiting_for
from layerweave.tool.builtin.view.notes import AXIS, LAYER_REF, OBJECT_REF
from layerweave.tool.builtin.view.screenshot import capture, find_browser, link_query, resolve_layers
from layerweave.tool.builtin.view.server import make_server
from layerweave.tool.builtin.view.state import read_state
from layerweave.tool.builtin.view.at import read_at
from layerweave.tool.builtin.view.walk import read_along


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
            first = Text(layer=main.id, begin=0, end=4, information={"text": "第一段"})
            save_object(c, self.project, first)
            self.text_at_0 = first.id
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
            with transaction(c) as write:
                write.create("bind", {"source_kind": "object", "source_project_id": self.project, "source_id": self.image.id,
                                      "target_kind": "layer", "target_project_id": self.project, "target_id": main.id,
                                      "tips": "这张图属于主线"})
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
        self.assertEqual(data["binds"], [{"id": data["binds"][0]["id"], "tips": "这张图属于主线",
                                          "source": {"kind": "object", "project": self.project, "id": self.image.id},
                                          "target": {"kind": "layer", "project": self.project, "id": self.main_layer}}])
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

    @unittest.skipIf(find_ffmpeg() is None, "本机没有 ffmpeg")
    def test_frames_can_be_taken_from_the_end_of_a_video(self):
        import subprocess
        video = Path(self.temp.name) / "media" / "red_blue.mp4"      # 前半秒红、后半秒蓝
        subprocess.run([find_ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=64x48:d=0.5:r=10",
                        "-f", "lavfi", "-i", "color=c=blue:s=64x48:d=0.5:r=10", "-filter_complex", "[0][1]concat=n=2:v=1",
                        "-pix_fmt", "yuv420p", str(video)], check=True, capture_output=True)
        first, last, beyond = (extract_frame(video, t, width=64) for t in (0, "end", 99))
        self.assertEqual(last, beyond)                                 # 超出时长时取最后一帧，而不是退回开头
        self.assertNotEqual(first, last)
        self.assertEqual(last[:2], bytes([0xFF, 0xD8]))
        with closing(open_database(self.database)) as c:
            clip = Movie(layer=self.art_layer, begin=6, end=7, information={"source": "media/red_blue.mp4"})
            save_object(c, self.project, clip)
        status, headers, body = self.get(f"/frame/{self.project}/{clip.id}?t=end")
        self.assertEqual((status, headers["Content-Type"]), (200, "image/jpeg"))

    @unittest.skipIf(find_ffmpeg() is None, "本机没有 ffmpeg")
    def test_thumbnails_are_scaled_cached_and_fall_back_to_the_original(self):
        import struct
        import subprocess
        big = Path(self.temp.name) / "media" / "big.png"                     # 1000×600，带透明
        subprocess.run([find_ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "color=c=red@0.5:s=1000x600:d=1,format=rgba",
                        "-frames:v", "1", str(big)], check=True, capture_output=True)
        with closing(open_database(self.database)) as c:
            pic = Image(layer=self.art_layer, begin=7, end=8, information={"source": "media/big.png"})
            save_object(c, self.project, pic)
        status, headers, body = self.get(f"/thumb/{self.project}/{pic.id}?w=300")
        self.assertEqual((status, headers["Content-Type"]), (200, "image/png"))           # 带透明的缩成 PNG
        self.assertEqual(struct.unpack(">II", body[16:24]), (320, 192))                    # 300 取到 320 这一档，高按比例
        cached = list((Path(self.state_root) / "thumbs").glob("*.png"))
        self.assertEqual(len(cached), 1)                                                  # 存在本机视图目录，第二次直接读
        self.assertEqual(self.get(f"/thumb/{self.project}/{pic.id}?w=320")[2], body)
        status, _, body = self.get(f"/thumb/{self.project}/{self.image.id}?w=320")        # 解不开的"图"：送原图
        self.assertEqual((status, body), (200, self.png))
        with self.assertRaises(HTTPError) as error:
            self.get(f"/thumb/{self.project}/{self.missing.id}")
        self.assertEqual(error.exception.code, 404)

    @unittest.skipIf(find_ffmpeg() is None, "本机没有 ffmpeg")
    def test_waveforms_are_computed_by_the_server_and_cached(self):
        import subprocess
        song = Path(self.temp.name) / "media" / "quiet_loud.wav"           # 前一秒小声、后一秒大声
        subprocess.run([find_ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "sine=f=440:d=1,volume=0.05",
                        "-f", "lavfi", "-i", "sine=f=440:d=1,volume=0.8", "-filter_complex", "[0][1]concat=n=2:v=0:a=1",
                        str(song)], check=True, capture_output=True)
        with closing(open_database(self.database)) as c:
            clip = Audio(layer=self.art_layer, begin=8, end=10, information={"source": "media/quiet_loud.wav"})
            save_object(c, self.project, clip)
        rms = self.json(f"/wave/{self.project}/{clip.id}")["rms"]
        self.assertEqual(len(rms), 800)
        self.assertGreater(sum(rms[500:700]), 5 * sum(rms[100:300]))                      # 后半段明显更响
        self.assertEqual(len(list((Path(self.state_root) / "waves").glob("*.json"))), 1)
        with self.assertRaises(HTTPError) as error:                                          # 解不开：404，页面退回自己解码
            self.get(f"/wave/{self.project}/{self.image.id}")
        self.assertEqual(error.exception.code, 404)

    def test_note_types_are_registered_in_core_configs_by_the_view(self):
        from layerweave.support.configuration.loader import Loader
        from layerweave.tool.builtin.view.notes.models import Note, NoteLayer
        loader = Loader()
        layer, obj = loader.load(LAYER_REF, "layer"), loader.load(OBJECT_REF, "object")
        self.assertEqual((layer["type"], obj["type"]), ("note", "note"))
        self.assertIn("layers/text.toml", layer["_lineage"])                            # 继承核心的文字层
        self.assertEqual(layer["display"], {"visibility": True, "default_visible": False})
        self.assertEqual((LAYER_REF, OBJECT_REF), ("layers/note.toml", "objects/note.toml"))   # 登记在核心的配置目录
        self.assertEqual((layer["requires"], obj["requires"]), ("layerweave.tool.builtin.view",) * 2)
        self.assertEqual(layer["objects"], "note")
        self.assertTrue(loader.accepts_object(layer, obj))
        self.assertFalse(loader.accepts_object(layer, loader.load("objects/text.toml", "object")))   # 批注层只装批注
        self.assertEqual(set(obj["information"]), {"text", "status", "author", "span"})
        self.assertTrue(issubclass(NoteLayer, TextLayer) and issubclass(Note, Text))
        self.assertTrue((Path(loader.root) / LAYER_REF).is_file() and (Path(loader.root) / OBJECT_REF).is_file())

    def test_notes_are_an_ordered_list_that_points_at_things(self):
        from layerweave.support.api import load_layer
        from layerweave.tool.builtin.usage.validation.recheck import recheck
        first = add_note(self.database, self.project, "球应该落在桌子下面", targets=[("object", self.project, self.image.id)],
                         author="用户")
        second = add_note(self.database, self.project, "这两秒空着", targets=[("layer", self.project, self.main_layer)], span=(5, 3))
        whole = add_note(self.database, self.project, "整体再紧一点")
        reply = add_note(self.database, self.project, "已改", targets=[("object", self.project, first["note"])], author="Claude")
        self.assertEqual([first["index"], second["index"], whole["index"], reply["index"]], [0, 1, 2, 3])   # 接在最后
        self.assertEqual(len({first["layer"], second["layer"], whole["layer"]}), 1)                   # 只建一个批注层
        with closing(open_readonly(self.database)) as c:
            notes = list_notes(c, self.project)
            layer = read_record(c, "layer", project_id=self.project, id=first["layer"])
        self.assertEqual((layer["type"], layer["config_ref"], layer["father"], layer["axis"]), ("note", LAYER_REF, None, AXIS))
        self.assertEqual([n["text"] for n in notes], ["球应该落在桌子下面", "这两秒空着", "整体再紧一点", "已改"])
        self.assertEqual(notes[0]["targets"][0]["id"], self.image.id)
        self.assertEqual(notes[1]["span"], {"begin": 3.0, "end": 5.0})
        self.assertEqual(notes[2]["targets"], [])
        self.assertEqual(notes[3]["targets"][0]["id"], first["note"])                                  # 回复：关联到另一条批注
        update_note(self.database, self.project, first["note"], status="done")
        update_note(self.database, self.project, whole["note"], text="整体再紧一点点")
        with closing(open_readonly(self.database)) as c:
            self.assertEqual([n["id"] for n in list_notes(c, self.project, "done")], [first["note"], reply["note"]])   # 按楼过滤，回复跟着楼主
            self.assertEqual(list_notes(c, self.project)[2]["text"], "整体再紧一点点")
        remove_note(self.database, self.project, first["note"])                                        # 删掉它，连同发出的关联
        with closing(open_readonly(self.database)) as c:
            notes = list_notes(c, self.project)
            self.assertNotIn(first["note"], [n["id"] for n in notes])
            self.assertEqual(notes[-1]["targets"][0]["exists"], False)                                  # 回复还在，目标已删除
            self.assertEqual(read_record(c, "bind", filters={"source_id": first["note"], "source_kind": "object"}), [])
        with closing(open_database(self.database)) as c:
            self.assertEqual(type(load_layer(c, self.project, first["layer"])).__name__, "NoteLayer")
            issues = recheck(c, self.project)["issues"]
            # 唯一的提醒：回复指向的那条批注被删了。回复保留，检测如实报告关联端点不存在
            self.assertEqual([(i["code"], i["severity"]) for i in issues], [("bind_reference_missing", "warn")])
        data = self.json(f"/api/project/{self.project}")
        flags = {l["name"]: (l["role"], l["hidden"]) for l in data["layers"]}
        self.assertEqual((flags["批注"], flags["主线"]), (("note", True), (None, False)))
        for bad, message in (({"targets": [("object", self.project, 999)]}, "没有对象"), ({"span": (1, 2)}, "span"),
                             ({}, None)):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, message or "正文"):
                add_note(self.database, self.project, "x" if message else "  ", **bad)
        with self.assertRaisesRegex(ValueError, "不是这个项目批注层里的批注"):
            update_note(self.database, self.project, self.image.id, status="done")
        self.assertIn("整体再紧一点点", note(self.database, self.project)["text"])
        with closing(open_database(self.database)) as c:                                          # 往批注层放普通文字：检测报错
            with transaction(c) as write:
                write.create("object", {"config_ref": "objects/text.toml", "layer": first["layer"], "begin": 9, "end": 10,
                                        "information": {"text": "普通文字"}}, project_id=self.project)
            self.assertIn("accepts_objects", [i["rule"] for i in recheck(c, self.project)["issues"]])

    def test_notes_form_threads_and_show_who_should_answer(self):
        top = add_note(self.database, self.project, "要补图吗？", targets=[("layer", self.project, self.main_layer)],
                       span=(4, 6), author="Claude")["note"]
        answer = note(self.database, self.project, "reply", text="先空着", note_id=top, author="用户")["note"]
        again = note(self.database, self.project, "reply", text="好", note_id=answer, author="Claude")["note"]
        other = add_note(self.database, self.project, "节奏再紧一点", author="用户")["note"]
        with closing(open_readonly(self.database)) as c:
            notes = list_notes(c, self.project)
        by = {n["id"]: n for n in notes}
        self.assertEqual((by[answer]["reply_to"], by[again]["reply_to"], by[other]["reply_to"]), (top, answer, None))
        self.assertEqual({by[i]["thread"] for i in (top, answer, again)}, {top})
        self.assertEqual([(t["id"], [r["id"] for r in rs]) for t, rs in threads(notes)], [(top, [answer, again]), (other, [])])
        self.assertEqual({n["thread"] for n in waiting_for(notes, "Claude")}, {other})       # Claude 刚回过的楼不用等
        self.assertEqual({n["thread"] for n in waiting_for(notes, "用户")}, {top})
        text = note(self.database, self.project, waiting="Claude")["text"]
        self.assertIn("第 2 楼", text)                                                       # 只列一部分时也用全部楼里的号
        self.assertNotIn("要补图吗", text)
        listing = note(self.database, self.project)["text"]
        self.assertIn("3 楼", listing)
        self.assertIn("回复 2 楼", listing)
        update_note(self.database, self.project, top, status="done")                          # 整楼已处理：按楼主过滤
        with closing(open_readonly(self.database)) as c:
            self.assertEqual({n["id"] for n in list_notes(c, self.project, "done")}, {top, answer, again})
        with self.assertRaisesRegex(ValueError, "不是这个项目批注层里的批注"):
            note(self.database, self.project, "reply", text="x", note_id=self.image.id)

    def test_read_marks_are_per_person_and_reset_by_new_replies(self):
        top = add_note(self.database, self.project, "这里要改吗？", author="用户")["note"]
        other = add_note(self.database, self.project, "顺便看看这个", author="用户")["note"]
        waiting = lambda: {n["thread"] for n in note(self.database, self.project, waiting="Claude")["notes"]}
        self.assertEqual(waiting(), {top, other})
        with closing(open_readonly(self.database)) as c:
            before = read_record(c, "project", id=self.project)["max_id"]
        marked = note(self.database, self.project, "read", note_id=top, author="Claude")
        self.assertEqual((marked["thread"], marked["last"]), (top, top))
        self.assertEqual(waiting(), {other})                                                 # 读过了：不再算等 Claude
        self.assertEqual({n["thread"] for n in note(self.database, self.project, waiting="另一个AI")["notes"]}, {top, other})
        with closing(open_readonly(self.database)) as c:                                      # 各记各的，身份就是楼主，不占项目编号
            self.assertEqual(read_record(c, "project", id=self.project)["max_id"], before)
            self.assertEqual(project_view(c, self.database, self.project)["noteReads"], {str(top): {"Claude": top}})
        later = note(self.database, self.project, "reply", text="补一句", note_id=top, author="用户")["note"]
        self.assertEqual(waiting(), {top, other})                                            # 有人再写一条：又算没读
        note(self.database, self.project, "read", note_id=later, author="Claude")              # 按回复标也是整楼
        self.assertEqual(waiting(), {other})
        note(self.database, self.project, "unread", note_id=top, author="Claude")
        self.assertEqual(waiting(), {top, other})
        with self.assertRaisesRegex(ValueError, "是谁"):
            note(self.database, self.project, "read", note_id=top)
        # 已处理的楼默认不列，要 status=done / all 才看得到
        update_note(self.database, self.project, top, status="done")                          # 第几楼按全部楼数，和网页一致
        self.assertIn("第 2 楼", note(self.database, self.project)["text"])
        update_note(self.database, self.project, top, status="open")
        update_note(self.database, self.project, other, status="done")
        self.assertEqual({n["thread"] for n in note(self.database, self.project)["notes"]}, {top})
        self.assertEqual({n["thread"] for n in note(self.database, self.project, status="done")["notes"]}, {other})
        self.assertEqual({n["thread"] for n in note(self.database, self.project, status="all")["notes"]}, {top, other})
        with self.assertRaisesRegex(ValueError, "status"):
            note(self.database, self.project, status="closed")
        # 网页按署名标已读
        body = json.dumps({"action": "read", "note": top, "reader": "用户"}).encode()
        with urlopen(Request(self.url + f"api/notes/{self.project}", data=body), timeout=10) as response:
            self.assertEqual(json.loads(response.read())["reader"], "用户")
        with closing(open_readonly(self.database)) as c:
            self.assertEqual(project_view(c, self.database, self.project)["noteReads"][str(top)]["用户"], later)

    def test_screenshot_layers_by_name_or_path(self):
        with closing(open_database(self.database)) as c:
            again = ImageLayer(name="原画", father=self.voice)                     # 另一个根下面也有"原画"
            save_layer(c, self.project, again)
        self.assertEqual(resolve_layers(self.database, self.project, ["旁白", str(self.board)]), [self.voice, self.board])
        self.assertEqual(resolve_layers(self.database, self.project, ["主线/原画", "旁白/原画"]), [self.art_layer, again.id])
        with self.assertRaisesRegex(ValueError, "有 2 个"):
            resolve_layers(self.database, self.project, ["原画"])
        with self.assertRaisesRegex(ValueError, "没有叫"):
            resolve_layers(self.database, self.project, ["没有这层"])
        with self.assertRaisesRegex(ValueError, "没有层 #"):
            resolve_layers(self.database, self.project, ["99999"])

    def test_at_reads_every_layer_at_a_moment(self):
        top = add_note(self.database, self.project, "这张图对吗", targets=[("object", self.project, self.image.id)], author="用户")["note"]
        band = add_note(self.database, self.project, "这两秒", targets=[("layer", self.project, self.art_layer)], span=(1.5, 2.5))["note"]
        add_note(self.database, self.project, "后面的事", targets=[("layer", self.project, self.art_layer)], span=(7, 8))
        at = read_at(self.database, self.project, root=self.main_layer, at=2)
        m = at["moments"][0]
        self.assertEqual([(r["layer"]["name"], [o["id"] for o in r["objects"]]) for r in m["layers"]],
                         [("主线", [self.text_at_0]), ("原画", [self.image.id])])
        image = m["layers"][1]["objects"][0]
        self.assertEqual((image["outside"], image["noted"]), (1, True))          # 图指着主线这一层（不在这一刻里）；有批注指着它
        self.assertEqual(sorted(n["id"] for n in m["notes"]), sorted([top, band]))   # 圈的时间不重叠的那条不算
        self.assertIn("1–3 秒", at["text"])
        # 没东西的层写是哪种空
        later = read_at(self.database, self.project, root=self.main_layer, at=7)["moments"][0]
        self.assertEqual([r["gap"]["kind"] for r in later["layers"]], ["after", "after"])
        self.assertIn("已经结束：最后一个在 6 秒 结束", read_at(self.database, self.project, root=self.main_layer, at=7)["text"])
        gap = read_at(self.database, self.project, root=self.voice, at=1)["moments"][0]["layers"][0]["gap"]
        self.assertEqual(gap["kind"], "before")
        # 一段：和这一段重叠的都算
        span = read_at(self.database, self.project, root=self.main_layer, range=(3.5, 5.5))["moments"][0]
        self.assertEqual([o["id"] for o in span["layers"][1]["objects"]], [self.missing.id, self.web.id])
        # 不给根：读用户在视图里看的地方
        from layerweave.tool.builtin.view.state import write_state
        write_state(self.database, {"project": self.project, "playhead_at": [{"root": self.main_layer, "name": "主线", "local": 2.0}]},
                    self.state_root)
        here = read_at(self.database, self.project, state_root=self.state_root)
        self.assertTrue(here["from_view"])
        self.assertEqual(here["moments"][0]["begin"], 2.0)
        write_state(self.database, {"project": self.project, "selection": {"root": self.main_layer, "name": "主线", "begin": 3.5, "end": 5.5}},
                    self.state_root)
        self.assertEqual(read_at(self.database, self.project, state_root=self.state_root)["moments"][0]["end"], 5.5)
        # 网页：几段一起读
        page = self.json(f"/api/at/{self.project}?span={self.main_layer}:2:2&span={self.voice}:3:3")
        self.assertEqual([m["root"] for m in page["moments"]], [self.main_layer, self.voice])
        with self.assertRaisesRegex(ValueError, "根层"):
            read_at(self.database, self.project, root=self.art_layer, at=2)
        with self.assertRaisesRegex(ValueError, "--at"):
            read_at(self.database, self.project, root=self.main_layer)

    def test_retarget_keeps_the_thread(self):
        top = add_note(self.database, self.project, "挂错了", targets=[("object", self.project, self.image.id)], author="用户")["note"]
        reply = note(self.database, self.project, "reply", text="嗯", note_id=top, author="Claude")["note"]
        note(self.database, self.project, "read", note_id=top, author="用户")
        moved = note(self.database, self.project, "edit", note_id=top, to=[f"layer:{self.main_layer}"], span=(8, 6))
        self.assertEqual(moved["targets"], [f"layer:{self.main_layer}"])
        notes = {n["id"]: n for n in note(self.database, self.project)["notes"]}
        self.assertEqual([(t["kind"], t["id"]) for t in notes[top]["targets"]], [("layer", self.main_layer)])
        self.assertEqual(notes[top]["span"], {"begin": 6.0, "end": 8.0})                      # 起止写反了也认
        self.assertEqual((notes[reply]["thread"], notes[top]["text"]), (top, "挂错了"))          # 楼、回复、正文都在
        with closing(open_readonly(self.database)) as c:
            self.assertIn(str(top), project_view(c, self.database, self.project)["noteReads"])   # 已读记录还在
        # 改回对象、同时改正文；去掉圈的时间
        note(self.database, self.project, "edit", text="改了", note_id=top, to=[f"object:{self.image.id}"])
        notes = {n["id"]: n for n in note(self.database, self.project)["notes"]}
        self.assertEqual(([(t["kind"], t["id"]) for t in notes[top]["targets"]], notes[top]["span"], notes[top]["text"]),
                         ([("object", self.image.id)], None, "改了"))
        with self.assertRaisesRegex(ValueError, "回复"):
            note(self.database, self.project, "edit", note_id=reply, to=[f"object:{self.image.id}"])
        with self.assertRaisesRegex(ValueError, "没有对象"):
            note(self.database, self.project, "edit", note_id=top, to=["object:99999"])
        with self.assertRaisesRegex(ValueError, "span"):
            note(self.database, self.project, "edit", note_id=top, to=[f"object:{self.image.id}"], span=(1, 2))
        # 网页：改成写给整个项目
        body = json.dumps({"action": "retarget", "note": top, "targets": []}).encode()
        with urlopen(Request(self.url + f"api/notes/{self.project}", data=body), timeout=10) as response:
            self.assertEqual(json.loads(response.read())["targets"], [])
        self.assertEqual({n["id"]: n for n in note(self.database, self.project)["notes"]}[top]["targets"], [])

    def test_walk_reads_along_relations_step_by_step(self):
        top = add_note(self.database, self.project, "这张图要换吗？", targets=[("object", self.project, self.image.id)], author="用户")["note"]
        reply = note(self.database, self.project, "reply", text="先不换", note_id=top, author="Claude")["note"]
        walked = read_along(self.database, self.project, f"object:{top}")
        steps = {s["ref"]: s for s in walked["steps"]}
        self.assertEqual([(s["ref"], s["depth"]) for s in walked["steps"]],
                         [(f"object:{top}", 0), (f"object:{self.image.id}", 1), (f"object:{reply}", 1), (f"layer:{self.main_layer}", 2)])
        self.assertEqual(steps[f"object:{top}"]["note"]["author"], "用户")
        self.assertEqual(steps[f"object:{self.image.id}"]["via"][0]["arrow"], "from")         # 楼主指着这张图
        self.assertEqual(steps[f"object:{reply}"]["via"][0]["arrow"], "to")                   # 回复指着楼主
        self.assertTrue(steps[f"object:{reply}"]["note"]["reply"])
        self.assertIsNone(steps[f"object:{reply}"]["note"]["status"])                         # 整楼的状态记在楼主上
        self.assertEqual(steps[f"layer:{self.main_layer}"]["via"][0]["tips"], "这张图属于主线")
        self.assertEqual(steps[f"object:{self.image.id}"]["source"], "media/a.png")
        text = walked["text"]
        self.assertIn(f"← #{top} 指着它", text)
        self.assertIn(f"→ 它指着 #{top}", text)
        self.assertIn("1–3 秒", text)
        # 只顺着关联的方向：读不到回复；步数到了写明还有几条没走；数量到了写明几个没列出
        out = read_along(self.database, self.project, f"object:{top}", direction="out")
        self.assertEqual([s["ref"] for s in out["steps"]], [f"object:{top}", f"object:{self.image.id}", f"layer:{self.main_layer}"])
        short = read_along(self.database, self.project, f"object:{top}", depth=1)
        self.assertEqual((short["beyond"], len(short["steps"])), (1, 3))
        self.assertIn("还连着 1 条关联没走", short["text"])
        few = read_along(self.database, self.project, f"object:{top}", max_nodes=2)
        self.assertEqual((len(few["steps"]), few["skipped"]), (2, 2))
        # 成环：回复也指着这张图，同一张图只列一次，多出来的关联记成环
        with closing(open_database(self.database)) as c, transaction(c) as write:
            write.create("bind", {"source_kind": "object", "source_project_id": self.project, "source_id": reply,
                                  "target_kind": "object", "target_project_id": self.project, "target_id": self.image.id, "tips": ""})
        looped = read_along(self.database, self.project, f"object:{top}")
        self.assertEqual((len(looped["steps"]), looped["loops"]), (4, 1))
        # 网页用同一份结果
        page = self.json(f"/api/walk/{self.project}?from=object:{top}&depth=1")
        self.assertEqual([s["ref"] for s in page["steps"]], [f"object:{top}", f"object:{self.image.id}", f"object:{reply}"])
        with self.assertRaisesRegex(ValueError, "不存在"):
            read_along(self.database, self.project, "object:99999")
        with self.assertRaisesRegex(ValueError, "方向"):
            read_along(self.database, self.project, f"object:{top}", direction="up")

    def test_page_writes_notes_only_when_allowed(self):
        body = json.dumps({"action": "add", "text": "页面写的", "targets": [{"kind": "object", "id": self.image.id}],
                           "author": "用户"}).encode()
        request = Request(self.url + f"api/notes/{self.project}", data=body, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=10) as response:
            written = json.loads(response.read())
        self.assertIn("operation_id", written)
        quiet, url = make_server(self.database, state_root=self.state_root, record_state=False)   # 截图用的服务不写
        threading.Thread(target=quiet.serve_forever, daemon=True).start()
        try:
            with urlopen(Request(url + f"api/notes/{self.project}", data=body), timeout=10) as response:
                self.assertEqual(json.loads(response.read()), {"recorded": False})
        finally:
            quiet.shutdown(); quiet.server_close()
        with closing(open_readonly(self.database)) as c:
            self.assertEqual([n["text"] for n in list_notes(c, self.project)], ["页面写的"])
        bad = Request(self.url + f"api/notes/{self.project}", data=json.dumps({"action": "add", "text": ""}).encode())
        with self.assertRaises(HTTPError) as error:
            urlopen(bad, timeout=10)
        self.assertEqual(error.exception.code, 400)

    def test_folds_are_two_sided_view_records_named_after_their_layer(self):
        self.assertEqual(fold(self.database, self.project)["folds"], [])                  # 从没折叠过：还没有表
        with closing(open_readonly(self.database)) as c:
            before = read_record(c, "project", id=self.project)["max_id"]
        done = fold(self.database, self.project, "fold", layers=[self.art_layer], by="Claude", why="先对字幕")
        self.assertEqual(done["changed"], [self.art_layer])
        self.assertEqual(done["folds"], [{"layer": self.art_layer, "user": "", "user_tips": "", "ai": "Claude", "ai_tips": "先对字幕"}])
        self.assertEqual(fold(self.database, self.project, "fold", layers=[self.art_layer], by="Claude", why="先对字幕")["changed"], [])
        with self.assertRaisesRegex(ValueError, "没有层"):
            fold(self.database, self.project, "fold", layers=[99999])
        with self.assertRaisesRegex(ValueError, "不替用户折叠"):
            fold(self.database, self.project, "fold", layers=[self.art_layer], side="user")
        with closing(open_readonly(self.database)) as c:
            row = read_record(c, "view_layer", project_id=self.project, id=self.art_layer)   # 身份就是层的（项目，编号）
            self.assertEqual((row["ai_fold"], row["ai_tips"], row["user_fold"]), ("Claude", "先对字幕", ""))
            self.assertEqual(read_record(c, "project", id=self.project)["max_id"], before)   # 不占项目编号
            self.assertEqual(project_view(c, self.database, self.project)["folds"], done["folds"])
            kinds = {item["kind"] for op in recent_changes(c, self.project, 10) for item in op["items"]}
            self.assertNotIn("view_layer", kinds)                                             # "改动"面板不列折叠

        def post(url, body):
            with urlopen(Request(url + f"api/folds/{self.project}", data=json.dumps(body).encode()), timeout=10) as response:
                return json.loads(response.read())

        # 网页是人这边：自己折叠、写备注；AI 那边只能展开，不能替 AI 折叠
        post(self.url, {"action": "fold", "side": "user", "layers": [self.art_layer], "by": "用户", "tips": "太乱"})
        both = post(self.url, {"action": "tips", "side": "user", "layers": [self.art_layer], "tips": "先不看图"})["folds"][0]
        self.assertEqual((both["user"], both["user_tips"], both["ai"]), ("用户", "先不看图", "Claude"))   # 两边各一份
        with self.assertRaises(HTTPError) as refused:
            post(self.url, {"action": "fold", "side": "ai", "layers": [self.main_layer]})
        self.assertEqual(refused.exception.code, 400)
        self.assertEqual(post(self.url, {"action": "unfold", "side": "ai", "layers": [self.art_layer]})["folds"][0]["ai"], "")   # 人让 AI 看回来
        # AI 把用户折叠的层展开给用户看：写了理由就在那一层留一条批注
        shown = fold(self.database, self.project, "unfold", layers=[self.art_layer], side="user", by="Claude", why="这张图要你看一下")
        self.assertEqual(shown["folds"], [])
        with closing(open_readonly(self.database)) as c:
            told = [n for n in list_notes(c, self.project) if "这张图要你看一下" in n["text"]]
        self.assertEqual(len(told), 1)
        # 截图用的服务不写
        quiet, url = make_server(self.database, state_root=self.state_root, record_state=False)
        threading.Thread(target=quiet.serve_forever, daemon=True).start()
        try:
            self.assertEqual(post(url, {"action": "fold", "side": "user", "layers": [self.art_layer]}), {"recorded": False})
        finally:
            quiet.shutdown(); quiet.server_close()
        # 不声明引用：折叠着的层照样能被删掉；留下的记录不碍事
        with closing(open_database(self.database)) as c:
            empty = run_operation(c, lambda w: w.create("layer", {"type": "text", "config_ref": "layers/text.toml", "name": "空层",
                                                                  "father": self.main_layer}, project_id=self.project))["data"]["id"]
        fold(self.database, self.project, "fold", layers=[empty])
        with closing(open_database(self.database)) as c:
            self.assertTrue(run_operation(c, lambda w: w.delete("layer", empty, project_id=self.project))["ok"])
        self.assertEqual([f["layer"] for f in fold(self.database, self.project)["folds"]], [empty])

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
        cuts = capture(self.database, self.project, Path(self.temp.name) / "shots" / "cuts.png", view="cuts", full_page=True,
                       links=True, width=900, height=400, wait_ms=15000, state_root=self.state_root)
        self.assertTrue(cuts["ready"])
        self.assertIn("view=cuts", cuts["page"])
        self.assertIn("full=1", cuts["page"])
        said = add_note(self.database, self.project, "这张图换一下", targets=[("object", self.project, self.image.id)], author="用户")["note"]
        aimed = capture(self.database, self.project, Path(self.temp.name) / "shots" / "note.png", note=said,
                        width=1000, height=600, wait_ms=15000, state_root=self.state_root)
        self.assertTrue(aimed["ready"])
        self.assertIn(f"note={said}", aimed["page"])
        link = f"http://127.0.0.1:8765/?project={self.project}&view=cuts&board={self.board}&select={self.image.id}&record=1"
        linked = capture(self.database, self.project, Path(self.temp.name) / "shots" / "link.png", link=link,
                         width=1000, height=600, wait_ms=15000, state_root=self.state_root)
        self.assertTrue(linked["ready"])
        for part in ("view=cuts", f"board={self.board}", f"select={self.image.id}", "record=0"):   # 链接里的 record=1 不算数
            self.assertIn(part, linked["page"])

    def test_screenshot_link_keeps_only_view_parameters(self):
        link = f"http://127.0.0.1:8765/?project={self.project}&board=1&begin=8&end=14&select=16&note=42&record=1&capture=0&x=1"
        self.assertEqual(link_query(link, self.project), {"board": "1", "begin": "8", "end": "14", "select": "16", "note": "42"})
        with self.assertRaisesRegex(ValueError, "链接是项目"):
            link_query(f"http://127.0.0.1:8765/?project={self.project + 1}&board=1", self.project)


if __name__ == "__main__":
    unittest.main()

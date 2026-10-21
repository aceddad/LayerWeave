"""Real project preparation, persistence, downloads and thin CLI delegation."""
from contextlib import closing, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from layerweave.support.api import open_database, read_record, transaction, change_cursor
from layerweave.tool.builtin.shared.launcher import catalog as sources
from layerweave.tool.builtin.shared.launcher.__main__ import main
from layerweave.tool.builtin.shared.launcher.projects import prepare_demo, prepare_new, prepare, existing


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "中文 project with spaces"

    def test_bundled_demo_never_downloads_and_reopening_keeps_records_and_media(self):
        with patch.object(sources, "urlopen", side_effect=AssertionError("must be offline")):
            first = prepare_demo(directory=self.folder)
        self.assertTrue(first["created"])
        with closing(open_database(first["database"])) as c:
            objects = read_record(c, "object", project_id=first["project_id"])
            self.assertEqual(len(objects), 32)
            identity = objects[0]["id"]
            with transaction(c) as write:
                write.update("object", identity, {"tips": "用户保留的修改"}, project_id=first["project_id"])
            cursor = change_cursor(c)
        asset = self.folder / "assets/article.md"
        asset.write_text("用户修改的素材", encoding="utf-8")
        before = hashlib.sha256(first["database"].read_bytes()).hexdigest()
        with patch.object(sources, "copy_example", side_effect=AssertionError("must not copy twice")):
            second = prepare_demo(directory=self.folder)
        self.assertFalse(second["created"])
        self.assertEqual(hashlib.sha256(second["database"].read_bytes()).hexdigest(), before)
        self.assertEqual(second["project_id"], first["project_id"])
        with closing(open_database(second["database"])) as c:
            self.assertEqual(change_cursor(c), cursor)
            self.assertEqual(len(read_record(c, "object", project_id=second["project_id"])), 32)
            self.assertEqual(read_record(c, "object", project_id=second["project_id"], id=identity)["tips"], "用户保留的修改")
        self.assertEqual(asset.read_text(encoding="utf-8"), "用户修改的素材")

    def test_project_folder_can_be_moved_without_reimport(self):
        original = prepare_demo(directory=self.folder)
        moved = self.root / "moved"
        self.folder.rename(moved)
        reopened = prepare_demo(directory=moved)
        self.assertFalse(reopened["created"])
        self.assertEqual(reopened["project_id"], original["project_id"])
        self.assertEqual(reopened["database"].parent, moved)

    def test_unrelated_or_different_project_directory_is_preserved(self):
        self.folder.mkdir()
        user_file = self.folder / "keep.txt"
        user_file.write_text("keep")
        with self.assertRaisesRegex(ValueError, "Choose another"):
            prepare_demo(directory=self.folder)
        self.assertEqual(list(self.folder.iterdir()), [user_file])
        other = self.root / "other"
        prepare_demo(directory=other)
        with self.assertRaisesRegex(ValueError, "different project"):
            prepare_new(other)

    def test_missing_database_or_project_is_reported_not_recreated(self):
        prepared = prepare_demo(directory=self.folder)
        prepared["database"].unlink()
        with self.assertRaisesRegex(ValueError, "Database not found"):
            prepare_demo(directory=self.folder)
        self.assertFalse(prepared["database"].exists())
        other = self.root / "other"
        prepare_demo(directory=other)
        marker = json.loads((other / "layerweave.json").read_text())
        marker["project_id"] = 999
        (other / "layerweave.json").write_text(json.dumps(marker))
        with self.assertRaisesRegex(ValueError, "Project not found"):
            existing(other)

    def test_failure_does_not_leave_a_half_created_destination(self):
        def bad(staging):
            (staging / "partial.txt").write_text("partial")
            raise OSError("download interrupted")
        with self.assertRaisesRegex(OSError, "interrupted"):
            prepare(self.folder, "demo", "broken", bad)
        self.assertFalse(self.folder.exists())
        self.assertFalse(list(self.root.glob(".layerweave-*")))
        self.assertTrue(prepare_demo(directory=self.folder)["created"])

    def test_template_reopens_same_project(self):
        first = prepare_new(self.folder, "subtitles")
        with closing(open_database(first["database"])) as c, transaction(c) as write:
            write.update("project", first["project_id"], {"name": "edited"})
        second = prepare_new(self.folder, "subtitles")
        with closing(open_database(second["database"])) as c:
            self.assertEqual(read_record(c, "project", id=second["project_id"])["name"], "edited")
        self.assertFalse(second["created"])

    def test_cli_delegates_to_the_existing_view_with_saved_identity(self):
        with patch("layerweave.tool.builtin.view.server.serve") as serve, redirect_stdout(io.StringIO()):
            self.assertEqual(main(["demo", "--dir", str(self.folder), "--no-browser"]), 0)
            serve.assert_called_once_with(self.folder / "project.sqlite3", port=0, project=1, open_browser=False)
            serve.reset_mock()
            self.assertEqual(main(["view", str(self.folder)]), 0)
            self.assertTrue(serve.call_args.kwargs["open_browser"])

    def test_cli_unknown_project_does_not_start_a_server(self):
        prepared = prepare_demo(directory=self.folder)
        with patch("layerweave.tool.builtin.view.server.serve") as serve, self.assertRaises(SystemExit) as done:
            main(["view", str(prepared["database"]), "--project", "999"])
        self.assertEqual(done.exception.code, 1)
        serve.assert_not_called()

    def test_listing_is_offline_and_does_not_create_a_project(self):
        with patch.object(sources, "urlopen", side_effect=AssertionError("no network")), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["demo", "--list"]), 0)
        self.assertIn("article-reading", output.getvalue())
        self.assertIn("comic-creation", output.getvalue())
        self.assertFalse(self.folder.exists())

    def test_cli_mcp_reuses_parser_and_restores_argv(self):
        import sys
        old = sys.argv
        with patch("layerweave.tool.builtin.shared.mcp.__main__.main", return_value=0) as delegate:
            self.assertEqual(main(["mcp", "--list"]), 0)
        delegate.assert_called_once()
        self.assertIs(sys.argv, old)

    def test_view_browser_opening_is_opt_in_and_service_closes(self):
        from threading import Event
        from layerweave.tool.builtin.view.server import serve
        prepared = prepare_demo(directory=self.folder)
        opened = Event()
        server = Mock()
        server.serve_forever.side_effect = KeyboardInterrupt
        with patch('layerweave.tool.builtin.view.server.make_server', return_value=(server, 'http://127.0.0.1:12345/')):
            with patch('webbrowser.open', side_effect=lambda url: opened.set()) as browser, redirect_stdout(io.StringIO()):
                serve(prepared['database'])
                browser.assert_not_called()
                serve(prepared['database'], project=prepared['project_id'], open_browser=True)
                self.assertTrue(opened.wait(2))
                browser.assert_called_once_with('http://127.0.0.1:12345/?project=' + str(prepared['project_id']))
        self.assertEqual(server.server_close.call_count, 2)

    def test_download_cache_is_verified_reused_and_can_recover(self):
        payload = b"a downloaded archive"
        spec = {"url": "https://example.invalid/cases.zip", "sha256": hashlib.sha256(payload).hexdigest()}
        cache = self.root / "cache"
        with patch.object(sources, "urlopen", return_value=io.BytesIO(b"wrong")):
            with self.assertRaisesRegex(ValueError, "checksum"):
                sources.cached_archive(spec, cache=cache)
        self.assertFalse(list(cache.iterdir()))
        with patch.object(sources, "urlopen", return_value=io.BytesIO(payload)):
            archive = sources.cached_archive(spec, cache=cache)
        with patch.object(sources, "urlopen", side_effect=AssertionError("cache should work offline")):
            self.assertEqual(sources.cached_archive(spec, cache=cache), archive)
        self.assertEqual(archive.read_bytes(), payload)

    def test_selected_remote_case_is_extracted_and_imported_once(self):
        buffer = io.BytesIO()
        document = {"format_version": 1, "project": {"op": "add", "data": {"name": "downloaded"}}, "items": []}
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("showcases/remote/project.json", json.dumps(document))
            archive.writestr("showcases/remote/assets/data.txt", "keep")
            archive.writestr("showcases/remote/README.md", "[guide](../README.md#setup)")
            archive.writestr("showcases/unselected/other.txt", "not selected")
        payload = buffer.getvalue()
        data = {"items": [{"name": "remote", "bundled": False}],
                "archive": {"version": "0.7.8", "url": "https://example.invalid/cases.zip", "sha256": hashlib.sha256(payload).hexdigest()}}
        with patch.object(sources, "catalog", return_value=data), patch.object(sources, "urlopen", return_value=io.BytesIO(payload)):
            made = prepare_demo("remote", self.folder, cache=self.root / "cache")
        self.assertTrue(made["created"])
        self.assertTrue((self.folder / "assets/data.txt").is_file())
        self.assertIn("/blob/v0.7.8/examples/showcases/README.md#setup", (self.folder / "README.md").read_text())
        self.assertFalse((self.folder / "unselected").exists())
        with patch.object(sources, "urlopen", side_effect=AssertionError("must reopen offline")):
            self.assertFalse(prepare_demo("remote", self.folder)["created"])

    def test_downloaded_case_cannot_escape_its_new_directory(self):
        archive = self.root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("showcases/remote/../../outside.txt", "outside")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            sources.extract_case(archive, "remote", self.folder)
        self.assertFalse((self.root / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()

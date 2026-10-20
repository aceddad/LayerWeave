"""Local HTML previews use scoped, temporary routes and do not write project state."""
from contextlib import closing
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from layerweave.support.api import initialize_database, open_database, change_cursor
from layerweave.tool.builtin.view.server import make_server


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = self.root/"site"
        (self.site/"pages").mkdir(parents=True)
        self.page = self.site/"pages/阅读 页面.html"
        self.page.write_text('<link rel="stylesheet" href="../style.css"><h1>阅读</h1>', encoding="utf-8")
        (self.site/"style.css").write_text("h1{color:green}", encoding="utf-8")
        (self.site/"module.mjs").write_text("export const title='reading';", encoding="utf-8")
        (self.root/"outside.txt").write_text("outside", encoding="utf-8")
        self.db = initialize_database(self.root/"test.sqlite3")
        self.server, self.url = make_server(self.db, state_root=self.root/"state", record_state=False)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def mount(self, data, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        with urlopen(Request(self.url+"api/documents", data=json.dumps(data).encode(), headers=headers)) as response:
            return json.load(response)

    def test_relative_unicode_path_and_resource_root(self):
        mounted = self.mount({"file": "site/pages/阅读 页面.html", "root": "site"})
        with urlopen(self.url.rstrip("/")+mounted["url"]) as response:
            self.assertIn("阅读", response.read().decode())
            self.assertIn("sandbox", response.headers["Content-Security-Policy"])
            self.assertNotIn("allow-same-origin", response.headers["Content-Security-Policy"])
        prefix = mounted["url"].split("/pages/")[0]
        for name, ctype in (("style.css", "text/css"), ("module.mjs", "text/javascript")):
            with urlopen(self.url.rstrip("/")+prefix+"/"+name) as response:
                self.assertIn(ctype, response.headers["Content-Type"])
                self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    def test_reuse_same_directory_without_database_or_state_writes(self):
        with closing(open_database(self.db)) as c:
            before = change_cursor(c)
        a = self.mount({"file": str(self.page)})
        b = self.mount({"file": str(self.page)})
        self.assertEqual(a, b)
        with closing(open_database(self.db)) as c:
            self.assertEqual(change_cursor(c), before)
        self.assertFalse((self.root/"state").exists())
        with urlopen(self.url+"api/projects") as response:
            self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_path_escape_and_unknown_mount_are_not_served(self):
        page = self.mount({"file": str(self.page), "root": str(self.site)})
        prefix = page["url"].split("/pages/")[0]
        for tail in ("/%2e%2e/outside.txt", "/%2e%2e%5coutside.txt"):
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.url.rstrip("/")+prefix+tail)
            self.assertEqual(caught.exception.code, 404)
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.url+"documents/unknown/page.html")
        self.assertEqual(caught.exception.code, 404)

    def test_symlink_cannot_escape_mounted_root(self):
        target = self.site/"escape.txt"
        try:
            target.symlink_to(self.root/"outside.txt")
        except OSError:
            self.skipTest("Symlink privilege unavailable")
        mounted = self.mount({"file": str(self.page), "root": str(self.site)})
        prefix = mounted["url"].split("/pages/")[0]
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.url.rstrip("/")+prefix+"/escape.txt")
        self.assertEqual(caught.exception.code, 404)

    def test_missing_non_html_and_incompatible_root(self):
        for data in ({}, {"file": "missing.html"}, {"file": "outside.txt"},
                     {"file": str(self.page), "root": str(self.root/"elsewhere")}):
            with self.subTest(data=data), self.assertRaises(HTTPError) as caught:
                self.mount(data)
            self.assertEqual(caught.exception.code, 400)

    def test_remote_and_opaque_origins_cannot_open_local_files(self):
        for origin in ("https://example.org", "null"):
            with self.assertRaises(HTTPError) as caught:
                self.mount({"file": str(self.page)}, origin)
            self.assertEqual(caught.exception.code, 403)

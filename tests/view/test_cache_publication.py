"""多个对象使用同一素材时，Windows 缓存替换竞争不应变成媒体加载失败。"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from layerweave.tool.builtin.view import data


class CachePublicationTests(unittest.TestCase):
    def test_concurrent_thumbnail_winner_can_be_reused_on_replace_denied(self):
        with tempfile.TemporaryDirectory(prefix="layerweave-cache-publish-") as folder:
            root = Path(folder)
            source = root / "source.png"
            source.write_bytes(b"fixture")
            barrier, lock = threading.Barrier(2), threading.Lock()
            replace = data.os.replace
            def rendered(*args, **kwargs):
                barrier.wait(timeout=5)
                return SimpleNamespace(returncode=0, stdout=b"complete thumbnail")
            def windows_replace(temp, cached):
                with lock:
                    if Path(cached).exists():
                        raise PermissionError("Windows: completed target is held by another reader")
                    return replace(temp, cached)
            with patch("subprocess.run", side_effect=rendered), patch.object(data.os, "replace", side_effect=windows_replace):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: data.thumbnail(source, 160, root / "cache", ffmpeg="fake"), range(2)))
            self.assertEqual(results, [(b"complete thumbnail", "image/png")] * 2)
            self.assertEqual(len(list((root / "cache/thumbs").glob("*.png"))), 1)
            self.assertEqual(list((root / "cache/thumbs").glob("*.tmp")), [])

    def test_permission_failure_without_a_completed_cache_still_raises(self):
        with tempfile.TemporaryDirectory(prefix="layerweave-cache-denied-") as folder:
            root = Path(folder)
            source = root / "source.png"
            source.write_bytes(b"fixture")
            with patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"complete")), \
                    patch.object(data.os, "replace", side_effect=PermissionError("unwritable")):
                with self.assertRaisesRegex(PermissionError, "unwritable"):
                    data.thumbnail(source, 160, root / "cache", ffmpeg="fake")

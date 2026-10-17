"""缩略图大图档位：mock FFmpeg 命令与缓存，不需要编码器或浏览器。"""
from pathlib import Path
from subprocess import CompletedProcess
import tempfile
import unittest
from unittest.mock import patch

from layerweave.tool.builtin.view.data import thumbnail


class ThumbnailQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-thumbnail-quality-")
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "synthetic.png"
        self.source.write_bytes(b"synthetic source; codec is mocked")
        self.cache = Path(self.temp.name) / "cache"

    def test_request_above_1280_uses_2048_and_preserves_no_upscale_filter(self):
        result = CompletedProcess([], 0, b"mocked-png-2048", b"")
        with patch("subprocess.run", return_value=result) as run:
            got = thumbnail(self.source, 1600, self.cache, ffmpeg="test-ffmpeg")
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("-vf") + 1], "scale='min(2048,iw)':-2")
        self.assertEqual(command[command.index("-i") + 1], str(self.source))
        self.assertEqual(command[command.index("-vcodec") + 1], "png")
        self.assertEqual(got, (b"mocked-png-2048", "image/png"))
        self.assertEqual(run.call_args.kwargs, {"capture_output": True, "timeout": 60})

    def test_largest_requests_share_one_cache_entry_but_keep_lower_tiers(self):
        def encode(command, **_):
            return CompletedProcess(command, 0, command[command.index("-vf") + 1].encode(), b"")
        with patch("subprocess.run", side_effect=encode) as run:
            high = thumbnail(self.source, 1281, self.cache, ffmpeg="test-ffmpeg")
            self.assertEqual(thumbnail(self.source, 2048, self.cache, ffmpeg="test-ffmpeg"), high)
            self.assertEqual(thumbnail(self.source, 8192, self.cache, ffmpeg="test-ffmpeg"), high)
            self.assertEqual(run.call_count, 1)
            medium = thumbnail(self.source, 1280, self.cache, ffmpeg="test-ffmpeg")
            small = thumbnail(self.source, 300, self.cache, ffmpeg="test-ffmpeg")
            self.assertEqual(medium[0], b"scale='min(1280,iw)':-2")
            self.assertEqual(small[0], b"scale='min(320,iw)':-2")
            self.assertEqual(run.call_count, 3)
        self.assertEqual(len(list((self.cache / "thumbs").glob("*.png"))), 3)

    def test_source_version_still_invalidates_the_largest_cached_tier(self):
        with patch("subprocess.run", side_effect=[CompletedProcess([], 0, b"first", b""), CompletedProcess([], 0, b"second", b"")]) as run:
            self.assertEqual(thumbnail(self.source, 2048, self.cache, ffmpeg="test-ffmpeg")[0], b"first")
            self.source.write_bytes(b"changed synthetic source with a different byte length")
            self.assertEqual(thumbnail(self.source, 2048, self.cache, ffmpeg="test-ffmpeg")[0], b"second")
            self.assertEqual(run.call_count, 2)

    def test_jpeg_codec_and_original_fallback_are_unchanged(self):
        source = self.source.with_suffix(".jpg")
        source.write_bytes(b"synthetic jpeg input")
        with patch("subprocess.run", return_value=CompletedProcess([], 0, b"jpeg", b"")) as run:
            self.assertEqual(thumbnail(source, 2048, self.cache, ffmpeg="test-ffmpeg"), (b"jpeg", "image/jpeg"))
            command = run.call_args.args[0]
            self.assertEqual(command[command.index("-vcodec") + 1], "mjpeg")
            self.assertEqual(command[command.index("-q:v") + 1], "4")
        with patch("subprocess.run", return_value=CompletedProcess([], 1, b"", b"invalid image")):
            self.assertIsNone(thumbnail(self.source, 2048, self.cache, ffmpeg="test-ffmpeg"))
        with patch("layerweave.tool.builtin.view.data.find_ffmpeg", return_value=None), patch("subprocess.run") as run:
            self.assertIsNone(thumbnail(self.source, 2048, self.cache))
            self.assertIsNone(thumbnail(self.source.with_suffix(".svg"), 2048, self.cache, ffmpeg="test-ffmpeg"))
            self.assertIsNone(thumbnail(self.source.with_suffix(".gif"), 2048, self.cache, ffmpeg="test-ffmpeg"))
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""视频技能的任务恢复和 HTTP 反馈；只用模拟服务、临时文件，不访问真实 API。"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from layerweave.support.paths import SKILLS_ROOT


class VideoSkillTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("review_video_skill", SKILLS_ROOT / "layers/movie/video-generate/scripts/video.py")
        self.video = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.video)
        folder = tempfile.TemporaryDirectory(prefix="layerweave-video-skill-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.prompt = self.root / "prompt.txt"
        self.prompt.write_text("test prompt", encoding="utf-8")
        self.output = self.root / "AI-chosen-output" / "clip.mp4"
        self.connection = Mock()
        self.stderr = io.StringIO()
        self.stdout = io.StringIO()

    def main(self, *args):
        with patch.object(self.video, "Connection", return_value=self.connection), \
                patch.object(sys, "argv", ["video.py", *map(str, args)]), \
                contextlib.redirect_stderr(self.stderr), contextlib.redirect_stdout(self.stdout):
            self.video.main()

    def test_prepares_caller_output_before_submission_and_saves_task(self):
        def submit(*args, **kwargs):
            self.assertTrue(self.output.parent.is_dir())
            return 200, {"task_id": "mock-task-42"}
        self.connection.call.side_effect = submit
        with patch.object(self.video, "wait") as wait:
            self.main("submit", self.output, self.prompt)
        self.assertEqual(Path(str(self.output) + ".task").read_text(), "mock-task-42")
        self.assertIn("已提交：task_id mock-task-42", self.stderr.getvalue())
        wait.assert_called_once_with(self.connection, "mock-task-42", str(self.output))

    def test_directory_failure_happens_before_paid_submission(self):
        self.output.parent.write_text("existing file", encoding="utf-8")
        with self.assertRaises(OSError):
            self.main("submit", self.output, self.prompt)
        self.connection.call.assert_not_called()

    def test_local_task_save_failure_still_reports_id_and_resume(self):
        Path(str(self.output) + ".task").mkdir(parents=True)
        self.connection.call.return_value = 200, {"task_id": "mock-task-42"}
        with patch.object(self.video, "wait") as wait, self.assertRaises(SystemExit) as raised:
            self.main("submit", self.output, self.prompt)
        self.assertIn("mock-task-42", self.stderr.getvalue())
        self.assertIn("已提交", str(raised.exception))
        self.assertIn('wait mock-task-42', str(raised.exception))
        self.assertIn("不要重新 submit", str(raised.exception))
        wait.assert_not_called()
        self.assertEqual(self.connection.call.call_count, 1)

    def test_submit_http_error_does_not_save_success_task(self):
        self.connection.call.return_value = 401, {"error": {"message": "invalid test key"}}
        with self.assertRaisesRegex(SystemExit, "提交失败：HTTP 401.*invalid test key"):
            self.main("submit", self.output, self.prompt)
        self.assertFalse(Path(str(self.output) + ".task").exists())

    def test_ping_http_errors_fail_instead_of_claiming_success(self):
        for status in (401, 403, 404, 500):
            self.connection.call.return_value = status, {"error": {"message": "test response"}}
            with self.subTest(status=status), self.assertRaisesRegex(SystemExit, f"HTTP {status}.*test response"):
                self.main("ping")

    def test_ping_success_preserves_response_without_submitting(self):
        self.connection.call.return_value = 200, {"test": "probe response"}
        self.main("ping")
        self.assertIn("HTTP 200", self.stdout.getvalue())
        self.assertEqual(self.connection.call.call_args.args[0], "GET")

    def test_poll_http_errors_report_reason_and_do_not_sleep(self):
        for status in (401, 403, 404, 429, 500):
            self.connection.call.return_value = status, {"error": {"message": "test failure"}}
            with self.subTest(status=status), patch.object(self.video.time, "sleep") as sleep:
                with self.assertRaisesRegex(SystemExit, f"查询任务 mock-task失败：HTTP {status}.*test failure"):
                    self.video.wait(self.connection, "mock-task", str(self.output))
                sleep.assert_not_called()

    def test_error_body_is_not_mistaken_for_pending_task(self):
        self.connection.call.return_value = 200, {"type": "error", "error": {"message": "test failure"}}
        with patch.object(self.video.time, "sleep") as sleep, self.assertRaisesRegex(SystemExit, "test failure"):
            self.video.wait(self.connection, "mock-task", str(self.output))
        sleep.assert_not_called()

    def test_wait_can_download_to_another_chosen_directory(self):
        self.connection.call.side_effect = [
            (200, {"task": {"status": "processing"}}),
            (200, {"task": {"id": "mock-task", "status": "succeeded", "model": "test-model",
                            "content": {"url": "https://example.invalid/video.mp4"}, "duration": 4}}),
        ]
        with patch.object(self.video.urllib.request, "urlopen", return_value=io.BytesIO(b"mock video")), \
                patch.object(self.video.time, "sleep") as sleep, \
                contextlib.redirect_stdout(self.stdout), contextlib.redirect_stderr(self.stderr):
            self.video.wait(self.connection, "mock-task", str(self.output))
        self.assertEqual(self.output.read_bytes(), b"mock video")
        self.assertEqual(json.loads(Path(str(self.output) + ".json").read_text())["id"], "mock-task")
        sleep.assert_called_once_with(10)
        self.assertEqual(json.loads(self.stdout.getvalue())["output"], str(self.output))

    def test_failed_task_stops_without_downloading(self):
        self.connection.call.return_value = 200, {"task": {"status": "failed", "error": {"message": "generation failed"}}}
        with patch.object(self.video.time, "sleep") as sleep, contextlib.redirect_stderr(self.stderr):
            with self.assertRaisesRegex(SystemExit, "generation failed"):
                self.video.wait(self.connection, "mock-task", str(self.output))
            sleep.assert_not_called()
        self.assertFalse(self.output.exists())


class KeySkillExampleTests(unittest.TestCase):
    def test_documented_image_and_video_calls_use_child_environment_and_explicit_output(self):
        doc = SKILLS_ROOT.parent / "builtin/developer/keys/README.md"
        section = doc.read_text(encoding="utf-8").split("## 把连接交给技能子进程", 1)[1]
        image, video = re.findall(r"```python\n(.*?)\n```", section, re.S)
        common = image.split("subprocess.run(", 1)[0]
        with tempfile.TemporaryDirectory(prefix="layerweave-key-skill-example-") as folder:
            root = Path(folder)
            prompt = root / "prompt.txt"
            prompt.write_text("test prompt", encoding="utf-8")
            for kind, code in (("image", image), ("video", common + video)):
                with self.subTest(kind=kind):
                    output = root / kind / "chosen-output"
                    namespace = {"entry_name": "test-entry", "project_dir": root, "output_dir": output, "prompt_file": prompt}
                    connection = {"env_name": "LAYERWEAVE_TEST_ONLY_KEY", "base_url": "https://example.invalid/v2" if kind == "video" else "https://example.invalid/v1", "model": "test-model"}
                    before = dict(os.environ)
                    with patch("layerweave.tool.builtin.developer.keys.service.manage_keys", return_value={"data": connection}), \
                            patch("layerweave.tool.builtin.developer.keys.service.get_key", return_value="fake-key-for-test"), \
                            patch("subprocess.run") as run:
                        exec(compile(code, str(doc), "exec"), namespace)
                    args = run.call_args.args[0]
                    self.assertTrue(Path(args[4]).is_file())
                    self.assertNotIn("fake-key-for-test", args)
                    self.assertEqual(run.call_args.kwargs["env"][connection["env_name"]], "fake-key-for-test")
                    self.assertEqual(run.call_args.kwargs["cwd"], root)
                    self.assertEqual(dict(os.environ), before)
                    self.assertTrue(output.is_dir())
                    self.assertIn(str(prompt), args)
                    self.assertIn(str(output / ("片段.mp4" if kind == "video" else "画面.png")), args)
                    if kind == "video":
                        self.assertLess(args.index("--key-env"), args.index("submit"))


if __name__ == "__main__":
    unittest.main()

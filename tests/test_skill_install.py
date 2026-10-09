"""技能 ZIP 安装：目录选择、字节保留、无隐式执行及文件系统边界。"""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from support.feedback import InputError
from tool.builtin.developer.skills.cli import install_skill


class SkillInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-install-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.skills = self.base / "tool" / "skills"

    def archive(self, entries, name="download.zip"):
        path = self.base / name
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            for filename, content in entries:
                archive.writestr(filename, content)
        return path

    def install(self, archive, **kwargs):
        return install_skill(archive, skills_root=self.skills, **kwargs)

    def test_wrapped_skill_preserves_files_and_returns_project_relative_route(self):
        script = b"raise RuntimeError('installer must not execute this')\n"
        archive = self.archive([
            ("release/demo/SKILL.md", "说明可以不带 frontmatter，安装器不解释内容"),
            ("release/demo/scripts/run.py", script),
            ("release/demo/assets/raw.bin", bytes(range(256))),
            ("release/README.md", "outside"),
        ])
        with patch("tool.builtin.developer.skills.cli.PROJECT_ROOT", self.base):
            result = self.install(archive, layer="text")
        destination = self.skills / "layers/text/demo"
        self.assertEqual(result, {"ok": True, "name": "demo", "path": str(destination),
                                 "route": "tool/skills/layers/text/demo/SKILL.md", "source_dir": "release/demo", "files": 3})
        self.assertEqual((destination / "scripts/run.py").read_bytes(), script)
        self.assertEqual((destination / "assets/raw.bin").read_bytes(), bytes(range(256)))
        self.assertFalse((destination / "README.md").exists())

    def test_flat_zip_uses_archive_stem_and_nested_reference_is_part_of_skill(self):
        archive = self.archive([("SKILL.md", "flat"), ("references/example/SKILL.md", "example")], "plain.skill")
        result = self.install(archive, scenario=True)
        self.assertEqual(result["name"], "plain")
        self.assertEqual(result["source_dir"], ".")
        self.assertEqual(result["files"], 2)
        self.assertTrue((self.skills / "scenarios/plain/references/example/SKILL.md").is_file())

    def test_bundle_requires_selection_and_explicit_name_does_not_rewrite_content(self):
        archive = self.archive([("bundle/one/SKILL.md", "name: one"), ("bundle/two/SKILL.md", "name: two")])
        with self.assertRaises(InputError) as failed:
            self.install(archive, layer="audio")
        self.assertEqual(failed.exception.details["candidates"], ["bundle/one", "bundle/two"])
        self.assertFalse(self.skills.exists())
        result = self.install(archive, layer="audio", source_dir="bundle/two", name="second")
        self.assertEqual(Path(result["path"]).name, "second")
        self.assertEqual((Path(result["path"]) / "SKILL.md").read_text(), "name: two")
        self.assertFalse((Path(result["path"]) / "one").exists())

    def test_existing_installation_is_not_merged_or_overwritten(self):
        archive = self.archive([("demo/SKILL.md", "new"), ("demo/new.txt", "new")])
        destination = self.skills / "layers/text/demo"
        destination.mkdir(parents=True)
        (destination / "SKILL.md").write_text("old")
        with self.assertRaises(InputError) as failed:
            self.install(archive, layer="text")
        self.assertEqual(failed.exception.details["code"], "destination_exists")
        self.assertEqual((destination / "SKILL.md").read_text(), "old")
        self.assertFalse((destination / "new.txt").exists())

    def test_unsafe_archive_paths_are_rejected_before_writing(self):
        names = ["../escaped.txt", "demo/../../escaped.txt", "/absolute.txt", "demo/file:stream",
                 "demo\\..\\escaped.txt", "demo/NUL", "demo/trailing.", str(self.base / "escaped.txt")]
        for name in names:
            with self.subTest(name=name):
                archive = self.archive([("demo/SKILL.md", "safe"), (name, "bad")])
                with self.assertRaises(InputError):
                    self.install(archive, layer="text")
                self.assertFalse(self.skills.exists())
                self.assertFalse((self.base / "escaped.txt").exists())

    def test_zip_symlink_and_duplicate_targets_are_rejected(self):
        link = zipfile.ZipInfo("demo/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive = self.archive([("demo/SKILL.md", "safe"), (link, "../../outside")])
        with self.assertRaises(InputError) as failed:
            self.install(archive, scenario=True)
        self.assertEqual(failed.exception.details["code"], "unsupported_entry")
        archive = self.archive([("demo/SKILL.md", "safe"), ("demo/a.txt", "a"), ("demo/A.txt", "b")])
        with self.assertRaises(InputError) as failed:
            self.install(archive, scenario=True)
        self.assertEqual(failed.exception.details["code"], "duplicate_path")
        self.assertFalse(self.skills.exists())

    def test_invalid_destination_and_missing_skill_have_no_installation(self):
        archive = self.archive([("demo/SKILL.md", "safe")])
        for args in ({}, {"layer": "text", "scenario": True}, {"layer": "../outside"},
                     {"scenario": True, "name": "../outside"}, {"scenario": True, "source_dir": "missing"}):
            with self.subTest(args=args), self.assertRaises(InputError):
                self.install(archive, **args)
        archive = self.archive([("README.md", "no skill")])
        with self.assertRaises(InputError) as failed:
            self.install(archive, scenario=True)
        self.assertEqual(failed.exception.details["code"], "skill_not_found")
        self.assertFalse(self.skills.exists())

    def test_corrupt_payload_removes_partial_skill_and_preserves_neighbor(self):
        payload = b"unique-payload-for-crc-test"
        archive = self.archive([("demo/SKILL.md", "safe"), ("demo/data.bin", payload)])
        damaged = bytearray(archive.read_bytes())
        offset = damaged.index(payload)
        damaged[offset] ^= 1
        archive.write_bytes(damaged)
        neighbor = self.skills / "layers/text/keep"
        neighbor.mkdir(parents=True)
        (neighbor / "SKILL.md").write_text("keep")
        with self.assertRaises(zipfile.BadZipFile):
            self.install(archive, layer="text")
        self.assertFalse((neighbor.parent / "demo").exists())
        self.assertEqual((neighbor / "SKILL.md").read_text(), "keep")

    def test_file_directory_conflict_cleans_partial_installation(self):
        archive = self.archive([("demo/SKILL.md", "safe"), ("demo/assets", "file"), ("demo/assets/x.txt", "child")])
        with self.assertRaises(OSError):
            self.install(archive, scenario=True)
        self.assertFalse((self.skills / "scenarios/demo").exists())

    def test_existing_destination_parent_cannot_redirect_outside_skills_root(self):
        outside = self.base / "outside"
        outside.mkdir()
        category = self.skills / "layers/text"
        category.parent.mkdir(parents=True)
        try:
            category.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("当前平台不允许测试目录符号链接")
        archive = self.archive([("demo/SKILL.md", "safe")])
        with self.assertRaises(InputError):
            self.install(archive, layer="text")
        self.assertEqual(list(outside.iterdir()), [])

    def test_relative_and_backslash_zip_paths_are_normalized(self):
        executable = zipfile.ZipInfo("./demo/scripts/run.sh")
        executable.create_system = 3
        executable.external_attr = (stat.S_IFREG | 0o755) << 16
        archive = self.archive([(".\\demo\\SKILL.md", "safe"), ("demo/assets/", ""), (executable, "echo hello\n")])
        result = self.install(archive, layer="custom-layer")
        destination = Path(result["path"])
        self.assertTrue((destination / "assets").is_dir())
        self.assertEqual((destination / "scripts/run.sh").read_text(), "echo hello\n")
        if os.name != "nt":
            self.assertTrue((destination / "scripts/run.sh").stat().st_mode & stat.S_IXUSR)

    def test_cli_json_success_and_conflict_do_not_touch_database_or_bindings(self):
        archive = self.archive([("demo/SKILL.md", "plain text")])
        command = [sys.executable, "-X", "utf8", "-B", "-m", "tool.builtin.developer.skills.cli", str(archive),
                   "--scenario", "--skills-root", str(self.skills), "--json"]
        installed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        data = json.loads(installed.stdout)
        self.assertEqual(data["route"], (self.skills / "scenarios/demo/SKILL.md").as_posix())
        rejected = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(rejected.returncode, 1)
        self.assertEqual(json.loads(rejected.stdout)["error"]["code"], "destination_exists")
        self.assertEqual(sorted(p.name for p in Path(data["path"]).iterdir()), ["SKILL.md"])


if __name__ == "__main__":
    unittest.main()

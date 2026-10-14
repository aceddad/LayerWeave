"""内部工具的命令唯一性、实际 CLI 和文档导引。"""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from layerweave.support.commands import command_help


ROOT = Path(__file__).resolve().parents[1]


class ToolLayoutTests(unittest.TestCase):
    def test_commands_have_one_canonical_declaration_each_and_same_help_shape(self):
        overview = command_help()
        self.assertEqual(overview["status"], "completed")
        names = {item["name"] for item in overview["items"]}
        self.assertEqual(names, {"align_objects", "append_object", "arrange_objects", "collect_text", "command_help",
                                "config_help", "copy_object", "copy_subtree", "delete_subtree", "dispatch", "find_gaps",
                                "find_objects", "initialize_database", "install_skill", "manage_keys", "manage_versions", "insert_gap", "project_details", "project_overview",
                                "query_relations", "read_history", "recheck", "set_duration", "shift_objects", "split_object",
                                "transfer_objects", "transfer_subtree", "undo_operation", "upsert_objects", "walk_relations",
                                "export_project", "import_project", "template_help",
                                # visualization 分支：视图工具包
                                "view_at", "view_bench", "view_fold", "view_frame", "view_layout", "view_note", "view_plugin", "view_screenshot", "view_server", "view_state", "view_walk"})
        self.assertEqual(len(overview["items"]), 44)
        self.assertTrue(all(set(item) == {"name", "summary", "read_only", "cli"} for item in overview["items"]))
        groups = {}
        for command in command_help(sorted(names))["items"]:
            group = command["source"].split("/")[0]
            groups[group] = groups.get(group, 0) + 1
        self.assertEqual(groups, {"usage": 27, "shared": 2, "developer": 4, "view": 11})
        view = ROOT / "src/layerweave/tool/builtin/view"
        self.assertTrue(view.is_dir())
        self.assertTrue((view / "web" / "index.html").is_file())   # visualization 分支：视图网页随包分发

    def test_database_and_crud_execute_through_canonical_tools(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "tools.sqlite3"
            base = [sys.executable, "-X", "utf8", "-B", "-m"]
            initialized = subprocess.run([*base, "layerweave.tool.builtin.developer.database.cli", str(database)],
                                         capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            created = subprocess.run([*base, "layerweave.tool.builtin.usage.records.cli", str(database)],
                                     input=json.dumps({"action": "create", "kind": "project", "data": {"name": "示例项目"}}),
                                     capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertTrue(json.loads(created.stdout)["ok"])
            read = subprocess.run([*base, "layerweave.tool.builtin.usage.records.cli", str(database)],
                                  input=json.dumps({"action": "read", "kind": "project"}),
                                  capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(read.returncode, 0, read.stderr)
            self.assertEqual(json.loads(read.stdout)["data"][0]["name"], "示例项目")

    def test_current_documentation_links_resolve_after_moves(self):
        documents = [ROOT / "README.md", ROOT / "AGENTS.md"]
        for directory in ("src", "docs", "examples"):
            documents.extend((ROOT / directory).rglob("*.md"))
        broken = []
        for document in documents:
            for value in re.findall(r"\]\(([^)\n]+)\)", document.read_text(encoding="utf-8")):
                if ":" in value or value.startswith("#"):
                    continue
                destination = value.split("#", 1)[0]
                if not (document.parent / destination).resolve().exists():
                    broken.append((document.relative_to(ROOT).as_posix(), value))
        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()

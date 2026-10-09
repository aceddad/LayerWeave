"""工具迁移后的命令唯一性、旧入口兼容、实际 CLI 和文档导引。"""

import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from runtime.api import command_help


ROOT = Path(__file__).resolve().parents[1]


def old_module(current):
    if current.startswith("tools.usage.common."):
        return current.replace("tools.usage.common.", "tools.common.", 1)
    if current.startswith("tools.usage.text."):
        return current.replace("tools.usage.text.", "tools.text.", 1)
    return {"tools.shared.command_help": "tools.common.command_help",
            "tools.shared.config_help": "tools.common.config_help",
            "tools.usage.crud": "runtime.console", "tools.developer.database": "runtime.storage.database"}[current]


class ToolLayoutTests(unittest.TestCase):
    def test_same_25_commands_one_canonical_declaration_each_and_same_help_shape(self):
        overview = command_help()
        self.assertEqual(overview["status"], "completed")
        names = {item["name"] for item in overview["items"]}
        self.assertEqual(names, {"align_objects", "append_object", "arrange_objects", "collect_text", "command_help",
                                "config_help", "copy_object", "copy_subtree", "delete_subtree", "dispatch", "find_gaps",
                                "find_objects", "initialize_database", "insert_gap", "project_details", "project_overview",
                                "query_relations", "read_history", "recheck", "set_duration", "shift_objects", "split_object",
                                "transfer_objects", "transfer_subtree", "undo_operation"})
        self.assertEqual(len(overview["items"]), 25)
        self.assertTrue(all(set(item) == {"name", "summary", "read_only", "cli"} for item in overview["items"]))
        groups = {}
        for command in command_help(sorted(names))["items"]:
            group = command["source"].split("/")[1]
            groups[group] = groups.get(group, 0) + 1
        self.assertEqual(groups, {"usage": 22, "shared": 2, "developer": 1})
        self.assertEqual(list((ROOT / "src/tools/view").glob("*.py")), [])

    def test_old_imports_and_fully_qualified_help_names_refer_to_same_functions(self):
        modules = set()
        for item in command_help()["items"]:
            command = command_help(item["name"])["items"][0]
            current = command["cli"].split()[-1]
            if current != "tools.developer.database":
                modules.add((old_module(current), current))
            for alias in command.get("aliases", []):
                if ":" not in alias:
                    continue
                queried = command_help(alias)
                self.assertEqual(queried["issues"], [])
                self.assertEqual(queried["items"][0]["name"], item["name"])
                old, old_name = alias.split(":")
                new, new_name = command["entrypoint"].split(":")
                self.assertIs(getattr(importlib.import_module(old), old_name), getattr(importlib.import_module(new), new_name))
        modules.add(("tools.catalog", "tools.shared.catalog"))
        modules.add(("tools._cli", "tools.shared._cli"))
        modules.add(("tools.common._hierarchy", "tools.usage.common._hierarchy"))
        for old, new in modules:
            old_module_object, new_module_object = importlib.import_module(old), importlib.import_module(new)
            for name, value in vars(new_module_object).items():
                if callable(value) and getattr(value, "__module__", None) == new:
                    self.assertIs(getattr(old_module_object, name), value, (old, name))

    def test_legacy_cli_help_forwards_without_duplicate_registration(self):
        seen = set()
        for item in command_help()["items"]:
            command = command_help(item["name"])["items"][0]
            current = command["cli"].split()[-1]
            if current in seen:
                continue
            seen.add(current)
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", old_module(current), "--help"],
                                    capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, (current, result.stderr))
            self.assertIn(command["examples"][0]["cli"], result.stdout)

    def test_legacy_database_and_crud_still_execute_with_new_core(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "legacy.sqlite3"
            base = [sys.executable, "-X", "utf8", "-B", "-m"]
            initialized = subprocess.run([*base, "runtime.storage.database", str(database)],
                                         capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            created = subprocess.run([*base, "runtime.console", str(database)],
                                     input=json.dumps({"action": "create", "kind": "project", "data": {"name": "兼容"}}),
                                     capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertTrue(json.loads(created.stdout)["ok"])
            read = subprocess.run([*base, "tools.usage.crud", str(database)],
                                  input=json.dumps({"action": "read", "kind": "project"}),
                                  capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(read.returncode, 0, read.stderr)
            self.assertEqual(json.loads(read.stdout)["data"][0]["name"], "兼容")

    def test_current_documentation_links_resolve_after_moves(self):
        documents = [ROOT / "README.md", ROOT / "AGENTS.md"]
        for directory in ("src", "docs", "configs"):
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

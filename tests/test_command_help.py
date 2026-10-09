"""命令目录静态发现、覆盖现有入口、可用示例和 CLI 就地帮助。"""

import ast
import importlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from runtime.api import command_help, dispatch, insert_gap, open_database, split_object
from runtime.storage.database import SCHEMA_PATH
from tools.shared.catalog import DEFAULT_SOURCE_ROOT, help_examples
from tools.shared.command_help import format_commands


class CommandHelpTests(unittest.TestCase):
    def test_overview_covers_all_tool_modules_and_is_small(self):
        result = command_help()
        self.assertEqual(result["status"], "completed")
        names = {item["name"] for item in result["items"]}
        self.assertTrue({"split_object","insert_gap","undo_operation","dispatch","initialize_database","command_help","shift_objects"} <= names)
        self.assertTrue(all("parameters" not in item for item in result["items"]))
        details = command_help(list(names))
        covered = {item["source"] for item in details["items"]}
        for path in (DEFAULT_SOURCE_ROOT/"tools").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if any(isinstance(n,ast.FunctionDef) and n.name=="main" for n in tree.body):
                self.assertIn(path.relative_to(DEFAULT_SOURCE_ROOT).as_posix(), covered)

    def test_details_resolve_aliases_and_include_inputs_outputs_examples(self):
        result = command_help(["split","split_object","runtime.api:split_object","insert_gap"])
        self.assertEqual(len(result["items"]),2)
        split,gap = result["items"]
        self.assertIn("object_id", split["parameters"])
        self.assertIn("database", split["parameters"])
        self.assertIn("whole_project", gap["parameters"])
        self.assertIn("crossing_actions", gap["parameters"])
        self.assertIn("examples", split)
        self.assertIn("returns", split)
        self.assertIn("first_information", format_commands(result))
        self.assertEqual(command_help([])["items"],[])

    def test_discovery_never_imports_new_modules_or_opens_a_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"custom.py"
            cmd = {"name":"fresh_tool","summary":"新增工具","entrypoint":"custom:fresh_tool","cli":"python -m custom","read_only":True}
            path.write_text("raise AssertionError('must not import')\nCOMMANDS = "+repr([cmd]),encoding="utf-8-sig")
            with patch("sqlite3.connect", side_effect=AssertionError("must not connect")):
                result = command_help("fresh_tool",source_root=folder)
            self.assertEqual(result["status"],"completed")
            self.assertEqual(result["items"][0]["summary"],"新增工具")
            cmd["summary"]="修改后直接可见"
            path.write_text("COMMANDS = "+repr([cmd]),encoding="utf-8")
            self.assertEqual(command_help("fresh_tool",source_root=folder)["items"][0]["summary"],"修改后直接可见")

    def test_invalid_metadata_and_unknown_names_do_not_hide_valid_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            good = {"name":"ok","summary":"有效","entrypoint":"example:ok","cli":"python -m example","read_only":True}
            (Path(folder)/"mixed.py").write_text("COMMANDS = "+repr([{"name":[]},good]),encoding="utf-8")
            result = command_help(["absent","ok"],source_root=folder)
            self.assertEqual(result["status"],"partial")
            self.assertEqual([item["name"] for item in result["items"]],["ok"])
            self.assertEqual({item["code"] for item in result["issues"]},{"command_metadata","command_name"})

    def test_duplicate_names_are_not_guessed_but_entrypoint_can_disambiguate(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("a","b"):
                command={"name":"same","summary":"说明","entrypoint":name+":run","cli":"python -m "+name,"read_only":True}
                (Path(folder)/(name+".py")).write_text("COMMANDS = "+repr([command]),encoding="utf-8")
            result=command_help(["same","a:run","b:run"],source_root=folder)
            self.assertEqual(result["status"],"partial")
            self.assertEqual(result["items"][0]["entrypoint"],"a:run")
            self.assertEqual(len(result["items"]),2)
            self.assertEqual(len(result["issues"][0]["candidates"]),2)

    def test_metadata_parameters_refer_to_real_callable_parameters(self):
        for summary in command_help()["items"]:
            command=command_help(summary["name"])["items"][0]
            module,name=command["entrypoint"].split(":")
            function=getattr(importlib.import_module(module),name)
            signature=inspect.signature(function)
            if any(p.kind==p.VAR_KEYWORD for p in signature.parameters.values()):
                continue  # runtime.api 的延迟包装；行为由对应工具测试覆盖。
            for parameter in command["parameters"]:
                if parameter=="database":
                    self.assertTrue("connection" in signature.parameters or command["name"]=="initialize_database")
                else:
                    self.assertIn(parameter,signature.parameters,command["name"])

    def test_all_root_cli_help_contains_its_shared_example(self):
        seen=set()
        for summary in command_help()["items"]:
            command=command_help(summary["name"])["items"][0]
            module=command["cli"].split()[-1]
            if module in seen:
                continue
            seen.add(module)
            run=subprocess.run([sys.executable,"-X","utf8","-B","-m",module,"--help"],capture_output=True,text=True,encoding="utf-8")
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn(command["examples"][0]["cli"],run.stdout)
            for filename,payload in command["examples"][0].get("files",{}).items():
                self.assertIn(json.dumps(payload,ensure_ascii=False,allow_nan=False),run.stdout)

    def test_help_json_files_can_be_used_for_actual_split_and_keep(self):
        c=open_database(":memory:")
        self.addCleanup(c.close)
        c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        p=dispatch(c,{"action":"create","kind":"project","data":{}},checker=None)["id"]
        layer=dispatch(c,{"action":"create","kind":"layer","project_id":p,"data":{"config_ref":"layers/text.toml"}},checker=None)["id"]
        def obj():
            return dispatch(c,{"action":"create","kind":"object","project_id":p,"data":{"config_ref":"objects/text.toml","layer":layer,"begin":10,"end":20,"information":{"text":"原文"}}},checker=None)["id"]
        command=command_help("split")["items"][0]
        payload=next(iter(command["examples"][0]["files"].values()))
        result=split_object(c,p,obj(),**payload)
        self.assertTrue(result["ok"],result)
        gap=command_help("insert_gap")["items"][0]
        actions=next(iter(gap["examples"][0]["files"].values()))
        # 示例编号由真实上下文替换，JSON 结构与字段保持一致。
        ids=[obj() for _ in actions]
        actions=[{**item,"object_id":id} for item,id in zip(actions,ids)]
        # 另建直属层，避免其他示例对象也跨界。
        other=dispatch(c,{"action":"create","kind":"layer","project_id":p,"data":{"config_ref":"layers/text.toml"}},checker=None)["id"]
        for id in ids:
            dispatch(c,{"action":"update","kind":"object","project_id":p,"id":id,"data":{"layer":other}},checker=None)
        result=insert_gap(c,p,layer_id=other,at=14,length=2,crossing_actions=actions)
        self.assertTrue(result["ok"],result)
        self.assertEqual(len(result["data"]["kept"]),1)
        self.assertEqual(len(result["data"]["stretched"]),1)
        self.assertEqual(len(result["data"]["moved"]),1)

    def test_command_help_cli_json_and_invalid_root(self):
        base=[sys.executable,"-X","utf8","-B","-m","tools.shared.command_help"]
        run=subprocess.run([*base,"split","gaps","--json"],capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(len(json.loads(run.stdout)["items"]),2)
        with tempfile.TemporaryDirectory() as folder:
            run=subprocess.run([*base,"--source-root",str(Path(folder)/"missing"),"--json"],capture_output=True,text=True,encoding="utf-8")
        self.assertEqual(run.returncode,1)
        self.assertEqual(json.loads(run.stdout)["status"],"failed")


if __name__ == "__main__":
    unittest.main()

"""真实目录隔离、统一写门及跨工作目录调用的架构验收。"""
import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from layerweave.support.api import open_database, run_operation, transaction
from layerweave.support.feedback import InputError
from layerweave.support.storage.database import SCHEMA_PATH


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src/layerweave"
PACKAGES = ("usage/records", "usage/query", "usage/editing", "usage/history", "usage/undo",
            "usage/validation", "usage/text", "usage/exchange", "shared/help", "shared/mcp", "developer/database", "developer/skills", "developer/keys", "developer/versions",
            "view")   # visualization 分支：视图工具包

FIXTURE = '''
from layerweave.support.api import open_database, save_layer, save_object, transaction, read_record
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.models import TextLayer, Title
c = open_database(":memory:")
c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
with transaction(c) as write:
    p = write.create("project", {"name": "isolation"})["id"]
layer = TextLayer(name="text")
saved = save_layer(c, p, layer)
assert saved["ok"] and saved["checks"]["status"] == "not_run", saved
obj = Title(layer=layer.id, begin=0, end=2, information={"text": "hello"})
saved_object = save_object(c, p, obj)
assert saved_object["ok"], saved_object
'''


class IsolationTests(unittest.TestCase):
    def isolated(self, code, *, package=None, core_only=False):
        with tempfile.TemporaryDirectory(prefix="layerweave-isolated-") as folder:
            root = Path(folder)
            package_root = root / "src/layerweave"
            package_root.mkdir(parents=True)
            shutil.copy2(PACKAGE / "__init__.py", package_root / "__init__.py")
            shutil.copy2(PACKAGE / "component.toml", package_root / "component.toml")
            for name in ("core", "models") if core_only else ("core", "models", "support"):
                shutil.copytree(PACKAGE / name, package_root / name,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            if not core_only:
                shutil.copytree(PACKAGE / "configs", package_root / "configs")
            if package is not None:
                dest = package_root / "tool/builtin" / package
                shutil.copytree(PACKAGE / "tool/builtin" / package, dest,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                for parent in dest.parents:
                    if parent == package_root:
                        break
                    (parent / "__init__.py").touch()
            outside = root / "unrelated-cwd"
            outside.mkdir()
            env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(root / "src"), str(root)))}
            # -S 排除可编辑安装及 site-packages，无法回退到完整仓库中的工具。
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-S", "-c", textwrap.dedent(code)],
                                    cwd=outside, env=env, capture_output=True, text=True, encoding="utf-8", timeout=40)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_core_and_models_without_support_configs_or_tools(self):
        self.isolated('''
            import sys
            from layerweave.core import Layer, Object, DefinitionError, merge_definition, identity_key, reference
            from layerweave.models import Text, Title
            layer = Layer(id=1, objects=[Title(layer=1, information={"text": "hello"})])
            assert layer.return_self() is layer
            assert isinstance(layer.objects[0], Text)
            assert isinstance(layer.objects[0], Object)
            assert identity_key("bind", 7, 9) == ("bind", None, 9)
            assert reference("object", 7, 9) == {"kind": "object", "project_id": 7, "id": 9}
            parent = merge_definition(None, {"information": {"source": {"type": "str", "optional": True}}})
            child = merge_definition(parent, {"information": {"source": {"optional": False}}})
            assert child["information"]["source"]["optional"] is False
            try:
                merge_definition(child, {"information": {"source": {"optional": True}}})
            except DefinitionError:
                pass
            else:
                raise AssertionError("must not weaken inherited contract")
            assert not any(n == p or n.startswith(p + ".") for n in sys.modules
                           for p in ("sqlite3", "tomllib", "layerweave.support", "layerweave.tool"))
        ''', core_only=True)

    def test_foundation_roundtrip_and_raw_reads_without_any_tools(self):
        self.isolated(FIXTURE + '''
from layerweave.support.api import load_object, load_layer
from layerweave.support.commands import command_help
import sys
assert command_help() == {"view":"overview", "status":"completed", "items":[], "issues":[]}
assert type(load_object(c, p, obj.id)) is Title
assert type(load_layer(c, p, layer.id).objects[0]) is Title
assert read_record(c, "project", id=p)["max_id"] == obj.id
assert len(read_record(c, "change")) == 3
from layerweave.support.api import save_layer_in_session, save_object_in_session, run_operation
def compose(write):
    extra = save_layer_in_session(write, p, TextLayer(name="composed"))
    return save_object_in_session(write, p, Title(layer=extra["id"], information={"text":"session"}))
composed = run_operation(c, compose)
assert composed["ok"] and composed["checks"]["status"] == "not_run", composed
assert type(load_object(c,p,composed["data"]["id"])) is Title
with transaction(c) as write:
    write.update("object", obj.id, {"config_ref": "objects/missing.toml"}, project_id=p)
assert read_record(c, "object", project_id=p, id=obj.id)["config_ref"] == "objects/missing.toml"
from layerweave.support.api import change_cursor, read_changes
assert read_changes(c)["next_cursor"] == change_cursor(c)
assert read_changes(c,after=change_cursor(c))["changes"] == []
try:
    load_object(c, p, obj.id)
except ValueError:
    pass
else:
    raise AssertionError("class restoration must report missing config")
from layerweave.support.api import register_tables, table_specs
register_tables(c, {"layer_state": {"id_source":"provided", "fields":{"fold":"TEXT"},
    "logical_references":[{"fields":["project_id","id"],"kind":"layer"}],
    "exchange":{"on_copy":"skip"}}})
with transaction(c) as write:
    spare = write.create("layer", {"type":"text","config_ref":"layers/text.toml"}, project_id=p)
    write.create("layer_state", {"id":spare["id"],"fold":"closed"}, project_id=p)
    write.delete("layer", spare["id"], project_id=p)
assert read_record(c,"layer_state",project_id=p,id=spare["id"])["fold"] == "closed"
assert table_specs(c)["layer_state"]["exchange"] == {"on_copy":"skip"}
assert not any(n == "layerweave.tool" or n.startswith("layerweave.tool.") for n in sys.modules)
''')

    def test_each_complete_package_works_alone(self):
        actions = {
            "usage/exchange": '''
from layerweave.tool.builtin.usage.exchange import export_project, import_project, template_help
assert len(template_help()["items"]) == 3
doc = template_help("storyboard")["items"][0]["document"]
made = import_project(c,doc,new_project=True)
assert made["ok"] and made["checks"]["status"] == "not_run", made
snapshot = export_project(c,made["data"]["project_id"],op="add")
again = import_project(c,snapshot)
assert again["ok"] and again["data"]["status"] == "completed", again
assert again["data"]["project_id"] != made["data"]["project_id"]
from layerweave.support.api import register_tables
register_tables(c, {
    "layer_state":{"id_source":"provided","fields":{"fold":"TEXT"},
        "logical_references":[{"fields":["project_id","id"],"kind":"layer"}]},
    "read_state":{"id_source":"provided","fields":{"reads":"TEXT"},
        "logical_references":[{"fields":["project_id","id"],"kind":"object"}],"exchange":{"on_copy":"skip"}},
})
with transaction(c) as write:
    write.create("layer_state",{"id":layer.id,"fold":"closed"},project_id=p)
    write.create("read_state",{"id":obj.id,"reads":"{}"},project_id=p)
q = again["data"]["project_id"]
copied = import_project(c,export_project(c,p,op="add"),project_id=q)
assert copied["ok"] and copied["checks"]["status"] == "not_run", copied
assert copied["data"]["counts"]["skipped"] == 1 and copied["data"]["issues"][0]["code"] == "copy_policy"
mapped = next(m["target"]["id"] for m in copied["data"]["id_map"] if m["source"]["kind"] == "layer")
assert mapped != layer.id and read_record(c,"layer_state",project_id=q)[0]["id"] == mapped
assert read_record(c,"read_state",project_id=q) == []
''',
            "usage/records": '''
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.tool.builtin.usage.records.save import save_object_with_checks
r = dispatch(c, {"action": "update", "kind": "object", "project_id": p, "id": obj.id, "data": {"tips": "ok"}})
assert r["ok"] and r["checks"]["status"] == "not_run", r
assert save_object_with_checks(c, p, Title(layer=layer.id, information={"text": "second"}))["ok"]
from layerweave.support.api import run_operation
from layerweave.tool.builtin.usage.records.dispatch import dispatch_in_session
r = run_operation(c, lambda w: dispatch_in_session(w, {"action":"update", "kind":"object", "project_id":p,
                                                       "id":obj.id, "data":{"tips":"session"}}))
assert r["ok"] and r["data"]["tips"] == "session", r
''',
            "usage/query": '''
from layerweave.tool.builtin.usage.query.project_overview import project_overview
from layerweave.tool.builtin.usage.query.project_details import project_details
from layerweave.tool.builtin.usage.query.free_ranges import find_gaps
assert project_overview(c,p)["counts"]["objects"] == 1
assert project_details(c,p)["layers"][0]["objects"][0]["id"] == obj.id
assert find_gaps(c,p,layer.id,begin=0,end=4) is not None
from layerweave.tool.builtin.usage.query.walk import walk_relations
with transaction(c) as write:
    write.create("bind",{"source_kind":"layer","source_project_id":p,"source_id":layer.id,
                         "target_kind":"object","target_project_id":p,"target_id":obj.id})
assert len(walk_relations(c,p,"layer",layer.id)["nodes"]) == 2
''',
            "usage/editing": '''
from layerweave.tool.builtin.usage.editing.timeline import split_object
from layerweave.tool.builtin.usage.editing.objects import append_object
from layerweave.tool.builtin.usage.editing.tree_service import copy_subtree
r = split_object(c,p,obj.id,first_information={"text":"one"},cuts=[{"at":1,"information":{"text":"two"}}])
assert r["ok"] and r["checks"]["status"] == "not_run", r
assert append_object(c,p,layer.id,{"config_ref":"objects/text.toml","information":{"text":"three"}},duration=1)["ok"]
assert copy_subtree(c,p,layer.id)["ok"]
from layerweave.support.api import run_operation
from layerweave.tool.builtin.usage.editing.objects import append_object_in_session
from layerweave.tool.builtin.usage.editing.timeline import shift_objects_in_session
def compose(write):
    row = append_object_in_session(write,p,layer.id,{"config_ref":"objects/text.toml","information":{"text":"four"}},duration=1)
    return shift_objects_in_session(write,p,[row["id"]],offset=1)
r = run_operation(c, compose)
assert r["ok"] and len(r["data"]) == 1, r
from layerweave.tool.builtin.usage.editing.upsert import upsert_objects
r = upsert_objects(c,p,layer.id,[{"name":"sync","config_ref":"objects/text.toml","information":{"text":"sync"}}])
assert r["ok"] and r["checks"]["status"] == "not_run", r
same = upsert_objects(c,p,layer.id,[{"name":"sync","tips":"updated"}])
assert same["ok"] and same["data"]["items"][0]["record"]["id"] == r["data"]["items"][0]["record"]["id"], same
''',
            "usage/history": '''
from layerweave.tool.builtin.usage.history.service import read_history
r = read_history(c,p)
assert r["operation_count"] == 3, r
assert read_history(c,operation_id=saved_object["operation_id"])["items"][0]["changes"][0]["after"]["id"] == obj.id
''',
            "usage/undo": '''
from layerweave.tool.builtin.usage.undo.service import undo_operation
r = undo_operation(c,saved_object["operation_id"])
assert r["ok"] and r["checks"]["status"] == "not_run", r
assert read_record(c,"object",project_id=p,id=obj.id) is None
assert undo_operation(c,r["operation_id"])["ok"]
assert read_record(c,"object",project_id=p,id=obj.id)["id"] == obj.id
from layerweave.support.api import run_operation
from layerweave.tool.builtin.usage.undo.service import undo_operation_in_session
r = run_operation(c, lambda w: undo_operation_in_session(w,saved_object["operation_id"]))
assert r["ok"] and read_record(c,"object",project_id=p,id=obj.id) is None, r
''',
            "usage/validation": '''
from layerweave.tool.builtin.usage.validation.recheck import recheck
r = recheck(c,p)
assert r["status"] == "completed", r
from layerweave.support.providers import optional_checker
from layerweave.support.api import run_operation
r = run_operation(c,lambda write: write.update("object",obj.id,{"information":{"text":1}},project_id=p),checker=optional_checker())
assert r["ok"] and r["checks"]["issues"], r
''',
            "usage/text": '''
from layerweave.tool.builtin.usage.text.collect import collect_text
assert collect_text(c,p,layer.id)["text"] == "hello"
''',
            "shared/help": '''
from layerweave.tool.builtin.shared.help.catalog import read_support
from layerweave.tool.builtin.shared.help.config_help import format_help
r = read_support("combined", "text")
assert r["status"] == "completed" and "objects/title.toml" in format_help(r), r
''',
            "shared/mcp": '''
from layerweave.tool.builtin.shared.mcp import create_runtime
import sys
runtime = create_runtime({"installed":False,"skills_roots":[]})
assert runtime.help()["groups"] == []
assert runtime.catalog.documentation[0]["id"] == "layerweave.mcp_server"
assert not any(n == "mcp" or n.startswith("mcp.") for n in sys.modules)
''',
            "developer/database": '''
from layerweave.tool.builtin.developer.database.cli import main
import sys
from pathlib import Path
sys.argv = ["database", "new.sqlite3"]
main()
assert Path("new.sqlite3").is_file()
''',
            "developer/skills": '''
from pathlib import Path
from zipfile import ZipFile
from layerweave.tool.builtin.developer.skills.cli import install_skill
with ZipFile("demo.zip","w") as archive:
    archive.writestr("demo/SKILL.md", "example")
r = install_skill("demo.zip",layer="text")
assert r["ok"], r
assert Path(r["path"]).is_dir()
''',
            "view": '''
from layerweave.tool.builtin.view.data import project_view, order_layers
r = project_view(c, ":memory:", p)
assert r["layers"][0]["objects"][0]["id"] == obj.id and r["layers"][0]["depth"] == 0, r
assert r["layers"][0]["objects"][0]["text"] == "hello"
assert r["layers"][0]["root"] == r["roots"][0]["id"] == r["layers"][0]["id"], r["roots"]
from layerweave.tool.builtin.view.layout import reconcile
assert reconcile([{"id": 1, "key": "秒"}, {"id": 2, "key": "秒"}, {"id": 3, "key": None}], None)[0]["rows"] == [[1], [2]]
''',
            "developer/versions": '''
from layerweave.tool.builtin.developer.versions import manage_versions
r = manage_versions(c)
assert r["ok"] and r["data"]["status"] == "completed", r
assert {row["name"] for row in r["data"]["items"]} == {"layerweave.foundation", "layerweave.versions"}, r
assert len(manage_versions(c,"read")["data"]["items"]) == 2
''',
            "developer/keys": '''
from layerweave.tool.builtin.developer.keys.service import manage_keys, get_key
store = "keys.local.json"
assert manage_keys("init",store=store)["ok"]
r = manage_keys("update","example-key",data={"key":"test-only-key", "used":["any-application"]},store=store)
assert "key" not in r["data"] and r["data"]["key_configured"]
assert get_key("example-key",store=store) == "test-only-key"
assert manage_keys("export",store=store)["data"]["example-key"]["key"] == ""
assert manage_keys("delete","example-key",store=store)["ok"]
''',
        }
        for package in PACKAGES:
            with self.subTest(package=package):
                # CLI wrappers and shared examples must also load with every other package absent.
                code = FIXTURE + actions[package] + '''
from layerweave.support.commands import command_help
from importlib import import_module
import shlex
import sys
overview = command_help()
assert overview["status"] == "completed", overview
assert overview["items"], overview
for item in overview["items"]:
    parts = shlex.split(item["cli"])
    module = parts[parts.index("-m")+1]
    command = import_module(module)
    if not hasattr(command, "main"):
        command = import_module(module + ".__main__")
    try:
        sys.argv = [module, "--help"]
        command.main()
    except SystemExit as done:
        assert done.code == 0
'''
                self.isolated(code, package=package)

    def test_tool_table_storage_and_each_history_tool_work_without_other_packages(self):
        setup = FIXTURE + '''
from layerweave.support.api import register_tables, run_operation, table_specs
register_tables(c, {"note": {"fields": {"text": "TEXT", "object_id": "INTEGER"},
                           "references": [{"fields": ["project_id", "object_id"], "kind": "object"}]}})
made = run_operation(c, lambda w: w.create("note", {"text": "review", "object_id": obj.id}, project_id=p))
assert made["ok"], made
assert read_record(c, "note", project_id=p, id=made["data"]["id"])["text"] == "review"
'''
        self.isolated(setup + '''
import sys
assert not any(n == "layerweave.tool" or n.startswith("layerweave.tool.") for n in sys.modules)
with transaction(c) as w:
    w.delete("note", made["data"]["id"], project_id=p)
with transaction(c) as w:
    w.restore("note", made["data"]["id"], made["data"], project_id=p)
''')
        self.isolated(setup + '''
from layerweave.tool.builtin.usage.history.service import read_history
r = read_history(c, p, kind="note", id=made["data"]["id"])
assert r["change_count"] == 1, r
''', package="usage/history")
        self.isolated(setup + '''
from layerweave.tool.builtin.usage.undo.service import undo_operation
undone = undo_operation(c, made["operation_id"])
assert undone["ok"] and undone["checks"]["status"] == "not_run", undone
assert undo_operation(c, undone["operation_id"])["ok"]
''', package="usage/undo")

    def test_installed_imports_and_cli_from_outside_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", "layerweave.tool.builtin.shared.help.command_help", "--json"],
                                    cwd=folder, capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("split_object", result.stdout)

    def test_provided_ids_and_numbering_work_without_any_tool_package(self):
        self.isolated(FIXTURE + '''
from layerweave.support.api import register_tables, allocate, numbering_entries, run_operation
register_tables(c, {"view_state": {"id_source":"provided", "fields":{"collapsed":{"type":"INTEGER", "default":0}},
                                  "references":[{"fields":["project_id","id"],"kind":"layer"}]}})
made = run_operation(c, lambda w: w.create("view_state", {"id":layer.id,"collapsed":1}, project_id=p))
assert made["ok"] and made["data"]["id"] == layer.id, made
assert "view_state" not in numbering_entries(c)["project_entities"]["members"]
with transaction(c) as w:
    identity = allocate("project_entities",data={"project_id":p})
assert identity["id"] > obj.id and identity["project_id"] == p
with transaction(c) as w:
    w.delete("view_state",layer.id,project_id=p)
with transaction(c) as w:
    w.restore("view_state",layer.id,made["data"],project_id=p)
assert read_record(c,"view_state",project_id=p,id=layer.id)["collapsed"] == 1
import sys
assert not any(n == "layerweave.tool" or n.startswith("layerweave.tool.") for n in sys.modules)
''')

    def test_foundation_has_no_import_dependency_on_builtin_tools(self):
        for path in (PACKAGE / "support").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                names = [node.module or ""] if isinstance(node, ast.ImportFrom) else [n.name for n in node.names] if isinstance(node, ast.Import) else []
                self.assertFalse(any(n == "layerweave.tool" or n.startswith("layerweave.tool.") for n in names), str(path))


class WriteGateTests(unittest.TestCase):
    def setUp(self):
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        with transaction(self.c) as write:
            self.p = write.create("project", {})["id"]
            self.layer = write.create("layer", {"type":"text", "config_ref":"layers/text.toml", "axis":{"precision":0.001}}, project_id=self.p)["id"]

    def test_callback_result_cannot_forge_or_hide_real_changes(self):
        def work(write):
            row = write.create("object", {"layer": self.layer, "config_ref":"objects/text.toml", "end":0.1+0.2}, project_id=self.p)
            changes = write.changes
            changes.clear()
            return {"claimed_changes": [], "id": row["id"]}
        result = run_operation(self.c, work)
        self.assertEqual(result["operation"]["status"], "committed")
        self.assertEqual(len(result["operation"]["changes"]), 1)
        self.assertEqual(result["checks"]["status"], "not_run")
        self.assertEqual(self.c.execute('SELECT "end" FROM objects').fetchone()[0], 0.3)

    def test_invalid_custom_checker_result_is_not_silently_treated_as_absent(self):
        result = run_operation(self.c, lambda write: write.update("project", self.p, {"name": "changed"}),
                               checker=lambda changes, read: None)
        self.assertTrue(result["ok"])
        self.assertEqual(result["checks"]["status"], "failed")

    def test_cycles_reject_and_rollback_even_without_checker(self):
        before = self.c.total_changes
        def work(write):
            child = write.create("layer", {"type":"text", "config_ref":"layers/text.toml", "father":self.layer}, project_id=self.p)
            write.update("layer", self.layer, {"father":child["id"]}, project_id=self.p)
            return child
        result = run_operation(self.c, work)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "father_cycle")
        self.assertEqual(self.c.execute("SELECT max_id FROM projects").fetchone()[0], self.layer)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM changes").fetchone()[0], 2)
        self.assertGreater(self.c.total_changes, before)  # 确实经过写入，并共同回滚。

    def test_only_final_parent_state_is_rejected(self):
        def work(write):
            child = write.create("layer", {"type":"text", "config_ref":"layers/text.toml", "father":self.layer}, project_id=self.p)
            write.update("layer", self.layer, {"father":child["id"]}, project_id=self.p)
            write.update("layer", child["id"], {"father":None}, project_id=self.p)
            return child
        self.assertTrue(run_operation(self.c, work)["ok"])

    def test_raw_mutation_requires_gate_and_same_operation(self):
        from layerweave.support import records
        with self.assertRaises(RuntimeError):
            records.create(self.c,"project",{},operation_id="invented")
        with transaction(self.c) as write:
            with self.assertRaises(ValueError):
                records.create(self.c,"project",{},operation_id="other")
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM projects").fetchone()[0],1)

    def test_restore_preserves_raw_values_and_never_reuses_ids(self):
        with transaction(self.c) as write:
            record=write.create("object",{"layer":self.layer,"config_ref":"objects/text.toml"},project_id=self.p)
            write.delete("object",record["id"],project_id=self.p)
        record["end"]=0.123456789
        with transaction(self.c) as write:
            restored=write.restore("object",record["id"],record,project_id=self.p)
            self.assertEqual(restored["end"],0.123456789)
            other=write.create("object",{"layer":self.layer,"config_ref":"objects/text.toml"},project_id=self.p)
            self.assertGreater(other["id"],record["id"])

    def test_restore_cannot_overlap_layer_and_object_identity(self):
        record={"project_id":self.p,"id":self.layer,"name":"","layer":self.layer,"config_ref":"objects/text.toml","begin":0,"end":0,"information":{},"tips":""}
        result=run_operation(self.c,lambda write:write.restore("object",self.layer,record,project_id=self.p))
        self.assertFalse(result["ok"])
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM objects").fetchone()[0],0)

    def test_empty_restore_field_selection_is_a_noop(self):
        with transaction(self.c) as write:
            record = write.read("project", id=self.p)
            record["name"] = "not selected"
            current = write.restore("project", self.p, record, fields=[])
            self.assertEqual(current["name"], "")
            self.assertEqual(write.changes, [])


if __name__ == "__main__":
    unittest.main()

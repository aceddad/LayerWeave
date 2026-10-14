"""宿主的常见模块名不能遮蔽 LayerWeave；独立进程避免导入缓存掩盖问题。"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMON_NAMES = ("core", "models", "support", "tool", "examples")

# check_wheel.py 在不加载测试环境中 layerweave 的独立进程中复用这些行为断言。
SMOKE = '''
from importlib import import_module
from pathlib import Path
import json
import subprocess
import sys
hosts = {name: import_module(name) for name in ("core", "models", "support", "tool", "examples")}
from layerweave.models import TextLayer, Title
from layerweave.support.api import open_database, transaction, save_layer, save_object, load_layer, read_object
from layerweave.support.paths import PACKAGE_ROOT, CONFIG_ROOT, SKILLS_ROOT
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.tool.builtin.usage.undo.service import undo_operation
from layerweave.tool.builtin.shared.help.catalog import read_support
from layerweave.support.commands import command_help
from layerweave.tool.builtin.developer.skills.cli import install_skill
from zipfile import ZipFile
assert TextLayer.__module__ == "layerweave.models.layers.text"
assert Title.__module__ == "layerweave.models.objects.title"
assert (CONFIG_ROOT / "layers/text.toml").is_file()
assert 'layerweave.models.objects.title:Title' in (CONFIG_ROOT / "objects/title.toml").read_text(encoding="utf-8")
c = open_database(":memory:")
c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
with transaction(c) as write:
    p = write.create("project", {"name": "namespace"})["id"]
layer = TextLayer(name="字幕")
assert save_layer(c, p, layer)["ok"]
title = Title(layer=layer.id, begin=0, end=1, information={"text": "hello"})
assert save_object(c, p, title)["ok"]
restored = load_layer(c, p, layer.id)
assert type(restored) is TextLayer and type(restored.objects[0]) is Title
assert read_object(c, p, title.id)["config_ref"] == "objects/title.toml"
changed = dispatch(c, {"action":"update", "kind":"object", "project_id":p, "id":title.id, "data":{"tips":"changed"}})
assert changed["ok"] and changed["checks"]["status"] == "completed", changed
assert undo_operation(c, changed["operation_id"])["ok"]
assert read_object(c, p, title.id)["tips"] == ""
from layerweave.support.api import register_tables, run_operation, read_record
register_tables(c, {"audit_entry": {"fields": {"data": {"type": "JSON", "default": {}}, "object_id": "INTEGER"},
                                    "references": [{"fields": ["project_id", "object_id"], "kind": "object"}]}})
entry = run_operation(c, lambda w: w.create("audit_entry", {"data": {"ok": True}, "object_id": title.id}, project_id=p))
assert entry["ok"] and entry["data"]["data"]["ok"] is True, entry
assert undo_operation(c, entry["operation_id"])["ok"]
assert read_record(c, "audit_entry", project_id=p) == []
from layerweave.support.api import allocate, numbering_entries
register_tables(c, {"view_state": {"id_source":"provided", "fields":{"collapsed":{"type":"INTEGER", "default":0}}}})
view = run_operation(c, lambda w: w.create("view_state", {"id":layer.id,"collapsed":1}, project_id=p))
assert view["ok"], view
assert "view_state" not in numbering_entries(c)["project_entities"]["members"]
reversed_view = undo_operation(c, view["operation_id"])
assert reversed_view["ok"] and undo_operation(c,reversed_view["operation_id"])["ok"]
allocated = run_operation(c, lambda w: allocate("project_entities",data={"project_id":p}))
assert allocated["applied"] and allocated["operation"]["status"] == "committed", allocated
assert allocated["operation"]["changes"] == [] and allocated["operation"]["numbering"], allocated
from layerweave.support.api import save_object_in_session
from layerweave.tool.builtin.usage.editing.timeline import shift_objects_in_session
from layerweave.tool.builtin.usage.records.dispatch import dispatch_in_session
def compose(write):
    row = save_object_in_session(write,p,Title(layer=layer.id,begin=4,end=5,information={"text":"session"}))
    shifted = shift_objects_in_session(write,p,[row["id"]],offset=1)
    dispatch_in_session(write,{"action":"update","kind":"object","project_id":p,"id":row["id"],"data":{"tips":"composed"}})
    return shifted
composed = run_operation(c,compose)
assert composed["ok"] and composed["data"][0]["begin"] == 5, composed
assert undo_operation(c,composed["operation_id"])["ok"]
from layerweave.support.api import change_cursor, read_changes
from layerweave.tool.builtin.usage.editing.upsert import upsert_objects
from layerweave.tool.builtin.usage.query.walk import walk_relations
cursor = change_cursor(c)
synced = upsert_objects(c,p,layer.id,[{"name":"sync","config_ref":"objects/text.toml","information":{"text":"s"}}])
assert synced["ok"], synced
synced_id = synced["data"]["items"][0]["record"]["id"]
again = upsert_objects(c,p,layer.id,[{"name":"sync","tips":"update"}])
assert again["ok"] and again["data"]["items"][0]["record"]["id"] == synced_id
assert len(read_changes(c,after=cursor)["changes"]) == 2
assert walk_relations(c,p,"object",synced_id)["nodes"][0]["record"]["tips"] == "update"
assert read_support("combined", "text")["status"] == "completed"
commands = command_help()
assert len(commands["items"]) == 40 and commands["status"] == "completed", commands
from layerweave.tool.builtin.developer.versions import manage_versions
versions = manage_versions(c)
assert versions["ok"] and versions["data"]["status"] == "completed", versions
assert len(versions["data"]["items"]) == 14, versions   # 基础部分 + 12 个内置工具包 + visualization 分支的视图工具包
assert all(row["status"] == "online" for row in versions["data"]["items"]), versions
assert manage_versions(c,"read",name="layerweave.versions")["data"]["items"][0]["version"] == "0.1.0"
from layerweave.tool.builtin.developer.keys.service import manage_keys, get_key
key_store = Path.cwd() / "keys.local.json"
assert manage_keys("init", store=key_store)["ok"]
assert manage_keys("update", "example-key", data={"key":"test-only-key"}, store=key_store)["ok"]
assert get_key("example-key", store=key_store) == "test-only-key"
assert manage_keys("export", store=key_store)["data"]["example-key"]["key"] == ""
skill = SKILLS_ROOT / "layers/text/text-normalize"
assert (skill / "SKILL.md").is_file()
normalized = subprocess.run([sys.executable,"-X","utf8","-B","-S",str(skill / "scripts/normalize_text.py")],
                            input=json.dumps({"text":"hello  \\r\\nworld\\t"}), text=True, capture_output=True, encoding="utf-8")
assert normalized.returncode == 0, normalized.stderr
assert json.loads(normalized.stdout)["text"] == "hello\\nworld"
with ZipFile("download.zip", "w") as archive:
    archive.writestr("downloaded/SKILL.md", "material")
installed = install_skill("download.zip", scenario=True)
assert Path(installed["path"]) == Path.cwd() / "tool/skills/scenarios/downloaded"
assert not Path(installed["path"]).is_relative_to(PACKAGE_ROOT)
assert installed["route"] == "tool/skills/scenarios/downloaded/SKILL.md"
for name, module in hosts.items():
    assert module is sys.modules[name] and module.MARKER == "host:" + name
c.close()
print("namespace, model roundtrip, tool tables/undo, session composition, numbering feedback, component versions, commands, config/schema and skills passed")
'''


def make_host_modules(folder, *, packages=False):
    for name in COMMON_NAMES:
        path = folder / name / "__init__.py" if packages else folder / (name + ".py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'MARKER = "host:{name}"\n', encoding="utf-8")


class NamespaceTests(unittest.TestCase):
    def test_host_files_and_packages_do_not_break_layerweave(self):
        for packages in (False, True):
            with self.subTest(packages=packages), tempfile.TemporaryDirectory(prefix="layerweave-shadow-") as folder:
                make_host_modules(Path(folder), packages=packages)
                env = dict(os.environ)
                env.pop("PYTHONPATH", None)
                result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", SMOKE], cwd=folder,
                                        env=env, capture_output=True, text=True, encoding="utf-8", timeout=45)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_distribution_declares_only_layerweave(self):
        from importlib.metadata import distribution
        names = distribution("layerweave").read_text("top_level.txt").splitlines()
        self.assertEqual(names, ["layerweave"])

    def test_source_install_does_not_expose_old_empty_namespace_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            code = '''
from importlib.util import find_spec
from pathlib import Path
from layerweave.support.paths import PACKAGE_ROOT
for name in ("core", "models", "support", "tool", "examples"):
    spec = find_spec(name)
    if spec is not None:
        paths = [*(spec.submodule_search_locations or []), *([spec.origin] if spec.origin else [])]
        assert not any(Path(p).resolve().is_relative_to(PACKAGE_ROOT.parent) for p in paths), (name,paths)
'''
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", code], cwd=folder,
                                    env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

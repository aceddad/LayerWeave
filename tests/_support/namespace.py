"""宿主遮蔽与普通安装共用的独立进程场景。"""
from tests._support.paths import ROOT

COMMON_NAMES = ("core", "models", "support", "tool", "examples")
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
from layerweave.tool.builtin.usage.exchange import export_project, import_project, template_help
templates = template_help()
assert len(templates["items"]) == 3, templates
made = import_project(c,template_help("storyboard")["items"][0]["document"],new_project=True)
assert made["ok"] and made["data"]["status"] == "completed", made
snapshot = export_project(c,made["data"]["project_id"],op="add")
copied = import_project(c,snapshot)
assert copied["ok"] and copied["data"]["status"] == "completed", copied
assert copied["data"]["counts"]["created"] == sum(snapshot["counts"].values()), copied
assert export_project(c,copied["data"]["project_id"])["counts"] == snapshot["counts"]
assert undo_operation(c,copied["operation_id"])["ok"]
register_tables(c, {
    "layer_cache":{"id_source":"provided","fields":{"fold":"TEXT"},
        "logical_references":[{"fields":["project_id","id"],"kind":"layer"}]},
    "read_cache":{"id_source":"provided","fields":{"reads":"TEXT"},
        "logical_references":[{"fields":["project_id","id"],"kind":"object"}],"exchange":{"on_copy":"skip"}},
})
source = made["data"]["project_id"]
source_layer = read_record(c,"layer",project_id=source)[0]["id"]
source_object = read_record(c,"object",project_id=source)[0]["id"]
with transaction(c) as write:
    write.create("layer_cache",{"id":source_layer,"fold":"closed"},project_id=source)
    write.create("read_cache",{"id":source_object,"reads":"{}"},project_id=source)
copied = import_project(c,export_project(c,source,op="add"),project_id=p)
assert copied["ok"] and copied["data"]["counts"]["skipped"] == 1, copied
assert copied["data"]["issues"][0]["code"] == "copy_policy"
mapped = next(m["target"]["id"] for m in copied["data"]["id_map"]
              if m["source"]["kind"] == "layer" and m["source"]["id"] == source_layer)
assert mapped != source_layer and read_record(c,"layer_cache",project_id=p)[0]["id"] == mapped
assert read_record(c,"read_cache",project_id=p) == []
assert undo_operation(c,copied["operation_id"])["ok"]
assert read_support("combined", "text")["status"] == "completed"
commands = command_help()
assert len(commands["items"]) == 46 and commands["status"] == "completed", commands
from layerweave.tool.builtin.developer.versions import manage_versions
versions = manage_versions(c)
assert versions["ok"] and versions["data"]["status"] == "completed", versions
assert len(versions["data"]["items"]) == 16, versions   # 基础部分与 15 个完整工具包，包含 MCP 和视图。
assert all(row["status"] == "online" for row in versions["data"]["items"]), versions
assert manage_versions(c,"read",name="layerweave.versions")["data"]["items"][0]["version"] == "0.1.1"
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

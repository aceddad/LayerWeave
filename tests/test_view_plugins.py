"""插件协议验收：仅临时目录/合成 ZIP，不碰真实本机清单或联网。"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from layerweave.tool.builtin.view import plugin_manifest as pm, plugin_store as store
from layerweave.tool.builtin.view.plugins import plugin, list_plugins, loadable, plugin_file, require_plugin


def package(folder, name="demo", publisher="alice", version="1.0.0", **changes):
    meta = {"format": 1, "kind": "view-plugin", "publisher": publisher, "name": name, "version": version,
            "label": "测试", "description": "合成测试插件", "entry": "dist/plugin.js", "slots": ["page"],
            "requires": {"view": ">=0.27.0", "host_api": [3]}, **changes}
    path = folder / f"{publisher}.{name}-{version}.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("plugin.json", json.dumps(meta))
        archive.writestr("README.md", "# 测试\n仅供验收")
        archive.writestr("dist/plugin.js", "import {label} from './chunk.js'; export default host => ({label});")
        archive.writestr("dist/chunk.js", "export const label = '" + version + "';")
        archive.writestr("icon.svg", "<svg/>")
    archive = {"url": path.name, "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return path, {**meta, "id": f"{publisher}.{name}", "archive": archive}


class ViewPluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.root = self.folder / "state"
        self.catalog = self.folder / "index.json"

    def index(self, *rows):
        self.catalog.write_text(json.dumps({"format": 1, "plugins": list(rows)}), encoding="utf-8")
        return self.catalog

    def test_zero_plugins_and_no_write_on_read(self):
        result = plugin(root=self.root)
        self.assertEqual(result["plugins"], [])
        self.assertEqual(len(result["recommended"]), 3)
        self.assertFalse(self.root.exists())

    def test_sdk_snapshot_matches_runtime(self):
        snapshot = Path(pm.__file__).with_name("sdk") / f"host-api-{pm.HOST_API}" / "snapshot.json"
        data = json.loads(snapshot.read_text(encoding="utf-8"))
        self.assertEqual((data["host_api"], data["view_version"]), (pm.HOST_API, pm.current_version()))

    def test_parallel_installs_keep_both_registrations(self):
        from concurrent.futures import ThreadPoolExecutor
        a, _ = package(self.folder, publisher="alice")
        b, _ = package(self.folder, publisher="bob")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda path: plugin("install", file=path, root=self.root), (a, b)))
        self.assertTrue(all(r["status"] == "installed" for r in results))
        self.assertEqual({r["id"] for r in list_plugins(self.root)["plugins"]}, {"alice.demo", "bob.demo"})

    def test_conflicting_release_does_not_select_arbitrary_content(self):
        _, row = package(self.folder)
        other = {**row, "archive": {**row["archive"], "sha256": "0" * 64}}
        self.index(row, other)
        with self.assertRaisesRegex(ValueError, "同 ID"):
            plugin("install", "alice.demo", catalog=self.catalog, root=self.root)

    def test_missing_ownership_receipt_does_not_remove_files(self):
        path, _ = package(self.folder)
        plugin("install", file=path, root=self.root)
        row = list_plugins(self.root)["plugins"][0]
        folder = Path(row["root"])
        (folder.parent / (row["version"] + ".receipt.json")).write_text("invalid", encoding="utf-8")
        result = plugin("remove", "alice.demo", files=True, root=self.root)
        self.assertIsNone(result["recycled"])
        self.assertTrue(folder.exists())

    def test_manifest_and_params(self):
        path, row = package(self.folder, params={"ids": {"type": "array", "items": {"type": "integer"}, "description": "编号", "required": True}})
        plugin("install", file=path, root=self.root)
        detail = plugin("info", "alice.demo", root=self.root)
        self.assertIn("仅供验收", detail["usage"])
        specs = detail["manifest"]["params"]
        self.assertEqual(pm.check_params(specs, {"ids": "[1,2]"}), [])
        self.assertEqual(pm.check_params(specs, {"ids": "[1,2]", "extra": "value"})[0]["severity"], "warn")
        for args in ({}, {"ids": '[true]'}, {"ids": "bad"}):
            with self.assertRaisesRegex(ValueError, "ids"):
                pm.check_params(specs, args)
        for invalid in ({"view": {"type": "string", "description": "占用"}}, {"data": {"type": "array", "description": "缺元素类型"}}):
            with self.assertRaises(ValueError):
                pm.manifest({**row, "params": invalid})

    def test_numeric_versions_and_explicit_api_generations(self):
        self.assertGreater(pm.version_tuple("1.10.0"), pm.version_tuple("1.9.0"))
        self.assertIsNone(pm.compatibility({"view": ">=0.27.0, <1.0.0", "host_api": [3]}, view_version="0.28.0"))
        self.assertIn("host.api", pm.compatibility({"view": ">=0.27.0", "host_api": [2]}, view_version="0.28.0"))
        for bad in ("1.0", "01.0.0", "1.0.0-beta"):
            with self.assertRaises(ValueError):
                pm.version_tuple(bad)

    def test_select_highest_compatible_and_pin_source(self):
        _, low = package(self.folder, version="1.9.0")
        _, good = package(self.folder, version="1.10.0")
        _, future = package(self.folder, version="2.0.0", requires={"view": ">=99.0.0", "host_api": [4]})
        self.index(low, good, future)
        result = plugin("install", "alice.demo", catalog=self.catalog, root=self.root)
        self.assertEqual(result["version"], "1.10.0")
        self.assertEqual(plugin("install", "alice.demo", catalog=self.catalog, root=self.root)["status"], "unchanged")
        other = self.folder / "other.json"
        other.write_bytes(self.catalog.read_bytes())
        with self.assertRaisesRegex(ValueError, "其他来源"):
            plugin("install", "alice.demo", catalog=other, root=self.root)
        with self.assertRaisesRegex(ValueError, "没有可安装"):
            plugin("install", "alice.demo", version="2.0.0", catalog=self.catalog, root=self.root)

    def test_update_preserves_off_and_old_versions(self):
        _, first = package(self.folder)
        self.index(first)
        plugin("install", "alice.demo", catalog=self.catalog, root=self.root)
        original = Path(list_plugins(self.root)["plugins"][0]["root"])
        plugin("off", "alice.demo", root=self.root)
        _, second = package(self.folder, version="1.1.0")
        self.index(first, second)
        result = plugin("update", "alice.demo", root=self.root)
        self.assertEqual(result["results"][0]["version"], "1.1.0")
        self.assertFalse(result["plugins"][0]["on"])
        self.assertTrue(original.exists())
        plugin("install", "alice.demo", version="1.0.0", catalog=self.catalog, root=self.root)
        self.assertEqual(list_plugins(self.root)["plugins"][0]["version"], "1.0.0")

    def test_failed_download_keeps_registration(self):
        _, first = package(self.folder)
        self.index(first)
        plugin("install", "alice.demo", catalog=self.catalog, root=self.root)
        saved = store.list_path(self.root).read_bytes()
        _, broken = package(self.folder, version="1.1.0")
        broken["archive"]["sha256"] = "0" * 64
        self.index(first, broken)
        result = plugin("update", root=self.root)
        self.assertEqual(result["status"], "failed")
        self.assertIn("sha256", result["results"][0]["message"])
        self.assertEqual(saved, store.list_path(self.root).read_bytes())

    def test_manifest_identity_and_zip_path_failure_leave_empty(self):
        path, row = package(self.folder)
        wrong = {**row, "name": "other", "id": "alice.other"}
        self.index(wrong)
        with self.assertRaisesRegex(ValueError, "不一致"):
            plugin("install", "alice.other", catalog=self.catalog, root=self.root)
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr("../escape.js", "bad")
        with self.assertRaisesRegex(ValueError, "越出"):
            plugin("install", file=path, root=self.root)
        self.assertEqual(list_plugins(self.root)["plugins"], [])
        self.assertFalse((self.folder / "escape.js").exists())

    def test_changed_same_version_is_rejected(self):
        path, row = package(self.folder)
        plugin("install", file=path, root=self.root)
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr("extra.js", "changed")
        with self.assertRaisesRegex(ValueError, "同版本内容冲突"):
            plugin("install", file=path, root=self.root)

    def test_same_short_name_different_publishers_and_revision_paths(self):
        a, _ = package(self.folder)
        b, _ = package(self.folder, publisher="bob")
        plugin("install", file=a, root=self.root)
        plugin("install", file=b, root=self.root)
        self.assertEqual([r["id"] for r in loadable(self.root)], ["alice.demo", "bob.demo"])
        row = require_plugin("alice.demo", root=self.root)
        self.assertTrue(plugin_file("alice.demo", "dist/chunk.js", self.root, revision=row["revision"]))
        self.assertTrue(plugin_file("alice.demo", "icon.svg", self.root, revision=row["revision"]))
        self.assertIsNone(plugin_file("alice.demo", "README.md", self.root))
        self.assertIsNone(plugin_file("alice.demo", "../index.json", self.root))
        self.assertIsNone(plugin_file("alice.demo", "dist/plugin.js", self.root, revision="wrong"))

    def test_info_does_not_install_or_execute(self):
        _, row = package(self.folder)
        self.index(row)
        result = plugin("info", "alice.demo", catalog=self.catalog, root=self.root)
        self.assertEqual(result["manifest"]["id"], "alice.demo")
        self.assertEqual(list_plugins(self.root)["plugins"], [])
        self.assertFalse(store.list_path(self.root).exists())

    def test_malformed_catalogue_row_and_python_are_isolated(self):
        _, row = package(self.folder)
        self.index(row, {"id": "alice.python", "kind": "python-component", "version": "1.0.0"}, {"id": "bad"})
        result = plugin("market", catalog=self.catalog, root=self.root)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(len(result["issues"]), 1)
        self.assertFalse(result["items"][1]["supported"])
        with self.assertRaisesRegex(ValueError, "尚不支持"):
            plugin("install", "alice.python", catalog=self.catalog, root=self.root)

    def test_migration_is_explicit_and_preserves_data(self):
        self.root.mkdir()
        file = self.folder / "mine.js"
        file.write_text("export default () => ({label:'测试'});", encoding="utf-8")
        legacy = {"plugins": [{"name": "cuts", "on": True}, {"name": "assets", "on": False}, {"name": "mine", "path": str(file), "on": False}]}
        store.list_path(self.root).write_text(json.dumps(legacy), encoding="utf-8")
        before = store.list_path(self.root).read_bytes()
        preview = list_plugins(self.root)
        self.assertTrue(preview["migration_pending"])
        self.assertEqual(store.list_path(self.root).read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "尚未迁移"):
            plugin("on", "local.mine", root=self.root)
        result = plugin("migrate", root=self.root)
        self.assertEqual(Path(result["backup"]).read_bytes(), before)
        self.assertEqual(result["plugins"][0]["id"], "local.mine")
        data = store.read(self.root)
        self.assertEqual(data["preferences"], {"layerweave.cuts": True, "layerweave.assets": False, "layerweave.preview": False})
        self.assertEqual(len(data["plugins"]), 1)

    def test_development_link_and_remove_never_remove_source(self):
        folder = self.folder / "development"
        folder.mkdir()
        file = folder / "plugin.js"
        file.write_text("export default () => ({label:'测试'});", encoding="utf-8")
        self.assertEqual(plugin("add", str(folder), root=self.root)["added"], "local.development")
        result = plugin("remove", "local.development", files=True, root=self.root)
        self.assertIsNone(result["recycled"])
        self.assertTrue(file.exists())

    def test_managed_removal_recycles_and_offline_still_loads(self):
        _, row = package(self.folder)
        self.index(row)
        plugin("install", "alice.demo", catalog=self.catalog, root=self.root)
        self.catalog.unlink()
        self.assertEqual(len(loadable(self.root)), 1)
        plugin("off", "alice.demo", root=self.root)
        with self.assertRaisesRegex(ValueError, "已关闭"):
            require_plugin("alice.demo", root=self.root)
        result = plugin("remove", "alice.demo", files=True, root=self.root)
        self.assertTrue(Path(result["recycled"]).is_dir())
        self.assertEqual(result["plugins"], [])

    def test_load_rechecks_compatibility(self):
        path, _ = package(self.folder)
        plugin("install", file=path, root=self.root)
        with patch.object(pm, "current_version", return_value="0.1.0"):
            self.assertEqual(loadable(self.root), [])
            self.assertIn("需要视图", list_plugins(self.root)["plugins"][0]["problem"])


if __name__ == "__main__":
    unittest.main()

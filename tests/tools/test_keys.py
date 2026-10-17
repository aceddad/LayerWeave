"""KEY 管理的实际读写、脱敏导出、CLI 与文件失败行为；仅用临时目录和假密钥。"""
from contextlib import redirect_stderr, redirect_stdout
import getpass
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from layerweave.support.feedback import InputError
from layerweave.tool.builtin.developer.keys import cli, service


SECRET = "test-only-key-never-use-for-a-real-service"
MODULE = "layerweave.tool.builtin.developer.keys.cli"


class KeyManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layerweave-key-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "private/keys.local.json"

    def call(self, action="read", name=None, **kwargs):
        return service.manage_keys(action, name, store=self.store, **kwargs)

    def register(self, name="service-a", **fields):
        return self.call("create", name, data={"key": SECRET, "env_name": "PRIVATE_ENV_NAME",
                         "base_url": "https://private-endpoint.example/v1", "model": "private-model",
                         "used": ["a-skill", "scripts/client.py", "another-application"], **fields})

    def assert_public(self, result):
        self.assertNotIn(SECRET, json.dumps(result, ensure_ascii=False))
        data = result["data"]
        records = data if isinstance(data, list) else [data]
        for record in records:
            self.assertNotIn("key", record)

    def test_crud_preserves_key_and_allows_any_used_references(self):
        created = self.register()
        self.assert_public(created)
        self.assertTrue(created["data"]["key_configured"])
        self.assertEqual(service.get_key("service-a", store=self.store), SECRET)
        raw = json.loads(self.store.read_text(encoding="utf-8"))
        self.assertEqual(raw["service-a"]["key"], SECRET)
        data = {"used": ["outside:anything", "scripts/other.py"]}
        updated = self.call("update", "service-a", data=data)
        data["used"].append("not saved")
        self.assertEqual(self.call("read", "service-a")["data"]["used"], ["outside:anything", "scripts/other.py"])
        self.assertEqual(service.get_key("service-a", store=self.store), SECRET)
        self.assert_public(updated)
        all_entries = self.call()
        self.assertEqual(len(all_entries["data"]), 1)
        self.assert_public(all_entries)
        self.assert_public(self.call("delete", "service-a"))
        self.assertEqual(json.loads(self.store.read_text()), {})

    def test_read_missing_store_has_no_side_effects_and_missing_name_is_explicit(self):
        self.assertEqual(self.call()["data"], [])
        self.assertEqual(self.call("connections")["data"], [])
        self.assertFalse(self.store.parent.exists())
        with self.assertRaises(InputError) as failed:
            self.call("read", "unknown")
        self.assertEqual(failed.exception.details["code"], "key_not_found")

    def test_init_has_empty_keys_prompts_and_never_overwrites_registered_file(self):
        initialized = self.call("init")
        self.assertFalse(initialized["data"][0]["key_configured"])
        raw = json.loads(self.store.read_text(encoding="utf-8"))
        self.assertEqual(raw["example-key"], {"key": "", **service.PROMPTS, "used": []})
        self.call("update", "example-key", data={"key": SECRET})
        before = self.store.read_bytes()
        with self.assertRaises(InputError) as failed:
            self.call("init")
        self.assertEqual(failed.exception.details["code"], "key_store_exists")
        self.assertEqual(self.store.read_bytes(), before)

    def test_example_export_preserves_names_and_used_only_and_can_initialize_elsewhere(self):
        self.register()
        self.register("service-b", used=[])
        before = self.store.read_bytes()
        exported_path = self.root / "keys.example.json"
        result = self.call("export", output=exported_path)
        exported = json.loads(exported_path.read_text(encoding="utf-8"))
        self.assertEqual(exported, result["data"])
        self.assertEqual(exported["service-a"], {"key": "", **service.PROMPTS,
                         "used": ["a-skill", "scripts/client.py", "another-application"]})
        serialized = json.dumps(exported)
        for private in (SECRET, "PRIVATE_ENV_NAME", "private-endpoint.example", "private-model"):
            self.assertNotIn(private, serialized)
        self.assertEqual(self.store.read_bytes(), before)
        other = self.root / "other/keys.local.json"
        initialized = service.manage_keys("init", template=exported_path, store=other)
        self.assertEqual([r["name"] for r in initialized["data"]], ["service-a", "service-b"])
        self.assertTrue(all(not r["key_configured"] for r in initialized["data"]))
        with self.assertRaises(InputError):
            self.call("export", output=self.store)
        self.assertEqual(self.store.read_bytes(), before)

    def test_import_template_cannot_copy_real_secret_values(self):
        self.register()
        other = self.root / "new/keys.json"
        result = service.manage_keys("init", store=other, template=self.store)
        self.assertNotIn(SECRET, other.read_text(encoding="utf-8"))
        self.assertFalse(result["data"][0]["key_configured"])

    def test_connection_view_is_local_metadata_and_does_not_set_environment(self):
        self.register(env_name="LAYERWEAVE_TEST_ONLY_ENV")
        with patch.dict(os.environ, {"LAYERWEAVE_TEST_ONLY_ENV": "unchanged"}):
            result = self.call("connections", "service-a")
            self.assertEqual(os.environ["LAYERWEAVE_TEST_ONLY_ENV"], "unchanged")
        self.assertEqual(result["data"][0]["model"], "private-model")
        self.assert_public(result)
        self.assertEqual(result["data"], self.call("connections")["data"])

    def test_get_key_reports_unconfigured_and_explicit_clear_keeps_other_fields(self):
        self.register()
        self.call("update", "service-a", data={"key": ""})
        public = self.call("read", "service-a")["data"]
        self.assertFalse(public["key_configured"])
        self.assertEqual(public["model"], "private-model")
        with self.assertRaises(InputError) as failed:
            service.get_key("service-a", store=self.store)
        self.assertEqual(failed.exception.details["code"], "key_not_configured")

    def test_failed_replace_keeps_existing_values_and_cleans_temporary_file(self):
        self.register()
        before = self.store.read_bytes()
        with patch.object(service.os, "replace", side_effect=OSError("injected failure")):
            with self.assertRaises(OSError):
                self.call("update", "service-a", data={"key": "replacement"})
        self.assertEqual(self.store.read_bytes(), before)
        self.assertEqual(list(self.store.parent.iterdir()), [self.store])

    def test_malformed_store_is_not_overwritten_and_errors_do_not_echo_values(self):
        self.store.parent.mkdir(parents=True)
        malformed = '{"service-a":{"key":"' + SECRET + '"}'
        self.store.write_text(malformed, encoding="utf-8")
        with self.assertRaises(InputError) as failed:
            self.call("create", "other", data={})
        self.assertNotIn(SECRET, str(failed.exception))
        self.assertEqual(self.store.read_text(), malformed)
        for data in ({SECRET: "wrong field"}, {"key": {"nested": SECRET}}, {"used": [SECRET, 42]}):
            with self.subTest(data_type=type(data).__name__), self.assertRaises(InputError) as failed:
                service.manage_keys("create", "test", data=data, store=self.root / "invalid.json")
            self.assertNotIn(SECRET, str(failed.exception))
            self.assertNotIn(SECRET, json.dumps(failed.exception.details))
        self.assertFalse((self.root / "invalid.json").exists())

    def test_noop_update_does_not_rewrite_and_names_are_not_upserted(self):
        self.register()
        with patch.object(service, "_write", side_effect=AssertionError("should not write")):
            self.assertTrue(self.call("update", "service-a", data={"key": SECRET})["ok"])
        with self.assertRaises(InputError):
            self.register()
        for action in ("update", "delete"):
            with self.assertRaises(InputError):
                self.call(action, "missing")

    def test_default_user_path_is_resolved_when_called(self):
        with patch("pathlib.Path.home", return_value=self.root):
            result = service.manage_keys("create", "local", data={})
        self.assertEqual(Path(result["store"]), self.root / ".layerweave/keys.json")
        self.assertTrue(Path(result["store"]).is_file())
        if os.name != "nt":
            self.assertEqual(Path(result["store"]).stat().st_mode & 0o777, 0o600)

    def test_cli_stdin_query_and_export_do_not_echo_key(self):
        base = [sys.executable, "-X", "utf8", "-B", "-m", MODULE]
        def run(*args, input=None):
            return subprocess.run([*base, *args, "--store", str(self.store), "--json"], input=input,
                                  text=True, encoding="utf-8", capture_output=True, cwd=self.root, timeout=30)
        created = run("create", "cli-key", "--key-stdin", input=SECRET + "\n")
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertTrue(json.loads(created.stdout)["data"]["key_configured"])
        for args in (("read",), ("connections", "cli-key"), ("export", "--output", str(self.root / "export.json"))):
            result = run(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(SECRET, result.stdout + result.stderr)
        self.assertNotIn(SECRET, created.stdout + created.stderr)
        self.assertEqual(service.get_key("cli-key", store=self.store), SECRET)
        self.assertEqual(json.loads((self.root / "export.json").read_text())["cli-key"]["key"], "")
        self.assertFalse(list(self.root.rglob("*.sqlite3")))

    def test_cli_bad_data_does_not_dump_input(self):
        data = self.root / "bad.json"
        data.write_text('{"key":"' + SECRET + '"', encoding="utf-8")
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", MODULE, "create", "bad",
                                 "--data-file", str(data), "--store", str(self.store), "--json"],
                                text=True, capture_output=True, encoding="utf-8", cwd=self.root, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        self.assertFalse(self.store.exists())

    def test_cli_rejects_plaintext_argument_without_echoing_it(self):
        for optional_name in (["bad"], []):
            with self.subTest(name_provided=bool(optional_name)):
                result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", MODULE, "create", *optional_name,
                                         "--store", str(self.store), "--key", SECRET, "--json"], input="",
                                        text=True, capture_output=True, encoding="utf-8", cwd=self.root, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(SECRET, result.stdout + result.stderr)
                self.assertFalse(self.store.exists())

    def test_hidden_input_and_unsupported_terminal_do_not_echo(self):
        argv = ["keys", "create", "prompted", "--store", str(self.store), "--prompt-key", "--json"]
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", argv), patch.object(getpass, "getpass", return_value=SECRET), redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(cli.main(), 0)
        self.assertNotIn(SECRET, output.getvalue() + errors.getvalue())
        argv[1] = "update"
        output = io.StringIO()
        with patch.object(sys, "argv", argv), patch.object(getpass, "getpass", side_effect=getpass.GetPassWarning("no tty")), redirect_stdout(output):
            self.assertEqual(cli.main(), 1)
        self.assertIn("--key-stdin", json.loads(output.getvalue())["error"]["message"])


if __name__ == "__main__":
    unittest.main()

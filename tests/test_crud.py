"""CRUD、批次日志、事务边界和独立检测通道的集成检查。"""

from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import UUID, uuid4

from runtime.dispatch import dispatch
from runtime.storage import crud
from runtime.storage.database import SCHEMA_PATH, initialize_database, open_database


class CrudTests(unittest.TestCase):
    def setUp(self):
        self.connection = open_database(":memory:")
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def tearDown(self):
        self.connection.close()

    def request(self, action, kind, **args):
        return dispatch(self.connection, {"action": action, "kind": kind, **args})

    def project(self, name="project"):
        result = self.request("create", "project", data={"name": name})
        self.assertTrue(result["ok"], result)
        return result["id"]

    def layer(self, project_id):
        result = self.request("create", "layer", project_id=project_id, data={
            "name": "主线", "type": "text", "config_ref": "layers/text.toml",
            "axis": {"unit": "秒", "precision": 0.001},
        })
        self.assertTrue(result["ok"], result)
        return result["id"]

    def obj(self, project_id, layer_id=None, information=None):
        if layer_id is None:
            layers = crud.read(self.connection, "layer", project_id=project_id)
            layer_id = layers[0]["id"] if layers else self.layer(project_id)
        result = self.request("create", "object", project_id=project_id, data={
            "config_ref": "objects/text.toml", "layer": layer_id,
            "information": {} if information is None else information,
        })
        self.assertTrue(result["ok"], result)
        return result

    def journal_count(self):
        return self.connection.execute("SELECT count(*) FROM changes").fetchone()[0]

    def test_complete_crud_preserves_json_and_logs_snapshots(self):
        project_id = self.project("O'Neil 的项目")
        layer_id = self.layer(project_id)
        payload = {"text": "你好", "extra": {"values": [1, True, None]}}
        created = self.obj(project_id, layer_id, payload)
        record_id = created["id"]
        self.assertEqual((layer_id, record_id), (1, 2))
        self.assertEqual(created["data"]["information"], payload)
        self.assertEqual(created["checks"]["status"], "completed")
        changed = self.request("update", "object", project_id=project_id, id=record_id,
                               data={"name": "新名字"})
        self.assertEqual(changed["data"]["information"], payload)
        read = self.request("read", "object", project_id=project_id, id=record_id)
        self.assertEqual(read["data"], changed["data"])
        removed = self.request("delete", "object", project_id=project_id, id=record_id)
        self.assertTrue(removed["applied"])
        self.assertEqual(removed["data"], changed["data"])
        self.assertIsNone(self.request("read", "object", project_id=project_id, id=record_id)["data"])
        history = crud.read(self.connection, "change", filters={"kind": "object", "project_id": project_id})
        self.assertEqual([item["action"] for item in history], ["create", "update", "delete"])
        self.assertIsNone(history[0]["before_data"])
        self.assertEqual(history[1]["before_data"]["name"], "")
        self.assertEqual(history[1]["after_data"]["name"], "新名字")
        self.assertIsNone(history[2]["after_data"])
        self.assertEqual(datetime.fromisoformat(history[0]["created_at"]).utcoffset().total_seconds(), 0)

    def test_json_update_replaces_one_field_and_keeps_other_fields(self):
        project_id = self.project()
        created = self.obj(project_id, information={"text": "old", "extra": 1})
        result = self.request("update", "object", project_id=project_id, id=created["id"],
                              data={"information": {"text": "new"}})
        self.assertEqual(result["data"]["information"], {"text": "new"})
        self.assertEqual(result["data"]["config_ref"], "objects/text.toml")

    def test_project_scope_and_shared_counter(self):
        first, second = self.project("first"), self.project("second")
        self.assertEqual(self.layer(first), 1)
        self.assertEqual(self.layer(second), 1)
        self.assertEqual(self.obj(first)["id"], 2)
        self.assertEqual(self.obj(second)["id"], 2)
        self.assertFalse(self.request("read", "object", id=2)["ok"])
        self.assertEqual(self.request("read", "object", project_id=second, id=2)["data"]["project_id"], second)

    def test_batch_shares_operation_id_and_checks_once_after_commit(self):
        project_id = self.project()
        layer_id = self.layer(project_id)
        calls = []

        def checker(changes, read_record):
            self.assertFalse(self.connection.in_transaction)
            self.assertEqual(len(read_record("object", project_id=project_id)), 2)
            calls.append(changes)
            return []

        result = dispatch(self.connection, [
            {"action": "create", "kind": "object", "project_id": project_id,
             "data": {"config_ref": "objects/text.toml", "layer": layer_id, "information": {"text": text}}}
            for text in ("one", "two")
        ], checker=checker)
        self.assertTrue(result["ok"], result)
        self.assertEqual(UUID(hex=result["operation_id"]).version, 4)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0]), 2)
        logs = crud.read(self.connection, "change", filters={"operation_id": result["operation_id"]})
        self.assertEqual(len(logs), 2)
        self.assertTrue(all(log["operation_id"] == result["operation_id"] for log in logs))
        other = self.obj(project_id)
        self.assertNotEqual(result["operation_id"], other["operation_id"])

    def test_failed_batch_rolls_back_rows_counter_and_journal(self):
        project_id = self.project()
        layer_id = self.layer(project_id)
        before_logs = self.journal_count()
        result = dispatch(self.connection, [
            {"action": "create", "kind": "object", "project_id": project_id,
             "data": {"config_ref": "objects/text.toml", "layer": layer_id}},
            {"action": "create", "kind": "object", "project_id": project_id,
             "data": {"config_ref": "objects/text.toml", "layer": 999}},
        ])
        self.assertFalse(result["ok"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["error"]["request_index"], 1)
        self.assertNotIn("results", result)
        self.assertEqual(crud.read(self.connection, "object", project_id=project_id), [])
        self.assertEqual(crud.read(self.connection, "project", id=project_id)["max_id"], 1)
        self.assertEqual(self.journal_count(), before_logs)

    def test_log_write_failure_rolls_back_business_write(self):
        project_id = self.project()
        layer_id = self.layer(project_id)
        self.connection.execute(
            "CREATE TRIGGER fail_log BEFORE INSERT ON changes "
            "BEGIN SELECT RAISE(ABORT, 'log unavailable'); END"
        )
        result = self.request("create", "object", project_id=project_id,
                              data={"config_ref": "objects/text.toml", "layer": layer_id})
        self.assertFalse(result["ok"])
        self.assertEqual(crud.read(self.connection, "object", project_id=project_id), [])
        self.assertEqual(crud.read(self.connection, "project", id=project_id)["max_id"], 1)
        self.assertEqual(self.journal_count(), 2)

    def test_checker_failure_does_not_undo_committed_operation(self):
        project_id = self.project()
        layer_id = self.layer(project_id)

        def checker(changes, read_record):
            raise RuntimeError("custom checker failed")

        result = dispatch(self.connection, {
            "action": "create", "kind": "object", "project_id": project_id,
            "data": {"config_ref": "objects/text.toml", "layer": layer_id, "information": {"text": 123}},
        }, checker=checker)
        self.assertTrue(result["ok"])
        self.assertTrue(result["applied"])
        self.assertEqual(result["checks"]["status"], "failed")
        self.assertEqual(crud.read(self.connection, "object", project_id=project_id, id=result["id"])["information"], {"text": 123})
        self.assertEqual(len(crud.read(self.connection, "change", filters={"operation_id": result["operation_id"]})), 1)

    def test_checker_can_report_content_issue_without_rejecting_write(self):
        project_id = self.project()
        layer_id = self.layer(project_id)

        def checker(changes, read_record):
            change = changes[0]
            record = read_record("object", project_id=project_id, id=change["id"])
            return [{"field": "information.text", "message": "应为字符串"}] if not isinstance(record["information"]["text"], str) else []

        result = dispatch(self.connection, {
            "action": "create", "kind": "object", "project_id": project_id,
            "data": {"config_ref": "objects/text.toml", "layer": layer_id, "information": {"text": 123}},
        }, checker=checker)
        self.assertTrue(result["applied"])
        self.assertEqual(result["checks"]["status"], "completed")
        self.assertEqual(len(result["checks"]["issues"]), 1)

    def test_invalid_checker_output_is_check_failure_only(self):
        result = dispatch(self.connection, {"action": "create", "kind": "project", "data": {}},
                          checker=lambda changes, read_record: {"issues": []})
        self.assertTrue(result["ok"])
        self.assertTrue(result["applied"])
        self.assertEqual(result["checks"]["status"], "failed")

    def test_read_and_noop_do_not_log_or_check(self):
        project_id = self.project()
        logs = self.journal_count()

        def checker(changes, read_record):
            self.fail("read or noop must not invoke checker")

        requests = [
            {"action": "read", "kind": "project", "id": project_id},
            {"action": "update", "kind": "project", "id": project_id, "data": {"name": "project"}},
            {"action": "update", "kind": "project", "id": project_id, "data": {}},
            {"action": "update", "kind": "project", "id": 999, "data": {"name": "missing"}},
            {"action": "delete", "kind": "project", "id": 999},
        ]
        for request in requests:
            result = dispatch(self.connection, request, checker=checker)
            self.assertTrue(result["ok"], result)
            self.assertFalse(result["applied"])
            self.assertEqual(result["checks"]["status"], "not_run")
        self.assertEqual(self.journal_count(), logs)

    def test_managed_identity_fields_cannot_be_overwritten(self):
        project_id = self.project()
        layer_id = self.layer(project_id)
        logs = self.journal_count()
        for field in ("id", "project_id"):
            result = self.request("update", "layer", project_id=project_id, id=layer_id, data={field: 99})
            self.assertFalse(result["ok"])
        self.assertFalse(self.request("update", "project", id=project_id, data={"max_id": 0})["ok"])
        self.assertFalse(self.request("create", "object", project_id=project_id,
                                      data={"id": 99, "config_ref": "objects/text.toml"})["ok"])
        self.assertEqual(self.journal_count(), logs)
        self.assertEqual(crud.read(self.connection, "project", id=project_id)["max_id"], 1)

    def test_cross_project_bind_and_history_survive_entity_deletion(self):
        first, second = self.project("first"), self.project("second")
        source = self.layer(first)
        target = self.obj(second)["id"]
        binding = self.request("create", "bind", data={
            "source_kind": "layer", "source_project_id": first, "source_id": source,
            "target_kind": "object", "target_project_id": second, "target_id": target,
            "tips": "跨项目引用",
        })
        self.assertTrue(binding["ok"], binding)
        removed = self.request("delete", "object", project_id=second, id=target)
        self.assertTrue(removed["applied"])
        self.assertEqual(crud.read(self.connection, "bind", id=binding["id"])["target_id"], target)
        target_layer = crud.read(self.connection, "layer", project_id=second)[0]["id"]
        self.assertTrue(self.request("delete", "layer", project_id=second, id=target_layer)["applied"])
        self.assertTrue(self.request("delete", "project", id=second)["applied"])
        history = crud.read(self.connection, "change", filters={"project_id": second})
        self.assertEqual([row["action"] for row in history], ["create", "create", "create", "delete", "delete", "delete"])

    def test_deleting_referenced_layer_is_not_cascaded_or_logged(self):
        project_id = self.project()
        layer_id = self.layer(project_id)
        self.obj(project_id, layer_id)
        logs = self.journal_count()
        result = self.request("delete", "layer", project_id=project_id, id=layer_id)
        self.assertFalse(result["ok"])
        self.assertEqual(self.journal_count(), logs)
        self.assertEqual(len(crud.read(self.connection, "object", project_id=project_id)), 1)

    def test_filters_and_ordering(self):
        project_id = self.project()
        layer_id = self.layer(project_id)
        for begin, end in ((5, 6), (1, 3), (1, 2)):
            result = self.request("create", "object", project_id=project_id, data={
                "name": "same", "config_ref": "objects/text.toml", "layer": layer_id, "begin": begin, "end": end,
            })
            self.assertTrue(result["ok"], result)
        records = self.request("read", "object", project_id=project_id, filters={"name": "same", "layer": layer_id})["data"]
        self.assertEqual([(row["begin"], row["end"]) for row in records], [(1, 2), (1, 3), (5, 6)])
        self.assertIsNone(self.request("read", "object", project_id=project_id, id=999)["data"])

    def test_config_reference_is_stored_without_running_configuration_checks(self):
        project_id = self.project()
        layer_id = self.layer(project_id)
        result = dispatch(self.connection, {"action": "create", "kind": "object", "project_id": project_id, "data": {
            "config_ref": "objects/not-yet-written.toml", "layer": layer_id, "information": {"anything": [1, 2]},
        }}, checker=None)
        self.assertTrue(result["ok"])
        self.assertEqual(result["checks"]["reason"], "not_configured")
        self.assertEqual(result["data"]["config_ref"], "objects/not-yet-written.toml")

    def test_dispatch_does_not_commit_callers_transaction(self):
        self.connection.execute("INSERT INTO projects (name) VALUES ('pending')")
        result = self.request("read", "project")
        self.assertFalse(result["ok"])
        self.assertTrue(self.connection.in_transaction)
        self.connection.rollback()
        self.assertEqual(crud.read(self.connection, "project"), [])

    def test_low_level_functions_share_caller_transaction_and_operation_id(self):
        operation_id = uuid4().hex
        self.connection.execute("BEGIN IMMEDIATE")
        project, _ = crud.create(self.connection, "project", {"name": "composed"}, operation_id=operation_id)
        layer, _ = crud.create(self.connection, "layer", {
            "type": "text", "config_ref": "layers/text.toml",
        }, project_id=project["id"], operation_id=operation_id)
        crud.create(self.connection, "object", {"config_ref": "objects/text.toml", "layer": layer["id"]},
                    project_id=project["id"], operation_id=operation_id)
        self.assertTrue(self.connection.in_transaction)
        self.assertEqual(len(crud.read(self.connection, "change", filters={"operation_id": operation_id})), 3)
        self.connection.rollback()
        self.assertEqual(crud.read(self.connection, "project"), [])
        self.assertEqual(self.journal_count(), 0)

    def test_cli_uses_json_and_reports_operation_failure_with_exit_code(self):
        with tempfile.NamedTemporaryFile(prefix="ai-production-crud-", suffix=".sqlite3", delete=False) as file:
            path = Path(file.name)
        self.addCleanup(path.unlink)
        initialize_database(path)
        command = [sys.executable, "-X", "utf8", "-B", "-m", "tools.usage.crud", str(path)]
        cwd = Path(__file__).resolve().parents[1] / "src"
        result = subprocess.run(command, input=json.dumps({
            "action": "create", "kind": "project", "data": {"name": "CLI 项目"},
        }), text=True, encoding="utf-8", capture_output=True, cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        created = json.loads(result.stdout)
        self.assertEqual(created["data"]["name"], "CLI 项目")
        self.assertEqual(created["checks"]["status"], "completed")
        failed = subprocess.run(command, input=json.dumps({"action": "delete", "kind": "project"}),
                                text=True, encoding="utf-8", capture_output=True, cwd=cwd)
        self.assertEqual(failed.returncode, 1)
        self.assertFalse(json.loads(failed.stdout)["applied"])
        with closing(open_database(path)) as connection:
            self.assertEqual(len(crud.read(connection, "project")), 1)
            self.assertEqual(len(crud.read(connection, "change")), 1)
        path.write_bytes(b"not a SQLite database")
        broken = subprocess.run(command, input=json.dumps({"action": "read", "kind": "project"}),
                                text=True, encoding="utf-8", capture_output=True, cwd=cwd)
        self.assertEqual(broken.returncode, 1)
        self.assertFalse(json.loads(broken.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()

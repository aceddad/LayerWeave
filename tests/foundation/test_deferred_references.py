"""延迟外键失败的可定位反馈，以及编号/日志/数据共同回滚。"""
import sqlite3
import unittest

from layerweave.support.api import open_database, read_record, run_operation, transaction
from layerweave.support.storage.database import SCHEMA_PATH


class DeferredReferenceTests(unittest.TestCase):
    def setUp(self):
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        with transaction(self.c) as write:
            self.p = write.create("project", {})["id"]
            self.layer = write.create("layer", {"type": "text", "config_ref": "layers/text.toml"}, project_id=self.p)["id"]
            self.obj = write.create("object", {"config_ref": "objects/text.toml", "layer": self.layer},
                                    project_id=self.p)["id"]

    def snapshot(self):
        return {kind: read_record(self.c, kind, **({"project_id": self.p} if kind in {"layer", "object"} else {}))
                for kind in ("project", "layer", "object", "bind", "change")}

    def test_missing_layer_reports_all_targets_and_rolls_back_ids_logs_and_rows(self):
        before = self.snapshot()

        def work(write):
            write.defer_references()
            layer = write.create("layer", {"type": "text", "config_ref": "layers/text.toml", "father": 998}, project_id=self.p)
            obj = write.create("object", {"config_ref": "objects/text.toml", "layer": 999}, project_id=self.p)
            return layer, obj

        result = run_operation(self.c, work)
        self.assertEqual(result["operation"]["status"], "failed")
        self.assertEqual(result["checks"]["status"], "not_run")
        self.assertEqual(result["error"]["type"], "IntegrityError")
        violations = result["error"]["violations"]
        self.assertEqual({v["field"] for v in violations}, {"father", "layer"})
        self.assertEqual({v["reference"]["id"] for v in violations}, {998, 999})
        self.assertEqual({v["target"]["id"] for v in violations}, {self.obj + 1, self.obj + 2})
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.c.in_transaction)

    def test_deleted_project_explains_remaining_references_and_rolls_back(self):
        before = self.snapshot()

        def work(write):
            write.defer_references()
            write.delete("project", self.p)

        result = run_operation(self.c, work)
        self.assertEqual(result["operation"]["status"], "failed")
        self.assertEqual({v["target"]["kind"] for v in result["error"]["violations"]}, {"layer", "object"})
        self.assertTrue(all(v["reference"] == {"kind": "project", "project_id": None, "id": self.p}
                            for v in result["error"]["violations"]))
        self.assertEqual(self.snapshot(), before)

    def test_direct_transaction_error_keeps_details_and_rolls_back(self):
        before = self.snapshot()
        with self.assertRaises(sqlite3.IntegrityError) as raised:
            with transaction(self.c) as write:
                write.defer_references()
                write.delete("layer", self.layer, project_id=self.p)
        self.assertIn(f"所属层 ({self.p}, {self.layer}) 不存在", str(raised.exception))
        self.assertEqual(raised.exception.details["target"], {"kind": "object", "project_id": self.p, "id": self.obj})
        self.assertEqual(self.snapshot(), before)

    def test_successful_deferred_transaction_has_no_extra_foreign_key_scan(self):
        statements = []
        self.c.set_trace_callback(statements.append)
        with transaction(self.c) as write:
            write.defer_references()
            write.delete("layer", self.layer, project_id=self.p)
            write.delete("object", self.obj, project_id=self.p)
        self.assertFalse(any("foreign_key_check" in sql.lower() for sql in statements))
        self.assertIsNone(read_record(self.c, "layer", project_id=self.p, id=self.layer))
        self.assertIsNone(read_record(self.c, "object", project_id=self.p, id=self.obj))


if __name__ == "__main__":
    unittest.main()

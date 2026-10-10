"""可空所属层的旧库升级；保留数据和附加索引，拒绝猜测旧对象归属。"""

import sqlite3
import unittest

from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.support.storage import crud
from layerweave.support.storage.database import SCHEMA_PATH, open_database, require_object_layer


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.connection = open_database(":memory:")
        self.addCleanup(self.connection.close)
        legacy = SCHEMA_PATH.read_text(encoding="utf-8").replace("layer       INTEGER NOT NULL,", "layer       INTEGER,")
        self.connection.executescript(legacy)
        self.project = dispatch(self.connection, {"action": "create", "kind": "project", "data": {}}, checker=None)["id"]
        self.layer = dispatch(self.connection, {"action": "create", "kind": "layer", "project_id": self.project,
                                               "data": {"type": "text", "config_ref": "layers/text.toml"}}, checker=None)["id"]

    def create(self, layer):
        return dispatch(self.connection, {"action": "create", "kind": "object", "project_id": self.project,
                                          "data": {"layer": layer, "config_ref": "objects/text.toml", "information": {"text": "保留"}}}, checker=None)

    def snapshot(self):
        return {kind: crud.read(self.connection, kind, **({"project_id": self.project} if kind in {"layer", "object"} else {}))
                for kind in ("project", "layer", "object", "bind", "change")}

    def test_migration_preserves_rows_logs_indexes_and_enforces_not_null(self):
        result = self.create(self.layer)
        self.connection.execute("CREATE INDEX custom_object_name ON objects(name)")
        before = self.snapshot()
        require_object_layer(self.connection)
        require_object_layer(self.connection)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(self.connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertIsNotNone(self.connection.execute("SELECT name FROM sqlite_master WHERE name='custom_object_name'").fetchone())
        with self.assertRaises(sqlite3.IntegrityError), self.connection:
            self.connection.execute("UPDATE objects SET layer=NULL WHERE id=?", (result["id"],))

    def test_orphan_blocks_migration_without_deleting_or_reassigning(self):
        self.create(None)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "缺少所属层"):
            require_object_layer(self.connection)
        self.assertEqual(self.snapshot(), before)
        layer_column = next(row for row in self.connection.execute("PRAGMA table_info(objects)") if row["name"] == "layer")
        self.assertEqual(layer_column["notnull"], 0)
        self.assertFalse(self.connection.in_transaction)

    def test_migration_does_not_commit_callers_transaction(self):
        self.connection.execute("UPDATE projects SET tips='pending'")
        with self.assertRaisesRegex(ValueError, "待提交"):
            require_object_layer(self.connection)
        self.assertTrue(self.connection.in_transaction)
        self.connection.rollback()

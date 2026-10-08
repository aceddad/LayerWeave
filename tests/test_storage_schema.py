"""核对四表存储语义，所有用例使用内存数据库。"""

import json
import unittest

from runtime.storage.database import SCHEMA_PATH, allocate_id, open_database


class StorageSchemaTests(unittest.TestCase):
    def setUp(self):
        self.connection = open_database(":memory:")
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def tearDown(self):
        self.connection.close()

    def project(self, name="project"):
        return self.connection.execute(
            "INSERT INTO projects (name) VALUES (?)", (name,)
        ).lastrowid

    def layer(self, project_id, name="layer", father=None):
        entity_id = allocate_id(self.connection, project_id)
        self.connection.execute(
            "INSERT INTO layers (project_id, id, name, type, config_ref, father) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, entity_id, name, "text", "layers/text.toml", father),
        )
        return entity_id

    def obj(self, project_id, layer_id=None, information=None):
        if layer_id is None:
            row = self.connection.execute("SELECT id FROM layers WHERE project_id = ? ORDER BY id LIMIT 1", (project_id,)).fetchone()
            layer_id = row[0] if row else self.layer(project_id)
        entity_id = allocate_id(self.connection, project_id)
        self.connection.execute(
            "INSERT INTO objects (project_id, id, config_ref, layer, information) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, entity_id, "objects/text.toml", layer_id,
             json.dumps(information or {}, ensure_ascii=False)),
        )
        return entity_id

    def test_business_tables_and_journal_reinitialization_preserves_data(self):
        with self.connection:
            project_id = self.project()
            self.layer(project_id)
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        tables = {row[0] for row in self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )}
        self.assertEqual(tables, {"projects", "layers", "objects", "binds", "changes"})
        self.assertEqual(self.connection.execute("SELECT max_id FROM projects").fetchone()[0], 1)
        self.assertEqual(self.connection.execute("SELECT count(*) FROM layers").fetchone()[0], 1)

    def test_counter_shared_by_entities_and_independent_between_projects(self):
        with self.connection:
            first = self.project("first")
            second = self.project("second")
            layer_id = self.layer(first)
            object_id = self.obj(first, layer_id)
            second_layer = self.layer(second)
        self.assertEqual((layer_id, object_id, second_layer), (1, 2, 1))
        counters = [row[0] for row in self.connection.execute("SELECT max_id FROM projects ORDER BY id")]
        self.assertEqual(counters, [2, 1])

    def test_committed_id_is_not_reused_after_delete(self):
        with self.connection:
            project_id = self.project()
            self.obj(project_id)
        with self.connection:
            self.connection.execute("DELETE FROM objects WHERE project_id = ?", (project_id,))
            new_id = self.obj(project_id)
        self.assertEqual(new_id, 3)

    def test_rollback_reverts_allocation_and_entity_write(self):
        with self.connection:
            project_id = self.project()
        with self.assertRaisesRegex(RuntimeError, "cancel"):
            with self.connection:
                self.layer(project_id)
                raise RuntimeError("cancel")
        self.assertEqual(self.connection.execute("SELECT max_id FROM projects").fetchone()[0], 0)
        self.assertEqual(self.connection.execute("SELECT count(*) FROM layers").fetchone()[0], 0)
        with self.connection:
            self.assertEqual(self.layer(project_id), 1)

    def test_layer_reference_uses_the_same_project(self):
        import sqlite3

        with self.connection:
            first = self.project("first")
            second = self.project("second")
            layer_id = self.layer(first)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.connection:
                self.obj(second, layer_id)
        self.assertEqual(self.connection.execute(
            "SELECT max_id FROM projects WHERE id = ?", (second,)
        ).fetchone()[0], 0)
        with self.connection:
            second_layer = self.layer(second)
            self.obj(second, second_layer)

    def test_cross_project_bind_survives_missing_target(self):
        with self.connection:
            first = self.project("first")
            second = self.project("second")
            source = self.layer(first)
            target = self.obj(second)
            bind_id = self.connection.execute(
                "INSERT INTO binds (source_kind, source_project_id, source_id, "
                "target_kind, target_project_id, target_id, tips) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("layer", first, source, "object", second, target, "引用对象"),
            ).lastrowid
        with self.connection:
            self.connection.execute("DELETE FROM objects WHERE project_id = ? AND id = ?", (second, target))
        row = self.connection.execute("SELECT * FROM binds WHERE id = ?", (bind_id,)).fetchone()
        self.assertEqual((row["target_project_id"], row["target_id"], row["tips"]), (second, target, "引用对象"))
        self.assertEqual([row[0] for row in self.connection.execute("SELECT max_id FROM projects ORDER BY id")], [1, 2])

    def test_delete_does_not_silently_cascade(self):
        import sqlite3

        with self.connection:
            project_id = self.project()
            layer_id = self.layer(project_id)
            self.obj(project_id, layer_id)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.connection:
                self.connection.execute("DELETE FROM layers WHERE project_id = ? AND id = ?", (project_id, layer_id))
        self.assertEqual(self.connection.execute("SELECT count(*) FROM objects").fetchone()[0], 1)

    def test_content_and_configuration_reference_are_preserved(self):
        information = {"text": "自由内容", "extra": {"values": [1, True, None]}}
        with self.connection:
            project_id = self.project()
            object_id = self.obj(project_id, information=information)
            self.connection.execute(
                'UPDATE objects SET "begin" = 5, "end" = 1 WHERE project_id = ? AND id = ?',
                (project_id, object_id),
            )
        row = self.connection.execute("SELECT * FROM objects").fetchone()
        self.assertEqual(json.loads(row["information"]), information)
        self.assertEqual(row["config_ref"], "objects/text.toml")
        self.assertEqual((row["begin"], row["end"]), (5, 1))


if __name__ == "__main__":
    unittest.main()

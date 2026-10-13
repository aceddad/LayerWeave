"""增量日志的分页、恢复、托管表和双连接快照。"""
from contextlib import closing
from pathlib import Path
import tempfile
import unittest

from layerweave.support.api import (open_database, transaction, run_operation, read_snapshot, read_record,
                                   change_cursor, read_changes, register_tables, allocate)
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.support.feedback import InputError
from layerweave.tool.builtin.usage.undo.service import undo_operation


class ChangeFeedTests(unittest.TestCase):
    def setUp(self):
        self.c = open_database(":memory:")
        self.addCleanup(self.c.close)
        self.c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def make_batch(self, count):
        with transaction(self.c) as w:
            for i in range(count):
                w.create("project",{"name":str(i)})
        return w.operation_id

    def test_empty_feed_and_tail_are_read_only(self):
        before = list(self.c.iterdump())
        self.assertEqual(change_cursor(self.c),0)
        self.assertEqual(read_changes(self.c),{"changes":[],"next_cursor":0,"has_more":False})
        self.assertEqual(list(self.c.iterdump()),before)
        self.assertFalse(self.c.in_transaction)

    def test_page_extends_last_operation_and_never_skips_next_one(self):
        first = self.make_batch(3)
        second = self.make_batch(2)
        final = self.make_batch(1)
        one = read_changes(self.c,limit=1)
        self.assertEqual([r["operation_id"] for r in one["changes"]],[first]*3)
        self.assertEqual((one["next_cursor"],one["has_more"]),(3,True))
        two = read_changes(self.c,after=one["next_cursor"],limit=1)
        self.assertEqual([r["operation_id"] for r in two["changes"]],[second]*2)
        three = read_changes(self.c,after=two["next_cursor"],limit=1)
        self.assertEqual([r["operation_id"] for r in three["changes"]],[final])
        self.assertFalse(three["has_more"])
        tail = read_changes(self.c,after=three["next_cursor"])
        self.assertEqual(tail,{"changes":[],"next_cursor":6,"has_more":False})

    def test_new_commits_between_pages_are_not_skipped(self):
        self.make_batch(2)
        self.make_batch(1)
        first = read_changes(self.c,limit=1)
        self.make_batch(2)
        later = read_changes(self.c,after=first["next_cursor"])
        self.assertEqual([r["id"] for r in later["changes"]],[3,4,5])
        self.assertFalse(later["has_more"])

    def test_noop_allocation_only_and_rollback_do_not_create_change_events(self):
        self.make_batch(1)
        cursor = change_cursor(self.c)
        run_operation(self.c,lambda w: w.update("project",1,{"name":"0"}))
        run_operation(self.c,lambda w: allocate("project_entities",data={"project_id":1}))
        def work(w):
            w.update("project",1,{"name":"rollback"})
            raise ValueError("test")
        self.assertFalse(run_operation(self.c,work)["ok"])
        self.assertEqual(read_changes(self.c,after=cursor)["changes"],[])
        self.assertEqual(change_cursor(self.c),cursor)

    def test_delete_and_undo_include_raw_snapshots_for_tool_tables(self):
        register_tables(self.c,{"review":{"scoped":False,"fields":{"data":{"type":"JSON","default":{}}}}})
        made = run_operation(self.c,lambda w: w.create("review",{"data":{"text":"note"}}))
        cursor = change_cursor(self.c)
        gone = run_operation(self.c,lambda w: w.delete("review",made["data"]["id"]))
        undone = undo_operation(self.c,gone["operation_id"])
        self.assertTrue(undone["ok"])
        rows = read_changes(self.c,after=cursor)["changes"]
        self.assertEqual([r["action"] for r in rows],["delete","create"])
        self.assertEqual(rows[0]["before_data"]["data"],{"text":"note"})
        self.assertIsNone(rows[0]["after_data"])
        self.assertEqual(rows[1]["undo_of"],gone["operation_id"])
        self.assertEqual(rows[1]["after_data"],made["data"])

    def test_binding_both_projects_remain_visible_without_scope_filter(self):
        self.make_batch(2)
        cursor = change_cursor(self.c)
        with transaction(self.c) as w:
            w.create("bind",{"source_kind":"object","source_project_id":1,"source_id":8,
                             "target_kind":"object","target_project_id":2,"target_id":8})
        row = read_changes(self.c,after=cursor)["changes"][0]
        self.assertEqual((row["after_data"]["source_project_id"],row["after_data"]["target_project_id"]),(1,2))

    def test_invalid_and_partial_operation_cursors_are_explicit(self):
        self.make_batch(3)
        with self.assertRaises(InputError) as error:
            read_changes(self.c,after=1)
        self.assertEqual(error.exception.details["code"],"cursor_inside_operation")
        with self.assertRaises(InputError) as error:
            read_changes(self.c,after=9999)
        self.assertEqual(error.exception.details["code"],"cursor_ahead")
        for kwargs in ({"after":-1},{"after":True},{"after":"1"},{"limit":0},{"limit":True}):
            with self.assertRaises(ValueError):
                read_changes(self.c,**kwargs)

    def test_one_large_operation_is_returned_whole(self):
        self.make_batch(800)
        result = read_changes(self.c,limit=20)
        self.assertEqual(len(result["changes"]),800)
        self.assertEqual(result["next_cursor"],800)
        self.assertFalse(result["has_more"])

    def test_snapshot_bootstrap_with_second_connection_cannot_lose_updates(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"snapshot.sqlite3"
            with closing(open_database(path)) as first, closing(open_database(path)) as second:
                first.execute("PRAGMA journal_mode=WAL")
                first.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
                with transaction(first) as w:
                    p = w.create("project",{"name":"old"})["id"]
                with read_snapshot(first):
                    initial = read_record(first,"project",id=p)
                    with transaction(second) as w:
                        w.update("project",p,{"name":"new"})
                    cursor = change_cursor(first)
                    self.assertEqual(initial["name"],"old")
                    self.assertEqual(cursor,1)
                    self.assertEqual(read_changes(first,after=cursor)["changes"],[])
                later = read_changes(first,after=cursor)
                self.assertEqual(later["changes"][0]["after_data"]["name"],"new")
                self.assertEqual(later["next_cursor"],2)


if __name__ == "__main__":
    unittest.main()

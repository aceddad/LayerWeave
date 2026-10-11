"""自定义视图身份、登记新发号簇与恢复；仅使用临时数据库。"""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.support.api import (allocate, initialize_database, open_database, register_tables,
                                   register_numbering, transaction, run_operation, read_record)
from layerweave.tool.builtin.usage.undo.service import undo_operation


def main():
    with TemporaryDirectory(prefix="layerweave-numbering-example-") as folder:
        database = initialize_database(Path(folder) / "example.sqlite3")
        with closing(open_database(database)) as connection:
            register_tables(connection, {
                "view_state": {"id_source": "provided", "fields": {"collapsed": {"type": "INTEGER", "default": 0}},
                               "references": [{"fields": ["project_id", "id"], "kind": "layer"}]},
                "task_counter": {"scoped": False, "id_source": "provided", "fields": {"max_num": {"type": "INTEGER", "default": 0}}},
                "task": {"fields": {"name": "TEXT"}},
            })
            register_numbering(connection, {"tasks": {
                "rule": "project_entity", "counter": {"kind": "task_counter", "field": "max_num", "key": {"id": "project_id"}},
                "members": ["task"],
            }})
            with transaction(connection) as write:
                project = write.create("project", {"name": "发号示例"})
                p = project["id"]
                layer = write.create("layer", {"type": "text", "config_ref": "layers/text.toml", "name": "字幕"}, project_id=p)
                view = write.create("view_state", {"id": layer["id"], "collapsed": 1}, project_id=p)
                write.create("task_counter", {"id": p})
                task = write.create("task", {"name": "生成预览"}, project_id=p)
            print("同编号不同表：", layer["id"], view["id"], task["id"])
            assert layer["id"] == view["id"] == task["id"]
            with transaction(connection):
                print("只领号：", allocate("tasks", data={"project_id": p}))
            removed = run_operation(connection, lambda w: w.delete("view_state", view["id"], project_id=p))
            restored = undo_operation(connection, removed["operation_id"])
            assert restored["ok"], restored
            assert read_record(connection, "view_state", project_id=p, id=layer["id"])["collapsed"] == 1
            print("原身份恢复成功；任务计数：", read_record(connection, "task_counter", id=p)["max_num"])


if __name__ == "__main__":
    main()

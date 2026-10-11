"""python -X utf8 -B examples/tool_tables.py：工具表和对象共用日志、撤销及恢复。"""
from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.support.api import initialize_database, open_database, read_record, register_tables, run_operation, table_specs, transaction
from layerweave.tool.builtin.usage.history.service import read_history
from layerweave.tool.builtin.usage.undo.service import undo_operation


DEFINITIONS = {
    "review_note": {
        "fields": {
            "object_id": {"type": "INTEGER", "nullable": False},
            "note": {"type": "TEXT", "default": ""},
            "details": {"type": "JSON", "default": {}},
        },
        "references": [{"fields": ["project_id", "object_id"], "kind": "object"}],
    },
}


def checked(result):
    if not result["ok"]:
        raise RuntimeError(result["error"])
    return result


def create_example():
    with TemporaryDirectory(prefix="layerweave-tool-table-example-") as directory:
        database = initialize_database(Path(directory) / "example.sqlite3")
        with closing(open_database(database)) as connection:
            register_tables(connection, DEFINITIONS)
            with transaction(connection) as write:
                project_id = write.create("project", {"name": "工具表演示"})["id"]
                layer = write.create("layer", {"type": "text", "config_ref": "layers/text.toml"}, project_id=project_id)
                obj = write.create("object", {"config_ref": "objects/text.toml", "layer": layer["id"],
                                              "information": {"text": "原稿"}}, project_id=project_id)

            def work(write):
                write.update("object", obj["id"], {"information": {"text": "修订稿"}}, project_id=project_id)
                return write.create("review_note", {"object_id": obj["id"], "note": "采用这次修订",
                                                     "details": {"resolved": True}}, project_id=project_id)

            edited = checked(run_operation(connection, work))
            history = read_history(connection, operation_id=edited["operation_id"])
            undone = checked(undo_operation(connection, edited["operation_id"]))
            after_undo = {"text": read_record(connection, "object", project_id=project_id, id=obj["id"])["information"]["text"],
                          "notes": read_record(connection, "review_note", project_id=project_id)}
            redone = checked(undo_operation(connection, undone["operation_id"]))

        # 重开时不再运行表声明，也不需要导入工具的自定义类。
        with closing(open_database(database)) as connection:
            return {"registered_table": table_specs(connection)["review_note"]["table"],
                    "mixed_changes": edited["operation"]["changes"], "history": history,
                    "after_undo": after_undo, "redo_status": redone["operation"]["status"],
                    "reopened_notes": read_record(connection, "review_note", project_id=project_id)}


if __name__ == "__main__":
    print(json.dumps(create_example(), ensure_ascii=False, indent=2))

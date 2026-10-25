"""BLOB 与注销托管示例；只创建专用临时数据库，不依赖任何外部服务。"""
from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.support.api import (initialize_database, open_database, register_tables,
    unregister_tables, retired_tables, transaction, run_operation, read_record, binary_json_default)
from layerweave.tool.builtin.usage.exchange.exporting import export_project
from layerweave.tool.builtin.usage.history.service import read_history
from layerweave.tool.builtin.usage.undo.service import undo_operation


def main():
    with TemporaryDirectory(prefix="layerweave-binary-example-") as directory:
        path = initialize_database(Path(directory) / "example.sqlite3")
        with closing(open_database(path)) as connection:
            register_tables(connection, {"binary_cache": {"fields": {"payload": "BLOB", "label": "TEXT"}}})
            with transaction(connection) as write:
                project_id = write.create("project", {"name": "二进制示例"})["id"]
            made = run_operation(connection, lambda write: write.create("binary_cache",
                {"payload": b"\x00\x01\xff", "label": "由工具解释内容"}, project_id=project_id))
            assert made["ok"], made
            record_id = made["data"]["id"]
            undone = undo_operation(connection, made["operation_id"], checker=None)
            assert undone["ok"], undone
            redone = undo_operation(connection, undone["operation_id"], checker=None)
            assert redone["ok"], redone
            assert read_record(connection, "binary_cache", project_id=project_id, id=record_id)["payload"] == b"\x00\x01\xff"
            document = export_project(connection, project_id)
            assert document["records"][0]["data"]["payload"] == "AAH/"
            print("JSON 交换记录：", json.dumps(document["records"], ensure_ascii=False))

            result = unregister_tables(connection, ["binary_cache"])
            assert connection.execute("SELECT COUNT(*) FROM tool_binary_cache").fetchone()[0] == 1
            assert "binary_cache" in retired_tables(connection)
            print("退出托管，物理表保留：", json.dumps(result, ensure_ascii=False))
            history = read_history(connection, operation_id=made["operation_id"])
            print("历史仍可读：", json.dumps(history, ensure_ascii=False, default=binary_json_default))
            blocked = undo_operation(connection, redone["operation_id"], checker=None)
            assert not blocked["ok"] and blocked["error"]["code"] == "retired_kind"
            print("恢复被明确拒绝：", blocked["error"]["message"])


if __name__ == "__main__":
    main()

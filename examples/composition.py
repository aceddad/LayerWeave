"""事务内组合与领号反馈；只使用临时数据库。"""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.support.api import initialize_database, open_database, transaction, run_operation, allocate, read_record
from layerweave.support.providers import optional_checker
from layerweave.tool.builtin.usage.editing.objects import append_object_in_session
from layerweave.tool.builtin.usage.editing.timeline import shift_objects_in_session
from layerweave.tool.builtin.usage.editing.positions import set_duration_in_session


def main():
    with TemporaryDirectory(prefix="layerweave-composition-") as folder:
        path = initialize_database(Path(folder) / "example.sqlite3")
        with closing(open_database(path)) as connection:
            with transaction(connection) as write:
                project_id = write.create("project", {"name": "组合示例"})["id"]
                layer_id = write.create("layer", {
                    "type": "text", "config_ref": "layers/text.toml", "name": "字幕",
                }, project_id=project_id)["id"]

            def compose(write):
                objects = [append_object_in_session(write, project_id, layer_id, {
                    "config_ref": "objects/text.toml", "information": {"text": text},
                }, duration=2) for text in ("第一句", "第二句")]
                return shift_objects_in_session(write, project_id, [row["id"] for row in objects], offset=1)

            result = run_operation(connection, compose, checker=optional_checker())
            assert result["ok"], result
            print("一次提交：", [(row["begin"], row["end"]) for row in result["data"]])
            before = read_record(connection, "project", id=project_id)

            def fails(write):
                write.update("project", project_id, {"tips": "应当回滚"})
                set_duration_in_session(write, project_id, 999999, 1)

            failed = run_operation(connection, fails)
            assert not failed["ok"]
            assert read_record(connection, "project", id=project_id) == before
            print("失败整批回滚：", failed["error"]["message"])
            allocated = run_operation(connection, lambda write: allocate("project_entities", data={"project_id": project_id}))
            assert allocated["applied"] and allocated["operation"]["status"] == "committed"
            assert allocated["operation"]["changes"] == []
            print("仅领号也明确提交：", allocated["data"], allocated["operation"]["numbering"])


if __name__ == "__main__":
    main()

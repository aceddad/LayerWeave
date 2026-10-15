"""临时库演示：状态随层换号、已读记录不复制，业务整批可撤销。"""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.support.api import (
    initialize_database, open_database, read_record, register_tables, transaction,
)
from layerweave.tool.builtin.usage.exchange import export_project, import_project
from layerweave.tool.builtin.usage.undo.service import undo_operation


TABLES = {
    "layer_state": {
        "id_source": "provided",
        "fields": {"fold": {"type": "TEXT", "default": ""}},
        "logical_references": [{"fields": ["project_id", "id"], "kind": "layer"}],
    },
    "read_state": {
        "id_source": "provided",
        "fields": {"reads": {"type": "JSON", "default": {}}},
        "logical_references": [{"fields": ["project_id", "id"], "kind": "object"}],
        "exchange": {"on_copy": "skip"},
    },
}


def main():
    with TemporaryDirectory(prefix="layerweave-logical-") as folder:
        root = Path(folder)
        source_path = initialize_database(root / "source.sqlite3")
        target_path = initialize_database(root / "target.sqlite3")
        with closing(open_database(source_path)) as source, closing(open_database(target_path)) as target:
            register_tables(source, TABLES)
            with transaction(source) as write:
                project = write.create("project", {"name": "源项目"})["id"]
                top = write.create("layer", {
                    "type": "text", "name": "主线", "config_ref": "layers/text.toml",
                }, project_id=project)["id"]
                story = write.create("layer", {
                    "type": "text", "name": "故事", "father": top, "config_ref": "layers/text.toml",
                }, project_id=project)["id"]
                note = write.create("object", {
                    "layer": story, "config_ref": "objects/text.toml", "information": {"text": "第一段"},
                }, project_id=project)["id"]
                write.create("layer_state", {"id": story, "fold": "closed"}, project_id=project)
                write.create("read_state", {"id": note, "reads": {"reader": note}}, project_id=project)

            # 目标已有一层，确保复制后的编号与来源不同。
            with transaction(target) as write:
                destination = write.create("project", {"name": "目标项目"})["id"]
                write.create("layer", {
                    "type": "text", "name": "原有层", "config_ref": "layers/text.toml",
                }, project_id=destination)

            document = export_project(source, project, op="add")
            result = import_project(target, document, project_id=destination)
            assert result["ok"], result
            new_story = next(item["target"]["id"] for item in result["data"]["id_map"]
                             if item["source"]["kind"] == "layer" and item["source"]["id"] == story)
            assert new_story != story
            assert read_record(target, "layer_state", project_id=destination)[0]["id"] == new_story
            assert read_record(target, "read_state", project_id=destination) == []
            assert result["data"]["counts"]["skipped"] == 1
            print(f"故事层：{story} → {new_story}；折叠状态跟随新编号。")
            print("已读进度：", result["data"]["issues"][0]["code"], "；新项目从未读开始。")
            print("业务提交成功，逐项结果：", result["data"]["status"], result["data"]["counts"])

            undone = undo_operation(target, result["operation_id"])
            assert undone["ok"], undone
            assert len(read_record(target, "layer", project_id=destination)) == 1
            assert read_record(target, "layer_state", project_id=destination) == []
            assert read_record(source, "read_state", project_id=project, id=note)["reads"] == {"reader": note}
            print("复制整批已撤销；目标原有层及源项目数据仍保留。")


if __name__ == "__main__":
    main()

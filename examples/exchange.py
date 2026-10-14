"""模板、导出编辑、复制及撤销；文件和数据库都在临时目录。"""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.support.api import initialize_database, open_database, read_record
from layerweave.tool.builtin.usage.exchange import export_project, import_project, template_help, save_document, load_document
from layerweave.tool.builtin.usage.undo.service import undo_operation


def main():
    with TemporaryDirectory(prefix="layerweave-exchange-") as folder:
        root = Path(folder)
        database = initialize_database(root / "demo.sqlite3")
        with closing(open_database(database)) as connection:
            template = template_help("storyboard")["items"][0]["document"]
            created = import_project(connection, template, new_project=True)
            assert created["ok"], created
            project_id = created["data"]["project_id"]
            document = export_project(connection, project_id, include_baseline=True)
            node = document["items"][0]["children"][0]
            original_id = node["id"]
            node["data"]["information"]["text"] = "修改后的开场说明"
            path = save_document(document, root / "edited.json")
            edited = import_project(connection, load_document(path))
            assert edited["ok"], edited
            assert read_record(connection, "object", project_id=project_id, id=original_id)["information"]["text"] == "修改后的开场说明"
            print("编辑后保留编号：", original_id, edited["data"]["counts"])
            copied = import_project(connection, export_project(connection, project_id, op="add"))
            assert copied["ok"], copied
            print("复制的新项目：", copied["data"]["project_id"], copied["data"]["counts"])
            assert undo_operation(connection, copied["operation_id"])["ok"]
            print("复制整批已撤销；源项目仍保留。")


if __name__ == "__main__":
    main()

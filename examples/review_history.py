"""python examples/review_history.py：内存中的复查、历史、撤销与重做。"""

from contextlib import closing

from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.support.api import open_database
from layerweave.tool.builtin.usage.records.save import save_layer, save_object
from layerweave.tool.builtin.usage.validation.recheck import recheck
from layerweave.tool.builtin.usage.history.service import read_history
from layerweave.tool.builtin.usage.undo.service import undo_operation
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.tool.builtin.usage.history.cli import format_history
from layerweave.tool.builtin.usage.validation.cli import format_recheck
from layerweave.tool.builtin.usage.undo.cli import format_undo


def create_example():
    with closing(open_database(":memory:")) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        project_id = dispatch(connection, {"action": "create", "kind": "project", "data": {"name": "历史示例"}})["id"]
        layer_id = save_layer(connection, project_id, {"config_ref": "layers/text.toml", "name": "剧情"})["data"]["id"]
        obj = {"config_ref": "objects/text.toml", "layer": layer_id, "information": {"text": "第一稿"}}
        save_object(connection, project_id, obj)
        obj["information"]["text"] = "第二稿"
        changed = save_object(connection, project_id, obj)
        checks = recheck(connection, project_id, layer_ids=[layer_id])
        history = read_history(connection, project_id, kind="object", id=obj["id"])
        undone = undo_operation(connection, changed["operation_id"])
        assert undone["ok"], undone
        redone = undo_operation(connection, undone["operation_id"])
        assert redone["ok"], redone
        return {"checks": checks, "history": history, "undone": undone, "redone": redone}


if __name__ == "__main__":
    example = create_example()
    print(format_recheck(example["checks"]))
    print(format_history(example["history"]))
    print(format_undo(example["undone"]))
    print(format_undo(example["redone"]))

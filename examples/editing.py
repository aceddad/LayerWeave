"""python -X utf8 examples/editing.py：分割、范围平移、插空档与跨项目剪切的内存示例。"""

from contextlib import closing

from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.tool.builtin.usage.query.free_ranges import find_gaps
from layerweave.tool.builtin.usage.editing.timeline import insert_gap, shift_objects, split_object
from layerweave.support.api import open_database
from layerweave.tool.builtin.usage.records.save import save_layer_with_checks, save_object_with_checks
from layerweave.tool.builtin.usage.editing.tree_service import transfer_objects, transfer_subtree
from layerweave.tool.builtin.usage.undo.service import undo_operation
from layerweave.tool.builtin.usage.query.free_ranges import format_gaps
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.tool.builtin.usage.editing.gaps import format_gap
from layerweave.tool.builtin.usage.editing.split import format_split
from layerweave.tool.builtin.usage.editing.transfer import format_transfer
from layerweave.tool.builtin.usage.undo.cli import format_undo


def create_example():
    with closing(open_database(":memory:")) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        source = dispatch(connection, {"action": "create", "kind": "project", "data": {"name": "原项目"}})["id"]
        destination = dispatch(connection, {"action": "create", "kind": "project", "data": {"name": "目标项目"}})["id"]
        layer = save_layer_with_checks(connection, source, {"config_ref": "layers/text.toml", "name": "歌词"})["data"]["id"]
        obj = save_object_with_checks(connection, source, {"config_ref": "objects/text.toml", "layer": layer, "begin": 10, "end": 20,
                                             "information": {"text": "原文"}})["data"]["id"]
        split = split_object(connection, source, obj, first_information={"text": "第一段"},
                             cuts=[{"at": 14, "information": {"text": "第二段"}}])
        assert split["ok"], split
        shift = shift_objects(connection, source, layer_ids=[layer], from_position=14, offset=1)
        assert shift["ok"], shift
        gap = insert_gap(connection, source, layer_id=layer, at=12, length=2,
                         crossing_actions=[{"object_id": obj, "action": "split", "first_information": {"text": "第一段前半"},
                                          "second_information": {"text": "第一段后半"}}])
        assert gap["ok"], gap
        other = save_layer_with_checks(connection, destination, {"config_ref": "layers/text.toml", "name": "引用方"})["data"]["id"]
        dispatch(connection, {"action": "create", "kind": "bind", "data": {
            "source_kind": "layer", "source_project_id": destination, "source_id": other,
            "target_kind": "object", "target_project_id": source, "target_id": obj}})
        cut = transfer_subtree(connection, source, layer, destination, mode="cut")
        assert cut["ok"], cut
        restored = undo_operation(connection, cut["operation_id"])
        assert restored["ok"], restored
        free = find_gaps(connection, source, layer, begin=0, end=30, min_length=1)
        copied = transfer_objects(connection, source, [obj], destination, other, mode="copy")
        assert copied["ok"], copied
        return {"split": split, "shift": shift, "gap": gap, "cut": cut, "restored": restored,
                "free": free, "copied_objects": copied}


if __name__ == "__main__":
    result = create_example()
    print(format_split(result["split"]))
    print(format_gap(result["gap"]))
    print(format_transfer(result["cut"]))
    print(format_undo(result["restored"]))
    print(format_gaps(result["free"]))
    print(format_transfer(result["copied_objects"]))

"""python examples/subtrees.py：内存中的歌词子树复制、删除与恢复。"""

from contextlib import closing

from layerweave.tool.builtin.usage.editing.tree_service import copy_subtree, delete_subtree
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.support.api import open_database
from layerweave.tool.builtin.usage.records.save import save_layer_with_checks, save_object_with_checks
from layerweave.tool.builtin.usage.undo.service import undo_operation
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.tool.builtin.usage.editing.subtrees import format_subtree
from layerweave.tool.builtin.usage.undo.cli import format_undo


def create_example():
    with closing(open_database(":memory:")) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        project = dispatch(connection, {"action": "create", "kind": "project", "data": {"name": "歌词版本"}})["id"]
        # 所有编号均来自实际保存结果。
        return _create(connection, project)


def _create(connection, project):
    lyrics = save_layer_with_checks(connection, project, {"config_ref": "layers/text.toml", "name": "歌词原版"})["data"]["id"]
    markers = save_layer_with_checks(connection, project, {"config_ref": "layers/text.toml", "father": lyrics, "name": "段落标记"})["data"]["id"]
    audio = save_layer_with_checks(connection, project, {"config_ref": "layers/audio.toml", "name": "伴奏"})["data"]["id"]
    line = save_object_with_checks(connection, project, {"config_ref": "objects/text.toml", "layer": lyrics,
                                           "information": {"text": "第一句歌词"}, "end": 4})["data"]["id"]
    marker = save_object_with_checks(connection, project, {"config_ref": "objects/title.toml", "layer": markers,
                                             "information": {"text": "主歌"}})["data"]["id"]
    links = [("object", line, "object", marker), ("object", line, "layer", audio), ("layer", audio, "object", line)]
    dispatch(connection, [{"action": "create", "kind": "bind", "data": {
        "source_kind": source_kind, "source_project_id": project, "source_id": source,
        "target_kind": target_kind, "target_project_id": project, "target_id": target}}
        for source_kind, source, target_kind, target in links])
    copied = copy_subtree(connection, project, lyrics, name="歌词修改版")
    assert copied["ok"], copied
    deleted = delete_subtree(connection, project, lyrics)
    assert deleted["ok"], deleted
    restored = undo_operation(connection, deleted["operation_id"])
    assert restored["ok"], restored
    return {"copied": copied, "deleted": deleted, "restored": restored}


if __name__ == "__main__":
    example = create_example()
    print(format_subtree(example["copied"]))
    print(format_subtree(example["deleted"]))
    print(format_undo(example["restored"]))

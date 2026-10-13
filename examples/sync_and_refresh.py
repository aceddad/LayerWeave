"""稳定键同步、保留引用、增量读取和关联展开；只使用内存数据库。"""
from contextlib import closing

from layerweave.support.api import (open_database, transaction, read_snapshot, read_project_details,
                                   change_cursor, read_changes, read_record)
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.tool.builtin.usage.editing.upsert import upsert_objects
from layerweave.tool.builtin.usage.query.walk import walk_relations
from layerweave.tool.builtin.usage.undo.service import undo_operation


def main():
    with closing(open_database(":memory:")) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        with transaction(connection) as write:
            project_id = write.create("project", {"name":"文档同步示例"})["id"]
            layer_id = write.create("layer", {"name":"分镜", "type":"text", "config_ref":"layers/text.toml"}, project_id=project_id)["id"]
        first = upsert_objects(connection, project_id, layer_id, [
            {"name":"开场", "config_ref":"objects/text.toml", "information":{"source_key":"scene_017", "text":"旧正文"}}
        ], match_by="information.source_key")
        assert first["ok"], first
        object_id = first["data"]["items"][0]["record"]["id"]
        with transaction(connection) as write:
            bind = write.create("bind", {"source_kind":"layer", "source_project_id":project_id, "source_id":layer_id,
                                         "target_kind":"object", "target_project_id":project_id, "target_id":object_id})
        with read_snapshot(connection):
            initial = read_project_details(connection, project_id)
            cursor = change_cursor(connection)
        changed = upsert_objects(connection, project_id, layer_id, [
            {"name":"序幕", "information":{"source_key":"scene_017", "text":"新正文"}}
        ], match_by="information.source_key")
        assert changed["ok"] and changed["data"]["items"][0]["record"]["id"] == object_id
        assert read_record(connection,"bind",id=bind["id"]) == bind
        page = read_changes(connection,after=cursor,limit=1)
        assert page["changes"][0]["before_data"]["name"] == "开场"
        assert page["changes"][0]["after_data"]["name"] == "序幕"
        print("更新保留对象编号：", object_id, "；原快照对象数：", sum(len(layer["objects"]) for layer in initial["layers"]))
        print("增量：", [(row["action"],row["kind"],row["target_id"]) for row in page["changes"]])
        graph = walk_relations(connection,project_id,"layer",layer_id,max_depth=1)
        print("关联阅读：", [(node["kind"],node["record"]["name"]) for node in graph["nodes"]])
        assert undo_operation(connection,changed["operation_id"])["ok"]
        restored = read_changes(connection,after=page["next_cursor"])
        assert restored["changes"][0]["after_data"]["name"] == "开场"
        print("撤销同样出现在增量日志中。")


if __name__ == "__main__":
    main()

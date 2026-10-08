"""运行：python -X utf8 -B -m examples.crud。只使用内存数据库。"""

from contextlib import closing
import json
from functools import partial

from runtime.dispatch import dispatch
from runtime.storage.database import SCHEMA_PATH, open_database
from runtime.storage import crud
from runtime.validation.runner import validate


def create_example():
    with closing(open_database(":memory:")) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        project = dispatch(connection, {
            "action": "create", "kind": "project", "data": {"name": "CRUD 示例"},
        })
        project_id = project["id"]
        layer = dispatch(connection, {
            "action": "create", "kind": "layer", "project_id": project_id,
            "data": {"name": "主线", "config_ref": "layers/text.toml",
                     "axis": {"unit": "秒", "precision": 0.001}},
        })

        batch = dispatch(connection, [
            {"action": "create", "kind": "object", "project_id": project_id,
             "data": {"config_ref": "objects/text.toml", "layer": layer["id"],
                      "name": name, "information": {"text": text}}}
            for name, text in (("开场", "角色走进画面。"), ("结尾", "角色离开画面。"))
        ])
        object_id = batch["results"][0]["id"]

        # 此处故意写入数字，展示“操作成功”与“发现约定问题”可以同时成立。
        updated = dispatch(connection, {
            "action": "update", "kind": "object", "project_id": project_id,
            "id": object_id, "data": {"information": {"text": 123}},
        })
        # 显式复查直接复用内置规则，不伪造 update、不增加日志。
        rechecked = validate(
            [{"kind": "layer", "project_id": project_id, "id": layer["id"]}],
            partial(crud.read, connection),
        )
        selected = dispatch(connection, {
            "action": "read", "kind": "object", "project_id": project_id,
            "filters": {"layer": layer["id"]},
        })
        deleted = dispatch(connection, {
            "action": "delete", "kind": "object", "project_id": project_id, "id": object_id,
        })
        history = dispatch(connection, {
            "action": "read", "kind": "change", "filters": {"operation_id": batch["operation_id"]},
        })
        return {
            "project": project["data"],
            "batch": batch,
            "update_with_issue": updated,
            "manual_recheck": rechecked,
            "read": selected,
            "delete": deleted,
            "batch_change_count": len(history["data"]),
        }


if __name__ == "__main__":
    print(json.dumps(create_example(), ensure_ascii=False, indent=2))

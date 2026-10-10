"""python -X utf8 -B examples/feedback.py：独立显示写入状态与逐条诊断。"""

from contextlib import closing

from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.support.api import format_feedback, open_database
from layerweave.support.storage.database import SCHEMA_PATH


def main():
    with closing(open_database(":memory:")) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        project_id = dispatch(connection, {"action": "create", "kind": "project", "data": {}})["id"]
        layer_id = dispatch(connection, {"action": "create", "kind": "layer", "project_id": project_id,
                                         "data": {"config_ref": "layers/text.toml"}})["id"]

        def create(**fields):
            return dispatch(connection, {"action": "create", "kind": "object", "project_id": project_id,
                "data": {"layer": layer_id, "config_ref": "objects/text.toml",
                         "information": {"text": "正文"}, **fields}})

        create()
        create(config_ref="objects/txt.toml")
        print(format_feedback(create()))
        print()
        print(format_feedback(create(start=1)))


if __name__ == "__main__":
    main()

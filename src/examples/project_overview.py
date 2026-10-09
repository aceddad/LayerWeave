"""python -X utf8 -B -m examples.project_overview；只使用内存数据库。"""

from contextlib import closing

from runtime.api import dispatch, open_database, save_layer
from runtime.storage.database import SCHEMA_PATH
from tools.usage.common.project_overview import format_overview, project_overview


def create_example():
    with closing(open_database(":memory:")) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        project_id = dispatch(connection, {
            "action": "create", "kind": "project", "data": {"name": "短片示例"},
        })["id"]
        main = save_layer(connection, project_id, {
            "config_ref": "layers/text.toml", "name": "主线",
            "objects": [{"config_ref": "objects/text.toml", "information": {"text": "开场"}},
                        {"config_ref": "objects/text.toml", "information": {"text": "结尾"}}],
        })["data"]
        save_layer(connection, project_id, {
            "config_ref": "layers/audio.toml", "name": "配音", "father": main["id"],
            "objects": [{"config_ref": "objects/audio.toml", "information": {"source": "voice.wav"}}],
        })
        save_layer(connection, project_id, {
            "config_ref": "layers/image.toml", "name": "参考图",
        })
        return project_overview(connection, project_id)


if __name__ == "__main__":
    print(format_overview(create_example()))

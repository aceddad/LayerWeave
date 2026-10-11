"""python -X utf8 -B examples/read_write.py：完整写入、关闭重开、装载修改、再次读取。"""

from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.models import Text, TextLayer
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.support.api import initialize_database, load_layer, open_database, read_layer
from layerweave.tool.builtin.usage.records.save import save_layer_with_checks


def _saved(result):
    if not result["ok"]:
        raise RuntimeError(result["error"])
    return result


def create_example():
    # 演示只使用自己的临时数据库，不向 output/ 的项目数据库写入内容。
    with TemporaryDirectory(prefix="layerweave-example-") as directory:
        database = initialize_database(Path(directory) / "example.sqlite3")
        with closing(open_database(database)) as connection:
            project = _saved(dispatch(connection, {
                "action": "create", "kind": "project", "data": {"name": "完整读写示例"},
            }))
            project_id = project["id"]
            layer = TextLayer(name="主线")
            _saved(save_layer_with_checks(connection, project_id, layer))
            text = Text(layer=layer.id, begin=0, end=3, information={"text": "初稿"})
            text.bind.append({"target_kind": "layer", "target_project_id": project_id,
                              "target_id": layer.id, "tips": "引用所属层的说明"})
            layer.objects.append(text)
            written = _saved(save_layer_with_checks(connection, project_id, layer))

        with closing(open_database(database)) as connection:
            loaded = load_layer(connection, project_id, layer.id)
            loaded.objects[0].information["text"] = "重新打开数据库后修改的正文"
            updated = _saved(save_layer_with_checks(connection, project_id, loaded))
            history = dispatch(connection, {
                "action": "read", "kind": "change", "filters": {"operation_id": updated["operation_id"]},
            })

        with closing(open_database(database)) as connection:
            record = read_layer(connection, project_id, layer.id)
        return {"model_types": [type(loaded).__name__, type(loaded.objects[0]).__name__],
                "write_checks": written["checks"], "update_checks": updated["checks"],
                "update_log_count": len(history["data"]), "reopened_record": record}


if __name__ == "__main__":
    print(json.dumps(create_example(), ensure_ascii=False, indent=2))

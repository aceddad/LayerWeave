"""视图工具登记的批注层：Python 类在 models.py；配置在核心的配置目录（configs/layers/note.toml、configs/objects/note.toml，
用 requires 写明依赖本工具包）。读写入口见上一级的 note.py。"""

LAYER_REF = "layers/note.toml"
OBJECT_REF = "objects/note.toml"
AXIS = {"unit": "条", "precision": 1}

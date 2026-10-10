"""视图工具自带的批注层：配置（layers/note.toml、objects/note.toml，和 configs 一样按层、对象分区）和类（models.py）。读写入口见上一级的 note.py。"""

# 从 configs/ 到本目录的相对路径：批注层、批注对象记录里的 config_ref
LAYER_REF = "../tool/builtin/view/notes/layers/note.toml"
OBJECT_REF = "../tool/builtin/view/notes/objects/note.toml"
AXIS = {"unit": "条", "precision": 1}

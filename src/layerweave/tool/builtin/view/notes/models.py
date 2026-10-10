"""批注层和批注对象的 Python 类：行为沿用文字层、文字对象；配置和约定在 configs/layers/note.toml、configs/objects/note.toml。"""
from layerweave.models.layers.text import TextLayer
from layerweave.models.objects.text import Text


class NoteLayer(TextLayer):
    """批注层：视图工具的批注容器，按顺序装批注。"""

    pass


class Note(Text):
    """一条批注：正文在 information.text，指向用关联表达。"""

    pass

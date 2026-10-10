"""在 src 目录运行：python -B examples/text.py。

示例直接使用 Python 类，尚不加载配置或执行配置中的检查。
"""

from layerweave.models.layers.text import TextLayer
from layerweave.models.objects.text import Text


def create_example():
    layer = TextLayer(
        id=1,
        name="主线说明",
        axis={"unit": "秒", "precision": 0.001},
        tips="记录作品各段的意图",
    )

    text = Text(
        id=2,
        name="开场说明",
        layer=layer.id,
        begin=0.0,
        end=5.0,
        information={"text": "这一段表现角色从犹豫到行动。"},
    )

    layer.objects.append(text)
    return layer.return_self()


if __name__ == "__main__":
    layer = create_example()
    print("Python 类：", type(layer).__name__)
    print("实例名字：", layer.name)
    print("层返回自身：", layer.return_self() is layer)
    for text in layer.objects:
        print("对象名字：", text.name)
        print("位置：", text.begin, "到", text.end)
        print("文本：", text.information["text"])
        print("对象返回自身：", text.return_self() is text)

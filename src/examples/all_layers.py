"""在 src 目录运行：python -X utf8 -B -m examples.all_layers。

展示六类封装的创建、装载与关联。资源地址仅作示意，不读取资源。
示例直接使用 Python 类，不加载配置或执行配置中的检查。
"""

from models import (
    TextLayer, Text,
    ImageLayer, Image,
    AudioLayer, Audio,
    MovieLayer, Movie,
    ModelLayer, Model,
    ActiveLayer, Active,
)


def create_example():
    root = TextLayer(
        id=1,
        name="主线说明",
        axis={"unit": "秒", "precision": 0.001},
        tips="下面各层共用这里的轴和文字说明",
    )
    root.objects.append(Text(
        id=2,
        name="开场说明",
        layer=root.id,
        begin=0.0,
        end=5.0,
        information={"text": "角色在音乐中向前走，背景逐渐展开。"},
    ))

    layers = [root]
    resources = [
        (ImageLayer, Image, "背景图片", "开场背景", "assets/background.png"),
        (AudioLayer, Audio, "背景音乐", "开场音乐", "assets/music.wav"),
        (MovieLayer, Movie, "预览结果", "开场片段", "assets/opening.mp4"),
        (ModelLayer, Model, "角色模型", "主角模型", "assets/character.glb"),
        (ActiveLayer, Active, "角色动作", "角色行走", "assets/walk.json"),
    ]

    for index, (layer_class, object_class, layer_name, object_name, source) in enumerate(resources):
        layer_id = 3 + index * 2
        layer = layer_class(id=layer_id, name=layer_name, father=root.id)
        obj = object_class(
            id=layer_id + 1,
            name=object_name,
            layer=layer.id,
            begin=0.0,
            end=5.0,
            information={"source": source},
        )
        layer.objects.append(obj)
        layers.append(layer)

    model = layers[-2].objects[0]
    action = layers[-1].objects[0]
    action.bind.append({"target_kind": "object", "target_project_id": 1,
                        "target_id": model.id, "tips": "作用于这个模型"})

    return [layer.return_self() for layer in layers]


if __name__ == "__main__":
    for layer in create_example():
        print(f"{layer.id} {type(layer).__name__}：{layer.name}")
        for obj in layer.objects:
            result = obj.return_self()
            print(f"  {result.id} {type(result).__name__}：{result.information}")
            if result.bind:
                print(f"  关联：{result.bind}")

# 用法一：嵌套层与时序

这是 LayerWeave 最初的组织思路：用父子层组织不同模块，在各层放入对象，再用对象的 begin/end 安排时序。文字、图片、视频、音频可以沿同一条轴配合。[返回开发指导](README.md)。

## 先组织层，再放入内容

以一段手书为例：

```text
项目
└─ 手书主线（文字层，root，轴：秒，精度 0.001）
   ├─ 画面（文字层）
   │  ├─ 插画（图片层）
   │  └─ 视频（视频层）
   ├─ 字幕（文字层）
   └─ 音乐（音频层）
```

“主线”“画面”等名称表达本项目的用途，复用已有层类型即可。文字控制层自身也能装载对象，例如记录某段的意图；子层用于分组具体内容。对象始终属于一个实际层。

层的父子关系负责组织和轴解释。对象的 begin/end 决定其位置，例如字幕 A 放在 [0,2)，字幕 B 放在 [2,4)，两句在 2 衔接。子层的位置数值不会因为嵌套而自动加上偏移，父层也不会自动裁剪子层对象。

## 建立一个最小模块

前提：connection 是已经初始化数据库的连接。示例创建一个新项目、上述层树和两条字幕；图片、视频与音乐层先保持空内容。所有编号使用写入入口的返回值。

```python
from layerweave.support.api import Loader, run_operation


def create_timeline(connection, name):
    loader = Loader()

    def work(write):
        project_id = write.create("project", {"name": name})["id"]

        def layer(name, config_ref, father=None, axis=None):
            return write.create("layer", {
                "name": name, "config_ref": config_ref,
                "type": loader.load(config_ref, "layer")["type"],
                "father": father, "axis": axis,
            }, project_id=project_id)["id"]

        root = layer("手书主线", "layers/text.toml",
                     axis={"unit": "秒", "precision": 0.001})
        visual = layer("画面", "layers/text.toml", father=root)
        layer("插画", "layers/image.toml", father=visual)
        layer("视频", "layers/movie.toml", father=visual)
        subtitles = layer("字幕", "layers/text.toml", father=root)
        layer("音乐", "layers/audio.toml", father=root)

        for begin, end, text in ((0, 2, "第一句"), (2, 4, "第二句")):
            write.create("object", {
                "config_ref": "objects/text.toml", "layer": subtitles,
                "begin": begin, "end": end, "information": {"text": text},
            }, project_id=project_id)
        return {"project_id": project_id, "root_id": root}

    return run_operation(connection, work)


result = create_timeline(connection, "时序示例")
```

支撑层将项目、层、对象和日志放进同一个事务。这个例子默认不接入内容检查，使用 operation.status 判断创建结果；需要检测时再按[API](../../src/layerweave/support/API.md#提交后的可选检查)选择提供者。

## 按模块和时段读取

下面沿用 create_timeline 创建成功后的 result：

```python
from layerweave.support.api import read_project_details

scope = result["data"]
details = read_project_details(
    connection, scope["project_id"], layer_id=scope["root_id"],
    begin=1, end=3,
)
```

它读取该 root 及全部子层，只选择与 [1,3) 相交的对象。两句字幕都会返回，并保留原来的完整起止位置；没有命中对象的层也会保留。需要树形文字或精简输出时，使用[详细展开工具](../../src/layerweave/tool/builtin/usage/GUIDE.md#项目详细展开)。

## 延伸这个思路

- 按场景继续增加子层，或将资源库、另一段制作流程放成独立 root；读取时选择对应模块。
- 默认在模块根层声明轴，子层沿父链解释位置。不同模块可以使用秒、帧或其他单位，查询保持原数值；轴规则见[配置说明](../../src/layerweave/support/configuration/README.md)。
- 使用[常用编辑](../../src/layerweave/tool/builtin/usage/GUIDE.md#常用编辑)接续、排列、对齐对象；复杂的分割、插空档和搬移见[范围编辑](../../src/layerweave/tool/builtin/usage/EDITING.md)。
- 用 bind 表达引用和作用关系，例如动作指向模型、片段指向素材；具体怎样解释由使用工具决定。

这些数据描述素材、内容、关系与时序，渲染器或视图工具据此组织实际画面。围绕作品的批注与待办，也可以使用[有序列表与隐藏信息管理](02-ordered-metadata.md)，与时序模块并存。

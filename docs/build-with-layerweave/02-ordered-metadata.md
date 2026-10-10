# 用法二：有序列表与隐藏信息管理

把一层的对象看作一组有序条目，可以组织批注、待办、审阅意见或素材选择理由。它们是真实保存的项目数据，视图可以把它们放进管理面板，而不画进作品。[返回开发指导](README.md)。

## 用序号组织条目

例如，一组批注可以直接放在一个独立的文字 root 中，每个批注是一个文字对象：

```text
项目
├─ 成片编排（root，轴：秒）
└─ 批注列表（root，轴：序号）
   ├─ 第 1 条批注（对象，位置 1）── bind → 某个镜头对象
   └─ 第 2 条批注（对象，位置 2）── bind → 某个字幕对象
```

用 begin=end=序号 表示条目的位置，序号轴可使用 precision=1。序号与数据库 id 分开：重排时修改位置，编号保持不变；同一位置的条目按编号稳定排序。需要分组时再增加子层，简单列表直接使用一层即可。

查询时指定这个 root 或具体层，按实际需要读取条目。同一项目中的秒轴和序号轴各自解释数值；范围查询不会换算单位，所以查成片某几秒时选择成片模块，查批注时选择批注模块。

“隐藏”描述工具的展示方式。普通读取和项目展开仍能取得这些记录；是否在画面或管理面板显示，由视图决定。

## 示例：给已有内容加一条批注

这是批注数据的接入示例。完整批注面板、选中标记和显示状态由视图工具实现。

前提：connection 已打开并初始化数据库，项目与批注文字层已存在；target 是已有层或对象的引用，包含 kind、project_id、id。批注层可作为独立 root，axis 使用 {"unit": "序号", "precision": 1}。order 由调用工具决定。

```python
from layerweave.support.api import run_operation


def add_annotation(connection, project_id, annotation_layer_id, target, text, order):
    def work(write):
        note = write.create("object", {
            "config_ref": "objects/text.toml",
            "layer": annotation_layer_id,
            "begin": order,
            "end": order,
            "information": {"text": text, "resolved": False},
        }, project_id=project_id)
        write.create("bind", {
            "source_kind": "object", "source_project_id": project_id,
            "source_id": note["id"],
            "target_kind": target["kind"], "target_project_id": target["project_id"],
            "target_id": target["id"], "tips": "批注指向的内容",
        })
        return note

    return run_operation(connection, work)
```

文字对象的 information 当前允许扩展键，因此示例可以同时保存 text 和 resolved。它们随数据保存，工具自行解释 resolved；没有因此给 Python 类或数据库新增列。批注对象和关联共用一次事务与操作编号，目标内容及其所在层无需整份读出或重存。

示例使用基础支撑，默认不执行内容检查；返回中的 operation 表示写入结果，checks 表示检查情况。产品需要内容检测时按[可选检查](../../src/layerweave/support/API.md#提交后的可选检查)接入；工具也可以提供自己的检查器。

## 只修改自己关心的字段

更新时提供需要修改的顶层字段即可。例如修改 tips 时，只提交 {"tips": "新的说明"}，其他字段保留。

information 和 axis 是整体替换的 JSON 字段。要修改其中一个键，在同一写会话内读取最新值并合并。下面沿用上例已创建的批注，note_id 是返回 note 的编号：

```python
def resolve_note(write):
    note = write.read("object", project_id=project_id, id=note_id)
    return write.update("object", note_id, {
        "information": {**note["information"], "resolved": True},
    }, project_id=project_id)


result = run_operation(connection, resolve_note)
```

工具负责自己的业务修改；支撑负责身份、归属存在、父链无环、编号、事务和日志。复用这一入口，就能省去重复的存储与结构检查代码。关系、时间和内容的完整语义见[架构说明](../architecture.md)，需要时再查。

## 给工具增加配置词条

如果批注层需要共享自己的用途说明和视图偏好，可以新增一个派生类。示意放在你的 my_notes/models.py 中：

```python
from layerweave.models import TextLayer


class AnnotationLayer(TextLayer):
    pass
```

在配置根目录的 layers/annotation.toml 中提供对应声明：

```toml
[layer]
type = "annotation"
class = "my_notes.models:AnnotationLayer"
extends = "text.toml"
name = "批注层"
when = "组织批注及其指向关系"

[layer.view]
role = "annotation"
default_visible = false
```

这里的 view、role、default_visible 是示例工具约定的词条。配置读取器保留它们，开发版 config_help 可展示完整定义；视图工具自行读取并决定行为。仅写入这些词条不会自动创建界面、隐藏对象或启用检测。

每份新封装仍有自己对应的 Python 类和 TOML。这个例子只新增层封装，内容对象继续复用 Text。自定义配置根目录保留 layers/objects 分区，并包含所需父配置；让类所在的 Python 包可导入，在 save/load 等接口传入 config_root 即可。具体文件组织见[配置说明](../../src/layerweave/support/configuration/README.md)。

已有 fields、rules 等区域遵循原有合并规则。自定义段当前会继承；子配置再次声明同名自定义段时，整段替换。工具设计自己的词条时，把含义和默认处理写在本工具说明中即可。

同一类的实例内容放在记录字段或 information 中；共用的行为偏好放在 TOML；临时的窗口选择、缓存等可以留在工具自身。visibility 继续表示是否允许显隐控制，示例的 default_visible 则由视图解释初始展示偏好。

同一项目可以同时采用[嵌套层与时序](01-timeline.md)和本篇的管理列表；工具按任务选择要读取的 root，再通过 bind 找到相关内容。

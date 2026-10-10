# 用 LayerWeave 开发自己的工具（给 AI）

你可以把 LayerWeave 当作组织数据、保存关系和记录修改的底座，按需接入自己的工具。工具只处理当前任务关心的数据；它的界面、算法、参数、缓存和临时结果，由工具自己设计。

本文帮助你选择接入方式。安装、源码位置与贡献流程见[开发指南](developer-conventions.md)，具体参数见[基础支撑 API](../src/layerweave/support/API.md)。

## 可以自由决定什么

| 你要组织的内容 | 可以怎样使用现有结构 |
|---|---|
| 批注、待办、审阅记录 | 用层组织条目，用对象保存文字和处理状态，用 bind 指向相关内容 |
| 有序列表 | 把轴解释为序号，用对象位置表达顺序；同一位置时按编号稳定排序 |
| 制作过程信息 | 建立独立 root，按需查询；由工具决定是否展示在画面或面板中 |
| 新的业务内容 | 在对象 information 中组织 JSON 内容，按需要提供自己的封装约定 |
| 工具行为偏好 | 在对应 TOML 中增加自定义段，由消费它的工具解释 |
| 缓存、导出文件、临时计算结果 | 放在工具自己的工作目录；需要进入项目的内容再通过接口保存 |

层可以用于时间线，也可以用于资料、列表和内部管理。项目可以有多个 root，工具可以只读取其中一个模块或一段范围。创建新功能时，先复用已经够用的类和字段；有独立的类型约定时，再增加封装。

## 从最小接入开始

| 当前需要 | 入口 |
|---|---|
| 读取普通记录、筛选对象、取得直接关联 | support.api 的 read_record、query_objects、read_bindings |
| 只修改几个字段，或一次组合多个修改 | run_operation 或 transaction 中的 write 原语 |
| 使用 Python 派生实例，或保存整层与装载对象 | load_layer/load_object、save_layer/save_object |
| 使用现成的查询展示、编辑、历史或撤销 | 对应的[内部工具包](../src/layerweave/tool/builtin/README.md) |

可以直接在自己的 Python 工程里导入公开接口。借用写会话不要求使用 CDUR 请求格式，也不要求构造完整的 Layer/Object 实例。读取普通记录时，配置文件和类不必可用；需要还原派生实例时再用 load。

“挂载工具”在这里指工具使用这套数据与配置能力。普通函数就能完成接入；需要进入命令 help 时，再按[命令声明](../src/layerweave/tool/builtin/shared/help/COMMANDS.md)提供 COMMANDS。层配置里的 tools 是供 AI 阅读的技能路由，执行方式由调用方选择。

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

示例使用基础支撑，默认不执行内容检查；返回中的 operation 表示写入结果，checks 表示检查情况。产品需要内容检测时按[可选检查](../src/layerweave/support/API.md#提交后的可选检查)接入；工具也可以提供自己的检查器。

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

工具负责自己的业务修改；支撑负责身份、归属存在、父链无环、编号、事务和日志。复用这一入口，就能省去重复的存储与结构检查代码。关系、时间和内容的完整语义见[架构说明](architecture.md)，需要时再查。

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

每份新封装仍有自己对应的 Python 类和 TOML。这个例子只新增层封装，内容对象继续复用 Text。自定义配置根目录保留 layers/objects 分区，并包含所需父配置；让类所在的 Python 包可导入，在 save/load 等接口传入 config_root 即可。具体文件组织见[配置说明](../src/layerweave/support/configuration/README.md)。

已有 fields、rules 等区域遵循原有合并规则。自定义段当前会继承；子配置再次声明同名自定义段时，整段替换。工具设计自己的词条时，把含义和默认处理写在本工具说明中即可。

同一类的实例内容放在记录字段或 information 中；共用的行为偏好放在 TOML；临时的窗口选择、缓存等可以留在工具自身。visibility 继续表示是否允许显隐控制，示例的 default_visible 则由视图解释初始展示偏好。

## 把工具放在哪里

- 在外部项目开发：导入 layerweave 的公开接口，代码、依赖与工作目录由你的项目管理。
- 作为 LayerWeave 内部工具提供：在 tool/builtin 对应分类放置完整包，通用入口复用 support，包内保留业务辅助实现。
- 作为 AI 按需阅读的外置技能提供：按[技能导引](../src/layerweave/tool/README.md)组织 SKILL.md、脚本与资源。

先完成最小的读取或写入流程，再按真实需求增加封装、配置和展示方式。安装所有工具、建立完整场景模板、接入视图或 MCP，都不是使用数据底座的前置步骤。

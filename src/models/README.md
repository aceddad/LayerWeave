# Python 模型

这里保存层和对象的基础类与派生类。[返回项目首页](../../README.md)，配置见[configs](../../configs/README.md)。

| 位置 | 职责 |
|---|---|
| [layers/base.py](layers/base.py) | Layer 的字段、对象装载容器和 return_self |
| [objects/base.py](objects/base.py) | Object 的字段、所属层、位置、information 和 return_self |
| layers/、objects/ 的其他模块 | 具体内容类型的派生类 |

模型保存数据，return_self 返回同一个实例。构造、赋值和返回自身不负责数据库查询或语义检查；完整读写通过[公共 API](../support/API.md)完成。

## 当前封装

| 类型 | 层类 | 对象类 | 内容入口 |
|---|---|---|---|
| text | TextLayer | Text | information.text |
| image | ImageLayer | Image | information.source |
| audio | AudioLayer | Audio | information.source |
| movie | MovieLayer | Movie | information.source |
| model | ModelLayer | Model | information.source / data |
| active | ActiveLayer | Active | information.source / data |

[Title](objects/title.py) 是继承 Text 的派生示例，对应[标题 TOML](../../configs/objects/title.toml)，继续装入文字层。用途名称如歌词、背景等可以通过实例 name 区分。

## 扩充入口

新增封装同时添加类与 TOML，类和配置的对应约定由[配置模块](../support/configuration/README.md)维护。参考 [Title 往返示例](../examples/title.py)或[文字示例](../examples/text.py)。

可直接从具体模块导入新类；若需要统一的 `from models import ...` 入口，同步 models、layers、objects 对应的 __init__.py 导出。统一入口继续按需加载，模型字段不自动映射成新数据库列。

# 配置读取与继承

这里维护继承、合并与类绑定的具体规则。[返回核心模块](../README.md)，配置文件位置见 [configs](../../../configs/README.md)。

查看支持能力使用 [配置 help](HELP.md)，四种查询均不需要数据库。底层入口为 [Loader](loader.py)。每次检测使用一个 Loader，在该次调用内缓存；下次调用重新读取文件，因此配置修改后可直接主动复查。只读取 TOML，不导入 class 或实例化 Python 对象。

配置名称和直接声明的 Python 类共用按种类构建的索引；同一 Loader 内每个种类只扫描一次。模型保存通过 class_config 查找实例实际类的配置，不再为每个实例重新扫描目录。索引和继承共用已读取的 TOML 内容；同一文件在一次 Loader 内只读取一次。

```python
from runtime.configuration.loader import Loader
config = Loader().load("objects/text.toml", "object")
```

路径默认相对于项目 configs/；extends 相对于当前配置文件。子目录可继续细分。层的 objects 按 objects/ 下的配置 type 唯一定位，有重名或缺失会报告，不猜测。

## 合并约定

| 配置内容 | 继承行为 |
|---|---|
| fields / information 中的类型等约定 | 已有显式声明保持，允许新增字段/属性；note/default 是说明，可更新 |
| 字段 optional | 已有字段允许 true→false 收紧，禁止 false→true 放宽，包括父字段默认的 false；新增字段自行声明 |
| rules | 固定规则可重复、可新增，不能改写父值；重复规则只执行一次 |
| constraint / display | 显式值成为固定约定，后代不能改成其他值 |
| defaults.constraint / defaults.display | 尚未明确取值时使用的默认值，不覆盖显式约定 |
| options | 明确可调整的选项，目前为 layer.axis_only_on_root，默认 true |
| objects | 保留父层要求，或收窄为它接受的对象类型的派生类型 |
| type / class | 每份配置必须直接声明自己的类型标识与类绑定；不从父配置继承。一个类只绑定一份配置 |
| name / version / when / note / example | 封装自身的说明与示例，可继承或自行声明 |
| object.open | 已有父约定保持；当前基础对象为 true |

例如从 layers/base.toml 新开一个不允许重叠的层：

```toml
[layer]
type = "track"
class = "models.layers.track:TrackLayer"
extends = "base.toml"
objects = "text"

[layer.constraint]
overlap = false
```

同时新增 `src/models/layers/track.py`，定义 `class TrackLayer(Layer)`；没有新行为可以使用 pass。配置继承负责约定，Python 继承负责行为，不能只新增配置却复用父类绑定。[Title](../../models/objects/title.py) 与 [title.toml](../../../configs/objects/title.toml) 是现成的派生示例。

基础配置提供 overlap=true 的默认值，因此 track 可以选择 false；track 的派生配置不能再改成 true。现有 text 层已显式声明 overlap=true，需要不同约定时从 base 新开封装。

子层允许独立轴是明确的可调选项：

```toml
[layer.options]
axis_only_on_root = false
```

根层始终不必填写轴。没有默认单位、坐标换算或资源读取。

字段声明 `optional=true` 表示允许缺省，是字段约定，不是检测开关。检查仍执行：缺省符合约定，已填值仍检查类型。模型/动作的 source/data 均这样声明，派生封装自然继承。比如 `data = { type="dict", optional=true }` 允许省略 data，但不允许传入字符串或 None。

未声明 optional 的字段在完成继承后按 false 解释，缺失产生 missing_field，不拦截、不自动填值。继承字段依据父配置有效值判断：允许 true→false 收紧，禁止 false→true 放宽，包括父字段未显式填写时的默认 false。子配置未写则继承，新增字段可自行声明。仅接受 TOML 布尔值。比如从 Model 派生 FileModel，可只声明 `source={optional=false}`，继承 str 类型，同时要求资源地址；data 仍继承可选。

汇报等级独立放在 [diagnostics.toml](../../../configs/logging/diagnostics.toml)，未配置时默认 warn。路径覆盖只作用于指定封装、不继承；none 隐藏已经产生的问题，optional 则使合法缺省不产生问题。类型错误另行控制，见 [汇报配置说明](../validation/DIAGNOSTICS.md)。open=true 允许额外键；疑似笔误仍可提示，包括指向可选字段的 src→source。空字符串/空字典是已填写。类型支持 str、int、float、dict、list、bool、None，以及用竖线组合的联合类型。float 接受整数坐标；bool 不作为数值类型。未实现的显式类型或规则报告未检查，普通说明字段不因未知而报错。

内部有效配置含 _ref、_lineage 和 _contracts，分别记录配置路径、继承链与固定约定，用于兼容判断和合并。读取失败抛出 ConfigError，由检测器逐目标转为诊断，其他目标继续。缺少明确 class、同一类重复绑定多份配置均为配置错误；无关的损坏配置不会阻止有效目标读取。type 字符串以 TOML 为唯一来源，Layer 类不保存它。配置读取器不执行 class 导入；需要还原实例时，由 storage/models.py 按需导入配置指定的类。

Loader.refs(kind) 发现包括坏文件在内的配置路径，source(ref) 保留原文，find_configs(name, kind) 查找唯一名称的候选，accepts_object(layer_config, object_config) 提供统一兼容判断。Help 的查询整理在 catalog.py；这些方法与既有解析过程共享调用内缓存。

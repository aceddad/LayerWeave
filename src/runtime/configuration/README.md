# 配置读取与继承

入口为 [Loader](loader.py)。每次检测使用一个 Loader，在该次调用内缓存；下次调用重新读取文件，因此配置修改后可直接主动复查。只读取 TOML，不导入 class 或实例化 Python 对象。

配置名称和直接声明的 Python 类共用按种类构建的索引；同一 Loader 内每个种类只扫描一次。模型保存通过 class_config 查找新实例的配置，不再为每个实例重新扫描目录。

```python
from runtime.configuration.loader import Loader
config = Loader().load("objects/text.toml", "object")
```

路径默认相对于项目 configs/；extends 相对于当前配置文件。子目录可继续细分。层的 objects 按 objects/ 下的配置 type 唯一定位，有重名或缺失会报告，不猜测。

## 合并约定

| 配置内容 | 继承行为 |
|---|---|
| fields / information 中的类型等约定 | 已有声明保持，允许新增字段；note/default 是说明，可更新 |
| rules | 固定规则可重复、可新增，不能改写父值；重复规则只执行一次 |
| constraint / display | 显式值成为固定约定，后代不能改成其他值 |
| defaults.constraint / defaults.display | 尚未明确取值时使用的默认值，不覆盖显式约定 |
| options | 明确可调整的选项，目前为 layer.axis_only_on_root，默认 true |
| objects | 保留父层要求，或收窄为它接受的对象类型的派生类型 |
| type / class / name / version / when / note / example | 封装自身的标识、说明与示例，可自行声明 |
| object.open | 已有父约定保持；当前基础对象为 true |

例如从 layers/base.toml 新开一个不允许重叠的层：

```toml
[layer]
type = "track"
extends = "base.toml"
objects = "text"

[layer.constraint]
overlap = false
```

基础配置提供 overlap=true 的默认值，因此 track 可以选择 false；track 的派生配置不能再改成 true。现有 text 层已显式声明 overlap=true，需要不同约定时从 base 新开封装。

子层允许独立轴是明确的可调选项：

```toml
[layer.options]
axis_only_on_root = false
```

根层始终不必填写轴。没有默认单位、坐标换算或资源读取。

配置声明过的字段没有填写时逐条报告 warn，不拦截、不自动填值。text/source/data 等仍是可填字段，缺少不变成保存失败；已填写的内容按类型检查，空字符串是已填写。open=true 允许额外键，但不会抑制声明字段缺失的提醒。类型支持 str、int、float、dict、list、bool、None，以及用竖线组合的联合类型。float 接受整数坐标；bool 不作为数值类型。未实现的显式类型或规则报告未检查，普通说明字段不因未知而报错。

内部有效配置含 _ref、_lineage 和 _contracts，分别记录配置路径、继承链与固定约定，用于兼容判断和合并。读取失败抛出 ConfigError，由检测器逐目标转为诊断，其他目标继续。配置读取器不执行 class 导入；需要还原实例时，由 storage/models.py 按需导入配置指定的类。

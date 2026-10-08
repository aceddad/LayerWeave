# 配置读取与继承

入口为 [Loader](loader.py)。每次检测使用一个 Loader，在该次调用内缓存；下次调用重新读取文件，因此配置修改后可直接主动复查。只读取 TOML，不导入 class 或实例化 Python 对象。

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

对象缺少 text/source/data 不自动报必填问题；目前只检查已经提供的字段类型。类型支持 str、int、float、dict、list、bool、None，以及用竖线组合的联合类型。float 接受整数坐标；bool 不作为数值类型。未实现的显式类型或规则报告未检查，普通说明字段不因未知而报错。

内部有效配置含 _ref、_lineage 和 _contracts，分别记录配置路径、继承链与固定约定，用于兼容判断和合并。读取失败抛出 ConfigError，由检测器逐目标转为诊断，其他目标继续。配置中的 class 目前只记录用途；Python 类导入与恢复由未来存储适配负责。

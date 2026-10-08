# 模块化检测（2026-10-09）

已实现内置规则，默认接入 dispatch 与 JSON CLI。底层类仍只有数据和 return_self，不在构造后、属性赋值或普通读取时自动检查。SQL 主键、外键、NOT NULL 在写入时生效；语义检测在数据与日志提交后运行，不撤销数据。

## 模块与触发位置

| 模块 | 责任 |
|---|---|
| [channel.py](channel.py) | 区分操作结果与检测反馈；兼容外部 checker |
| [runner.py](runner.py) | 合并批次变化、查询最终记录、选择目标、逐项执行与去重 |
| [registry.py](registry.py) | 规则名、函数路径、触发字段与检查范围 |
| [rules/fields.py](rules/fields.py) | 共用类型判断与已声明字段检测 |
| [rules/layers.py](rules/layers.py) | 父链、轴、装载对象兼容、重叠 |
| [rules/objects.py](rules/objects.py) | 起止顺序与时长 |
| [rules/binds.py](rules/binds.py) | 关联两端统一检查 |
| [配置读取器](../configuration/loader.py) | 检测需要配置时读取，检查继承并合并约定 |

登记表使用字符串函数路径；需要执行才导入规则模块。规则是普通函数，不需要检测器基类、装饰器或目录扫描注册。

| 改动 | 自动检查 |
|---|---|
| 新建层/对象 | 该目标适用的规则，以及有关层的装载约定 |
| 普通字段修改 | 已修改字段的类型；声明依赖这些字段的规则 |
| begin/end | 起止顺序、已启用的时长与重叠限制 |
| 对象换层 | 旧层、新层的对象兼容与重叠 |
| father | 父链无环、改变根/子身份后的轴约定 |
| axis | 字段类型、轴的位置约定 |
| config_ref | 当前目标规则；对象类型变化或层配置变化也检查层的装载约定 |
| 关联端点变化 | 关联两端存在性 |
| 删除实体 | 保留关联的端点；删除对象也复查原层 |
| 配置文件修改 | 显式调用 validate；不制造 update 或日志 |
| read、无实际变化的更新、return_self | 不自动检测 |

批次按最终记录检查，创建后又删除的临时对象不参与；同一目标与规则只执行一次。某个规则可返回多对真实冲突。只改 name/tips 不扫描父链或重叠，也不重查旧的内容错误。结果只说明本次范围，不宣称整个项目通过。

## 约定

- 对象必须有所属层：Python 的 layer 是必传关键字参数，保存时由 NOT NULL 与复合外键保证非空、层存在和项目正确。类型注解本身不拦截显式传入 None；基础类不查询数据库。
- 父层存在由外键保证，不再重复检测 father_exists/layer_exists。父链无环在结构变更后诊断；Python 类继承环由 Python 处理，配置继承环由读取器处理。
- 根可以没有轴；默认仅根可设轴。配置 options.axis_only_on_root=false 后，子层可设自己的轴。
- 层接受指定对象配置及其派生配置。拥有 text 字段的基础 Object 不自动成为 Text；类型兼容和内容有效性分别判断。
- begin<=end，允许负位置。持续区间为 [begin,end)，瞬间 begin=end 占一个点。1～3 与 3～5 不冲突；瞬间 3 与 1～3 不冲突，与 3～5 冲突；同点瞬间冲突。
- overlap=true 不执行冲突检查；duration=any 不增加时长限制。positive 要求正时长，zero 要求瞬间。
- 没有必填 text/source、文本长度、资源存在性、文件格式、树深度等附加限制。visibility 留给视图，不检查实例显隐。

## 反馈

内置问题为普通字典：severity（warn/error）、rule、target（kind/project_id/id）、message；可附 field、related、skipped。

- completed：本次选择的检查执行完成，issues 仍可含 error。
- partial：部分检查无法执行，每条 skipped=true 的问题说明原因，其他继续。
- not_run：没有实际改动，或显式关闭自动检测。
- failed：整个外部 checker/入口异常，已有提交保留。

缺失/损坏配置逐目标报告；基础配置仍可读时，基础字段、父链、起止顺序仍可检查。无法判断的派生约定、类型兼容等明确报告未检查。规则异常按项捕获，不丢掉此前已收集的问题。软关联失效返回 warn，引用保持原样。

## 调用

```python
from functools import partial
from runtime.storage import crud
from runtime.validation.runner import check_changes, validate

# connection 是已打开的数据库连接。只读复查，无业务写入、无日志。
checks = validate(
    [{"kind": "layer", "project_id": 1, "id": 1}],
    partial(crud.read, connection),
)
```

层复查包含直接装载的对象，不递归子层；项目目标 {"kind":"project","id":1} 检查该项目全部层、对象与两端涉及该项目的关联。对象目标复查该对象及相关层。此接口面向数据库记录，尚未实现 Python 实例的存储还原适配。

```python
from runtime.dispatch import dispatch

# 默认内置检测。
result = dispatch(connection, request)
# 明确关闭；也可传自己的 checker(changes, read_record) 替换内置检测。
result = dispatch(connection, request, checker=None)
# 自定义配置根目录；每次调用都会新建 Loader。
result = dispatch(connection, request, checker=partial(check_changes, config_root="/path/to/configs"))
```

低层 CRUD 仍不提交、不检测；组合调用方提交后将 changes 交给 check_changes，或主动 validate。检测只接收查询入口，不接收可写数据库连接。

## 新增约束的完整示例

下面演示一个自选的“标题文本不为空”规则，它没有加入当前基础约定。

第一步，在 rules/objects.py 增加普通函数：

```python
def text_nonempty(record, config, read_record):
    information = record.get("information")
    if isinstance(information, dict) and information.get("text") == "":
        return [{"severity": "error", "field": "information.text", "message": "标题文本不能为空"}]
    return []
```

第二步，在 registry.py 的 RULES 中登记：

```python
"text_nonempty": {
    "function": "runtime.validation.rules.objects:text_nonempty",
    "triggers": {"object": ("information",)},
    "scope": "self",
    "setting": ("rules", "text_nonempty"),
},
```

第三步，新增 configs/objects/title.toml：

```toml
[object]
type = "title"
extends = "text.toml"
note = "标题用途，复用文字对象类"

[object.rules]
text_nonempty = true
```

文字层接受此派生配置。新规则仅在配置启用且有关字段变化时执行，runner 与 CRUD 无需修改。规则返回问题列表；runner 补充 rule/target，规则也可为相关对象指定 target。函数应只读输入与关联数据。

登记表的 triggers 按数据种类列出依赖字段；None 表示任意字段。创建、config_ref 变化和主动复查会重新选择适用规则。scope=self 检查目标自身；layer 选择有关旧/新层；binds 检查关联自身或实体删除留下的关联。遇到全新的跨实体范围才扩充 runner 的范围选择函数。

可用的合并配置携带 _lineage；规则需要解析其他配置时可使用 config["_loader"]。_changed_fields 是本次变化字段，None 表示全量复查，供通用字段检查使用。新内容类型复用已有规则时，只新增类/配置，不修改登记表。

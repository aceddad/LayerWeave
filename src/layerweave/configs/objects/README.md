# 对象配置

[返回配置入口](../README.md)。

基础约定、通用封装及 Title 派生示例放在这里，可按需继续分子目录。工具包登记的对象类型也放在这里，class 指向工具包，用 `requires` 写明依赖，例如视图工具的批注对象 note.toml（继承 text.toml），步骤见[工具包登记类型](../../tool/builtin/developer/TOOL_TYPES.md)。对应 Python 类在 src/layerweave/models/objects/，读取与继承见 [配置说明](../../support/configuration/README.md)。

每份封装明确声明自己的 type 与 class，一个类只绑定一份配置。title.toml 继承 text.toml，绑定继承 Text 的独立 Title 类；沿用文字约定，不添加限制，也不需要新建标题层。

对象 layer 必须指向同项目实际存在的层。base.toml 说明字段与固定约定，默认 duration=any、visibility=true。optional=true 允许字段缺省并随字段继承；已填写时仍检查类型。未声明 optional 按 false 检查缺失。模型/动作的 source/data 均声明 optional=true。产生诊断后，等级在 ../logging/diagnostics.toml 管理，路径覆盖不继承，未配置默认 warn。所有内置类型 open=true，允许附加内容键。

text 使用 information.text；image/audio/movie/model/active 使用 information.source 引用资源；model/active 另可使用 information.data 字典。引用原样保存，资源解释与工具接入后续实现。

## 通用数据 Data

Data 与 DataLayer 自 0.7.10b2 起提供；已有数据库无需迁移，读取配置并还原这两种类时使用本版或更新版本。

[data.toml](data.toml) 对应直接继承 Object 的 Data；[数据层](../layers/data.toml)对应直接继承 Layer 的 DataLayer，接受 Data 及其派生封装。它不继承 Text，不要求 information.text。

information 外层保持字典，information.data 承载 JSON 对象、数组、字符串、整数、小数、布尔值或 null，可以嵌套组合：

```json
{"data": {"name": "角色甲", "tags": ["主角"], "enabled": true, "extra": null}}
```

这段是 information 的内容；创建对象还需要所属层与 config_ref。空字典、空列表、空字符串、0、false 和 null 都是合法值，漏填 data 则按现有 missing_field 设置报告，默认 warn；不在构造或赋值时拦截。附加信息键仍由 open=true 允许。

数据应遵守 JSON 表达范围：字典键为字符串，数字有限。现有字段检测检查 data 的顶层类型，不为嵌套业务结构增加 Schema 校验；存储仍沿用 JSON 编码。不自动解析 JSON 字符串、YAML、TOML、CSV 或 XML。需要读取这些格式时，由使用方解析、转换为可用 JSON 表示的内容；保留原文时可以存字符串，并在 information 的附加字段注明格式。日期、特殊数值及资源引用的表示方式也由使用方约定，二进制入库使用[工具表 BLOB](../../../../docs/build-with-layerweave/03-managed-tables.md)。

位置可以表示时间，也可以 begin=end 表示序号；数据层示例里的序号轴只是示例，不是该类型的固定规则。JSON 内容中的业务引用仍由工具维护，不会因为使用 Data 就自动重映射。

最短可运行示例见 [examples/data.py](../../../../examples/data.py)，涵盖各种值的保存、关闭重开和实例还原。查看当前用法及完整声明：

```sh
python -X utf8 -B examples/data.py
python -X utf8 -B -m layerweave.tool.builtin.shared.help.config_help combined data
python -X utf8 -B -m layerweave.tool.builtin.shared.help.config_help objects data --dev
```

需要专用数据类型时，可以继承 Data 并增加自己的字段约定；父配置已有的 data 类型约定仍按现有规则固定。只接受特定 data 结构的业务校验由对应工具执行，或从 Object 新建独立封装。无需新增数据库表或修改读写接口。

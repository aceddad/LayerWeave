# 诊断汇报配置

[configs/logging/diagnostics.toml](../../configs/logging/diagnostics.toml) 独立管理汇报等级。原有约束继续决定是否执行检查，不增加 enabled 开关；修改等级不改变约束和写入结果，也不影响 changes 操作历史。

| 等级 | 行为 |
|---|---|
| error | 输出错误诊断 |
| warn | 输出警告诊断 |
| none | 检查仍执行，但不输出该项诊断 |

未提供配置文件、未写对应项，均使用 warn。只有发现问题才汇报；配置缺失本身不制造一条警告。配置文件语法或等级写错时，保留已有问题并给出配置警告。每次操作重新读取文件。

读取位置为 `config_root/logging/diagnostics.toml`；config_root 仍指配置根目录。文件内的封装引用仍相对于 config_root，例如 `objects/model.toml`，不随日志配置文件所在目录改变。

## 查找顺序

诊断有 code 时按 code 查找；没有 code 的自定义规则使用 rule 名称。优先级：封装+code+字段 → 封装+code → 全局 code → warn。封装路径相对于当前 config_root，按具体配置匹配，不从父封装隐式继承汇报覆盖项。

```toml
[levels]
field_type = "error"
missing_field = "warn"
field_typo = "warn"

# 只隐藏文字对象缺少 text 的提醒，类型错误仍使用全局 error。
# 这是本封装的汇报偏好，不改变字段约定，也不传给 Title。
[overrides."objects/text.toml".missing_field]
"information.text" = "none"

# 也可以对一个封装的某类诊断整体指定等级。
[overrides."objects/title.toml"]
missing_field = "error"
```

model/active 的 source 和 data 在各自封装里声明 optional=true，并随字段继承；缺省符合约定，不产生 missing_field，因而不需要本文件静音。提供了值仍检查类型。未声明 optional 时按 false 检查，产生的问题依照这里的等级汇报。none 只隐藏已有诊断，不负责表达字段是否可选。open=true 仍允许自定义键；未声明键像某个未填写字段时，field_typo 提供建议而不自动修改数据，包括可选字段。对应字段已经存在时不猜测笔误。

## 合并与展示

同一目标、同一种配置失败、同一失败配置路径，只报告一次原因，affected_checks 保留每个受影响的规则和检查目标。不同对象各自定位。合并不制造历史状态，也不把关联问题推断为旧问题。

文字输出只列操作结果和逐条诊断，跳过的检查在对应条目中说明。JSON 的 checks.status 仍描述实际执行情况：即使失败诊断被设为 none，无法完成的检查仍使状态为 partial。静音不会伪装成已完成。

内置检查与文本汇集使用这一配置。外部 checker 若直接返回诊断列表，仍由提供方设置其等级；要使用统一配置，可调用 prepare_diagnostics 后交给通道，或在只读工具中调用 support.api.diagnostic_report。

新增诊断只需给出稳定 code、目标、字段和原因，再在这个文件中配置等级；漏写等级时自然回退为 warn。规则函数不需要负责文字展示或读取汇报配置。

配置 help 通过同一个 DiagnosticPolicy.level/describe 查询等级，不伪造诊断来推测级别，也不单独维护等级映射。规则对应的问题代码可能带字段覆盖，describe 同时保留默认级别和这些覆盖。

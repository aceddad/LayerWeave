# 层配置

[返回配置入口](../README.md)。

基础约定与通用封装放在这里，可按需继续分子目录。对应 Python 类在 src/layerweave/models/layers/，读取与继承见 [配置说明](../../support/configuration/README.md)。

每份封装明确声明自己的 type 与 class，一个类只绑定一份配置。type 字符串只在 TOML 定义，由保存接口写入层记录，Python 层类不重复声明。

base.toml 说明字段、返回方法、固定规则、默认取值和可调选项。默认 overlap=true、visibility=true；具体封装的显式 constraint/display 成为固定父约定。axis_only_on_root 是明确可调选项，默认 true，根层不必填写轴。

层的 objects 按对象配置 type 唯一定位，接受该类型及其派生配置。内置层包括 text、data、image、audio、movie、model、active；data 用于[通用 JSON 数据](../objects/README.md#通用数据-data)。

工具包也可以在这里登记自己的层类型：配置照常放在本目录，class 指向工具包里的类，并用 `requires = "工具包模块"` 写明依赖。这样 AI 和工具按类型就能找到它，配置帮助也会列出；卸掉那个工具包后，配置仍说明数据的样子、检测照常，只是不能还原成实例。现有的例子是视图工具的批注层 note.toml（装 objects/note.toml 的批注对象），约定见[视图工具](https://gitee.com/emotion1354414/layer-weave/blob/visualization/src/layerweave/tool/builtin/view/DEVELOPMENT.md#批注层用一个层当有序列表)。完整步骤见[工具包登记类型](../../tool/builtin/developer/TOOL_TYPES.md)。

axis.precision 是位置写入、工具和检查共用的正数步长。子层未声明轴时沿父链取得轴，默认来自根；显式自有轴覆盖上级轴。没有轴或当前轴没有 precision 时默认 1e-6。所有对象位置写入按精度落点，比较使用同一整数刻度；不换算单位或 fps。读取保持原始存储数值，不批量重写旧数据。

## 外置技能 tools

层原型的 `[layer]` 可声明 tools，供 AI 按路由查阅外置 skill。它与软件自身的内部工具目录是两回事，不是 Layer 实例字段。

以下仅为填写示例，不表示项目已安装这些技能；实际使用时替换 route：

```toml
# 放在已有 [layer] 的字段区内。
tools = [
  { route = "skill:example-text-format", tier = "层级", when = "需要统一文字格式时" },
  { route = "skill:example-lyric-align", tier = "可用", when = "已有歌词和时间标记，需要辅助对齐时" },
]
```

| 字段 | 给 AI 的说明 |
|---|---|
| route | 技能在哪里；填写 AI 可定位的文件位置或 skill 引用 |
| tier | 技能的分类或级别，例如“层级”“可用” |
| when | 何时使用该技能、需要什么场景或前提 |

tier 和 when 都是原样展示的说明，不是枚举限制、开关或检测条件。route 不由本程序拼接、解析、检查存在性或执行。项目内文件路径应写清相对位置，外置引用由 AI 所在环境解释。

当前文字、图片、音频、视频、动作层已填写技能引用，基础层、数据层和模型层仍以 tools=[] 留位。实际技能清单以各层 TOML 和配置 help 为准；引用只帮助 AI 查阅，不表示自动执行或已安装技能所需依赖。配置 help 会在总览和详情展示这些引用；具体输出位置见[配置 help](../../tool/builtin/shared/help/CONFIG_HELP.md)。这项声明不新增约束，也不改变现有字段的检查。

仓库内的技能存放方式、实际示例与绑定写法见[外置工具](../../tool/README.md)。已有外置 skill 也可以直接填写它的引用位置。

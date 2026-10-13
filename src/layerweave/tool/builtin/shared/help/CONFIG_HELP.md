# 使用 help 与开发 help

两种 help 共用动态发现与配置读取：默认 `audience="usage"` 供调用工具，`audience="developer"` 供开发封装。它们均不读取项目实例、不连接数据库、不导入或运行配置指向的 Python 类。项目已有内容仍用项目概览、详细展开等数据工具查看。

使用 help 展示用途（when/note/not_for）、有效内容输入、约定、保存示例和公共接口的输入/返回。开发 help 另外展示完整有效定义、字段属性来源、继承链、固定约定、汇报等级和当前 TOML 原文。两者保留同样的四种查询范围：

| view | 内容 |
|---|---|
| overview | 所有层及各自接受的对象类摘要 |
| layers | 指定层的支持说明；对象类只列摘要 |
| objects | 指定对象类的支持说明 |
| combined | 指定层的说明，加上它们接受的对象类详情；工具包登记的派生类型（配置里声明了 requires，例如视图工具的 note）只在支持列表里点名，查它所属的层时才展开 |

## 使用

完成可编辑安装后运行，无需提供数据库或项目编号：

```sh
python -X utf8 -B -m layerweave.tool.builtin.shared.help.config_help
python -X utf8 -B -m layerweave.tool.builtin.shared.help.config_help combined text
python -X utf8 -B -m layerweave.tool.builtin.shared.help.config_help objects model title --dev
# 查当前参数、可选值及默认值。
python -X utf8 -B -m layerweave.tool.builtin.shared.help.command_help config_help --json
python -X utf8 -B -m layerweave.tool.builtin.shared.help.config_help --help
```

本文解释两种阅读方式和返回含义；参数说明由实时 help 从命令声明生成。使用版保持简洁，开发版详情默认附当前 TOML 原文；父配置原文可按 lineage 路径另行查询。配置根目录包含 layers/、objects/ 和可选的 logging/diagnostics.toml。

Python 工具入口：

```python
from layerweave.tool.builtin.shared.help.config_help import config_help, format_help

result = config_help("combined", ["text", "image"])
print(format_help(result))
development = config_help("objects", ["model", "title"], audience="developer")
```

需要纯数据时也可从 layerweave.tool.builtin.shared.help.catalog 导入 read_support，参数相同；config_root 省略时使用包内配置目录。从项目根运行 python examples/config_help.py 可查看四种查询的调用示例。

## 目标与结果

详情接受单个目标字符串或目标列表。优先使用完整 config_ref，如 objects/title.toml；也支持唯一的 type、完整 Python class 路径或类名。名称匹配严格区分大小写；多个配置同名时列出候选，使用路径消除歧义，不猜测。重复指向同一配置的有效目标只返回一次。显式空列表返回空 items，不展开全部配置。

返回 view、audience、status、items、issues；联合查询另有 object_details。同一对象类的详情只在 object_details 中出现一次，各层的 accepted_objects 通过 config_ref 指向它。详情的公共保存输入与返回说明放在顶层 io，仅显示一次。

每项有 target、kind、config_ref 和 status。loaded 表示配置已成功解析；它说明配置声明的能力，不表示 Python 模块已经经过导入或执行测试。unavailable 表示该项配置不可用，其他项继续返回。层的兼容对象目录含不可解析条目时，accepted_objects_complete=false，并保留已确定的兼容类。顶层 partial 不因诊断被静音而改成 completed。

总览使用简短 summary。使用版详情包含：

- summary：身份与用途，保留 when/note/not_for 和外置技能 tools 声明。
- usage：有效内容字段与相关约定；派生 Title 仍能看到继承的 information.text，不要求调用者自行追查父类。
- reporting_exceptions：仅列与全局设置不同的汇报等级；无差异则不出现。
- save_example：带当前 config_ref 的保存调用代码，以及所需上下文变量。

开发版详情包含同样的 save_example，并提供：

- definition：按既有规则合并继承后的配置，保留字段、类型、说明、默认值声明、约束、方法、示例及额外的自定义节。
- lineage：完整配置继承链。
- field_origins：每个基础/内容字段属性的最后声明位置；未声明 optional 标为 default: false，默认值不写回字段约定。
- fixed_contracts：固定约定，与 defaults 和可调 options 区分。
- reporting：复用实际诊断的等级解析，展示已知字段的类型错误等级、内容字段缺失等级；约定对应的问题代码保留默认等级及字段覆盖。疑似笔误按实际问题键应用等级覆盖。
- source：默认提供，也可用 include_source 控制，表示当前 TOML 文件原文。

optional=true 表示允许缺省；缺省符合约定，已填写时仍检查类型。未声明时默认 false，缺失会产生诊断，缺失等级未配置则为 warn；这不等于在写入前阻止保存。开发版 reporting 说明“若产生该诊断时采用的等级”，不会让 optional 字段的合法缺省变成问题。日志路径覆盖不继承。

## 层原型的外置技能

配置里的 tools 是给 AI 阅读的技能引用。声明格式和 route/tier/when 的含义统一见[层配置说明](../../../../configs/layers/README.md#外置技能-tools)。

总览与使用版详情在 summary.tools 中保留完整声明；开发版详情在 definition.tools 中保留。文字输出将 route、tier、when 分行列出，联合查看也沿用同样展示。空列表显示“未声明”。

help 不打开技能文件、不解析路由或判断 tier/when 是否满足条件。其他形状的声明原样展示，不产生技能诊断；--raw 或开发版的 TOML 原文仍可查看实际写法。tools 只是配置说明，不出现在保存层实例的字段列表中。

## 保存示例与构造参数

TOML 的 example 仍表示 Python 类的构造参数，开发版保留原样；config_ref 是存储元数据，不传给 Python 构造函数。两种 help 另行生成 save_example，自动补入当前查询封装的 config_ref，派生封装不会误用父配置路径。

生成的示例调用 layerweave.support.api.save_layer/save_object，保持帮助包独立使用，默认不检测。需要默认内容检测时，改用 layerweave.tool.builtin.usage.records.save 中的 save_layer_with_checks/save_object_with_checks。

示例使用已初始化的 connection、真实 project_id，以及对象所属的真实 layer_id。所需变量在 required_context 中逐一说明；help 不查询数据库，也不会假设编号 1 已存在。准备好这些变量后，代码可直接调用。自定义配置目录也会进入保存调用。

新增示例移除作者示意的 id/project_id/type；非空父层、绑定、装载对象等已有引用使用明确的上下文变量，不能把作者的示意编号直接当作真实数据。示例字段列表复用实际保存接口。作者没有提供参数字典、含不支持的顶层字段或不能表示为 JSON 的保存值时，save_example 单独标记 unavailable 并说明原因，其他支持信息仍可读。

新增内容字段时，作者应同步补充 example，使示例内容符合自己的约定。Help 不执行示例或模拟全部检查；不根据字段 default 猜测业务内容，也不会自动补写 information。测试会在临时数据库执行内置封装的两种 help 示例。TOML 额外说明里的日期时间与非有限数值在 JSON 视图中表示为字符串，原始写法可通过 source 查看。

结构化查询有效时退出码为 0，包括部分目标不可用；参数或配置根目录错误为 1，命令行参数用法错误由 argparse 返回 2。文字输出直接附上逐条诊断，JSON 将其保留在 issues。

## 新增封装后自动显示

将自己的 Python 类与 TOML 按项目规范分别放置；TOML 位于 src/layerweave/configs/layers 或 src/layerweave/configs/objects，可继续分子目录。明确声明 type、class，并通过 extends 指向父配置。下次查询会重新发现文件，无需修改 help 的名单或统一模型导出入口。

总览和联查使用 Loader.accepts_object，与运行时兼容检查共用同一个判断。例如继承 text.toml 的 Dialogue 会自动成为文字层可选对象；收窄为 dialogue 的层只列出 Dialogue 及其派生配置。

每次查询内，文件扫描、原文、解析结果、继承合并和日志等级各自复用；下次查询重新读取，因此新增或修改配置后不需要重启。配置损坏、名称冲突和继承错误逐项诊断，未认识的附加节在开发版完整展示。新增检测语义仍由现有规则执行器实现；help 负责描述配置，不替代规则实现。展示数据在本包 help_data.py，查询编排在 catalog.py，文字与 CLI 在 config_help.py，不需要另建封装注册表。

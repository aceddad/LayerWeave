# 配置 help：查支持什么

四种查询都展示封装定义，信息来自 TOML。它们不读取项目实例，不需要数据库，不导入或运行配置指向的 Python 类。项目已有内容仍用项目概览、详细展开等数据工具查看。

| view | 内容 |
|---|---|
| overview | 所有层及各自接受的对象类摘要 |
| layers | 指定层的完整支持说明；对象类只列摘要 |
| objects | 指定对象类的完整支持说明 |
| combined | 指定层的完整说明，加上它们接受的对象类详情 |

## 使用

从 src/ 运行，无需提供数据库或项目编号：

```sh
python -X utf8 -B -m tools.common.config_help
python -X utf8 -B -m tools.common.config_help layers text image
python -X utf8 -B -m tools.common.config_help objects Text Title objects/model.toml
python -X utf8 -B -m tools.common.config_help combined TextLayer ImageLayer --json
python -X utf8 -B -m tools.common.config_help objects title --raw
```

默认文字输出，--json 返回同一份结构化数据；--raw 在详情中附带当前文件原文，包括注释，继承合并后的内容仍在 definition。父配置原文可按 lineage 中的路径另行查询。--config-root 指定配置根目录，其中包含 layers/、objects/ 和可选的 logging/diagnostics.toml。

Python 工具入口：

```python
from tools.common.config_help import config_help, format_help

result = config_help("combined", ["text", "image"])
print(format_help(result))
```

需要纯数据时也可从 runtime.api 导入 read_support，参数相同；config_root 省略时使用项目配置目录。运行 examples.config_help 可查看四种查询的调用示例。

## 目标与结果

详情接受单个目标字符串或目标列表。优先使用完整 config_ref，如 objects/title.toml；也支持唯一的 type、完整 Python class 路径或类名。名称匹配严格区分大小写；多个配置同名时列出候选，使用路径消除歧义，不猜测。重复指向同一配置的有效目标只返回一次。显式空列表返回空 items，不展开全部配置。

返回 view、status、items、issues；联合查询另有 object_details。同一对象类的详情只在 object_details 中出现一次，各层的 accepted_objects 通过 config_ref 指向它。

每项有 target、kind、config_ref 和 status。loaded 表示配置已成功解析；它说明配置声明的能力，不表示 Python 模块已经经过导入或执行测试。unavailable 表示该项配置不可用，其他项继续返回。层的兼容对象目录含不可解析条目时，accepted_objects_complete=false，并保留已确定的兼容类。顶层 partial 不因诊断被静音而改成 completed。

总览使用简短 summary。详情包含：

- definition：按既有规则合并继承后的配置，保留字段、类型、说明、默认值声明、约束、方法、示例及额外的自定义节。
- lineage：完整配置继承链。
- fixed_contracts：固定约定，与 defaults 和可调 options 区分。
- reporting：复用实际诊断的等级解析，展示已知字段的类型错误等级、内容字段缺失等级；约定对应的问题代码保留默认等级及字段覆盖。疑似笔误按实际问题键应用等级覆盖。
- source：仅 --raw/include_source=True 时提供，表示当前 TOML 文件原文。

展示不会把所有字段标成必填，也不根据 default 自动填充内容。example 来自封装作者；示例中的层编号要替换成实际编号。字典保存时还需提供对应 config_ref；Python 实例则按实际类确定配置。TOML 的日期时间与非有限数值在 JSON 视图中表示为字符串，原始写法可通过 source 查看。

结构化查询有效时退出码为 0，包括部分目标不可用；参数或配置根目录错误为 1，命令行参数用法错误由 argparse 返回 2。文字输出直接附上逐条诊断，JSON 将其保留在 issues。

## 新增封装后自动显示

将自己的 Python 类与 TOML 按项目规范分别放置；TOML 位于 configs/layers 或 configs/objects，可继续分子目录。明确声明 type、class，并通过 extends 指向父配置。下次查询会重新发现文件，无需修改 help 的名单或统一模型导出入口。

总览和联查使用 Loader.accepts_object，与运行时兼容检查共用同一个判断。例如继承 text.toml 的 Dialogue 会自动成为文字层可选对象；收窄为 dialogue 的层只列出 Dialogue 及其派生配置。

每次查询内，文件扫描、原文、解析结果、继承合并和日志等级各自复用；下次查询重新读取，因此新增或修改配置后不需要重启。配置损坏、名称冲突和继承错误逐项诊断，未认识的附加声明仍展示。新增检测语义仍由现有规则执行器实现；help 负责描述配置，不替代规则实现。

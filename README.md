# LayerWeave

创建日期：2026-10-08。当前状态：六类封装及 Title 派生示例、SQLite 存储与日志、完整读写、配置继承与检测已实现。已提供概览/详细展开、对象检索、文本汇集及位置编辑工具；缺字段给 warn，工具生成位置按轴精度落点。可视化尚未开始。

## 快速开始

当前代码只使用 Python 标准库。本机核对环境为 Python 3.11.3、SQLite 3.40.1。读取 TOML 使用 tomllib；发号语句需要 SQLite 3.35+。

从本项目目录进入 src，运行完整示例：

```sh
cd src
python -X utf8 -B -m examples.read_write
```

此示例使用自己的临时数据库文件，演示创建层与对象、关闭重开、还原 Python 实例、修改并再次保存、读取关联和日志，不改动输出数据库。原有记录 CRUD 示例仍可用：`python -X utf8 -B -m examples.crud`。

派生封装示例：`python -X utf8 -B -m examples.title`。Title 继承 Text，标题 TOML 继承文字 TOML 并绑定 Title；普通文字层可同时装载两种对象，保存时不需要额外指定配置。

纯模型示例仍可用：`python -X utf8 -B -m examples.all_layers` 或 `python -X utf8 -B -m examples.text`。其中手动编号只用于演示内存结构，持久化时由核心分配编号。

查看第一批四个工具的完整演示：`python -X utf8 -B -m examples.first_batch`。只查看项目概览可运行 `python -X utf8 -B -m examples.project_overview`。真实数据库的用法和结果格式见 [内部工具说明](tools/README.md)。

第二批六个写入工具的内存演示：`python -X utf8 -B -m examples.second_batch`，涵盖接续新增、连续排列、平移、对齐、修改时长和复制。

详细展开的内存演示：`python -X utf8 -B -m examples.project_details`，展示指定层及子层按数值范围筛选后的完整对象内容；不做单位换算。

初始化数据库（同样从 src 目录执行）：

```sh
python -X utf8 -B -m runtime.storage.database ../output/ai-production.sqlite3
```

数据库由上述命令在本地生成，默认位置为 `output/ai-production.sqlite3`，不随 Git 上传。初始化会补建缺失表，并将旧版 objects.layer 升级为 NOT NULL，保留原数据；存在未归属的旧对象时停止迁移并列出编号，不自动猜测归属。

读取项目列表的 JSON 入口：

```sh
python -X utf8 -B -m runtime.console ../output/ai-production.sqlite3 --request examples/requests/read-projects.json
```

完整读写与内部工具开发优先阅读[公共 API](src/runtime/API.md)。单条请求、批量事务和反馈格式见[运行接口说明](src/runtime/README.md)。

## 按任务找入口

| 要做什么 | 从哪里开始 |
|---|---|
| 读写完整层/对象、开发内部工具 | [公共 API](src/runtime/API.md)、[统一入口](src/runtime/api.py)、[往返示例](src/examples/read_write.py) |
| 理解层的基础结构 | [层基础类](src/models/layers/base.py)、[层基础配置](configs/layers/base.toml) |
| 理解对象的基础结构 | [对象基础类](src/models/objects/base.py)、[对象基础配置](configs/objects/base.toml) |
| 新增一种封装 | 对照 [文字层类](src/models/layers/text.py)、[文字对象类](src/models/objects/text.py)、[层配置](configs/layers/text.toml)、[对象配置](configs/objects/text.toml) |
| 看 CRUD、日志和检测组合 | [完整内存示例](src/examples/crud.py) |
| 看六类模型的创建装载 | [六类组合示例](src/examples/all_layers.py) |
| 修改配置读取与继承 | [配置读取器](src/runtime/configuration/loader.py)、[合并约定](src/runtime/configuration/README.md) |
| 查看项目层级与数量 | [项目概览工具](src/tools/common/project_overview.py)、[用法与示例](tools/README.md) |
| 按项目/子树/时间范围详细展开 | [详细展开工具](src/tools/common/project_details.py)、[完整示例](src/examples/project_details.py) |
| 检索对象、查询关联、汇集文字 | [第一批工具说明](tools/README.md)、[完整组合示例](src/examples/first_batch.py) |
| 接续新增、位置编辑、对象复制 | [第二批工具说明](tools/README.md)、[完整组合示例](src/examples/second_batch.py) |
| 开发内部工具 | [工具开发说明](tools/README.md) |
| 查看表结构与存储操作 | [建表脚本](src/runtime/storage/schema.sql)、[初始化与发号](src/runtime/storage/database.py)、[存储说明](src/runtime/storage/README.md) |
| 调用 CRUD 和查看日志 | [运行接口说明](src/runtime/README.md)、[CRUD](src/runtime/storage/crud.py)、[分流](src/runtime/dispatch.py) |
| 新增约束或主动复查 | [规则登记表](src/runtime/validation/registry.py)、[检测与扩充示例](src/runtime/validation/README.md) |
| 查看全部约束及检测设计 | [约束与触发时点](src/runtime/validation/README.md) |
| 修改模型与存储映射 | [完整记录读取](src/runtime/storage/assembly.py)、[实例装载](src/runtime/storage/models.py)、[组合保存](src/runtime/storage/save.py) |

新增一种完整内容类别可对照现有六类，分别提供层类、对象类和两份配置。只扩展对象时，例如 Title，仅新增对象类与对象配置即可，继续装入 TextLayer。每份封装 TOML 显式声明自己的 type 与 class；class 指向类定义位置，一个类在同一配置根目录内只绑定一份配置。extends 相对于当前配置文件。

可以直接从具体模块导入新增类。若还要支持统一的 `from models import ...` 入口，目前需要同步三个导出文件：`src/models/__init__.py`、`src/models/layers/__init__.py`、`src/models/objects/__init__.py`。这些入口现在只按请求加载对应模块，不导入全部封装。若不需要统一入口，只从具体模块导入即可。

## 核心约定

- 给 AI 用的制作辅助工具：用层、对象组织内容、关系及其在轴上的位置。
- 底层保持精简和自由。Layer、Object 只保存字段和返回自身；检测、配置读取、持久化由外部执行代码承担。
- type 字符串统一由 TOML 提供，Python 类不再重复声明；name 是创建实例时传入的名字，objects 实际装载对象实例。常规保存自动填写层记录的 type，原始 CRUD 的矛盾值由独立检测报告。
- Object.layer 是必传关键字参数，保存时保证非空且层存在。information 是内容字典；Python 类型注解本身不做运行时拦截，所有封装保留 open = true。
- 完整读写使用 runtime.api；read 返回记录字典，load 返回派生实例，save 同时接受字典和实例。整层保存明确设置所传对象的归属；省略对象或关联不表示删除。
- return_self() 返回同一个 Python 实例；它不是 JSON 导出或数据库序列化方法。
- visible 已从基础类移除。visibility 是配置中的显隐控制能力，默认 true；实际显示状态由外部视图管理。
- 基础配置说明类本身及共同检测约定；后续封装延续基础检查，相同检查不重复执行。可调整的默认约定与共同规则分开。
- CRUD 与检测职责分开，对外一次调用。操作和日志先成功提交，再统一调用内置检测。可显式传 checker=None 关闭自动检测；检测失败不掩盖已提交的操作。
- 分流入口为每次请求或批次生成一次 operation_id（UUID）。只有实际增删改写 changes 日志，读取不写日志；同一批操作与日志共用事务。
- 先讨论清楚一块，再落到实现；旧材料中未获认可的提议不自动成为新设计的决定。

## 已有的六类封装

每类都有层类、对象类和两侧配置。层默认允许重叠，对象默认 duration = "any"，显隐控制默认开启。

| 标识 | 层类／对象类 | 主要内容 |
|---|---|---|
| text | TextLayer／Text | information.text |
| image | ImageLayer／Image | information.source：图片引用 |
| audio | AudioLayer／Audio | information.source：音频引用 |
| movie | MovieLayer／Movie | information.source：视频引用 |
| model | ModelLayer／Model | source：模型引用；data：可选字典 |
| active | ActiveLayer／Active | source：动作引用；data：可选字典；bind：作用对象关联 |

另有 [Title 类](src/models/objects/title.py) 和 [标题配置](configs/objects/title.toml) 作为派生示例；继承 Text 的内容与约定，不新增非空或长度限制，也不新增标题层。

source 目前原样保存，由使用方解释。封装不读取资源，也不新增必填、资源存在性检查或格式白名单。主线、歌词、背景、原画等用途可通过实例名字区分，复用同一种封装。

## 数据库（四张业务表与日志表已实现）

采用 SQLite：

| 表 | 保存内容 |
|---|---|
| projects | id、name、max_id、tips |
| layers | project_id、id、name、type、config_ref、father、axis、tips |
| objects | project_id、id、name、config_ref、layer、begin、end、information、tips |
| binds | 内部 id，来源和目标各自的 kind、project_id、id，以及 tips |
| changes | id、operation_id、created_at、kind、project_id、target_id、action、before_data、after_data |

编号与归属：

- 项目编号独立管理；每个项目内部，层和对象共用一套发号器。
- 实体的完整身份为 (project_id, id)。不同项目可重复局部编号，同一项目内层与对象不重号。
- projects.max_id 记录历史上已提交的最大实体编号，初始为 0，删除实体后不回退。项目编号本身不占这个计数，项目表独立自动发号。
- layer／object 是实体种类；text／image 等是封装类型，二者分开。
- 项目归属包含在实体的项目号中，不再另设项目归属关系表。跨项目通过 bind 引用，保留目标完整身份。
- binds 的两端是普通引用，可由检测通道报告失效目标。关联记录有自己的内部行号，不参与项目内实体计数。
- allocate_id() 统一给本项目的层和对象发号，不自行提交。调用方将发号与记录写入放在同一个事务中，整个事务回滚时计数也回滚。
- 两个实体表的主键各自限制同表重号，跨表共享编号由统一发号方法保证；没有额外触发器追踪任意直接 SQL 写入。
- 整项目换号与向已有项目迁入内容的操作接口尚未实现；后者可能需要编号映射。
- 同项目 father、layer 引用可利用项目上下文解释。跨项目 bind 必须明确两端的项目和种类。
- 可视状态暂不持久化。轻量修改历史已使用独立 changes 表，日志不占项目内实体编号，也不对被记录的实体加外键。

存储方式：config_ref 保存相对于 configs/ 的配置路径，给按需装载正确的类提供依据；它是存储元数据，不加进基础类。axis、information 保存为 JSON 文本。层的 objects 和两类的 bind 分别从对象表、关联表反查，不重复保存在实体行里。

已启用项目归属、同项目父层和对象所属层的外键；father 可为 NULL，objects.layer 必须非空。没有级联删除或更新，也没有把时间、环、轴、资源或封装规则写成数据库检测。普通删除不级联，项目搬移接口仍待实现。

存储检查命令（从 src 执行）：

```sh
python -X utf8 -B -m unittest discover -s ../tests -v
```

测试覆盖配置继承、父约定保护、字段类型、区间边界、类型兼容、检测触发范围、逐项继续、批次最终状态、按需导入，以及存储、日志、迁移、完整记录/实例往返、关闭重开和 CLI。使用内存库和专用临时文件，不写入输出数据库。

当前包含详细展开、缺字段提醒和轴精度回归在内的 154 项测试通过。JSON 内容变化会区分 `1`、`1.0` 与 `true`，日志、批次最终状态和检测字段选择使用同一比较方式；字典键顺序不产生变化。无变化的字段在 SQL UPDATE 前跳过。

此前读写优化时的本地 100 对象场景记录（现有层、新 Text 实例自动匹配配置、内置检测开启；以下文件读取数是加入 Title 与配置唯一性检查前的基线）：

| 操作 | 修复前 | 修复后 |
|---|---|---|
| 新增 100 个对象的 TOML 读取次数 | 711 | 18 |
| 完整读层的 SELECT 次数 | 103 | 4 |
| 原样保存整层的 UPDATE 次数 | 101 | 0 |

配置索引只在本次调用内复用，下次调用重新读取；关联按所属层成批查询。以上是操作次数，数据量与返回内容仍随对象数量增长。

## CRUD 与反馈

- create、read、update、delete 面向 project、layer、object、bind；另支持 read(kind="change") 查询日志。
- 层和对象通过 project_id 与 id 定位；项目、关联记录按独立 id 定位。
- read 按 id 返回单条或 null，未传 id 返回筛选列表；第一版支持普通列等值和空值条件。
- update 只修改传入字段，JSON 字段整体替换；身份与计数由系统管理。delete 不级联。记录不存在或数据未变化时不记日志，applied 为 false。
- 分流入口接收字典或字典列表，列表原子提交；使用中的连接不能已有待提交操作。
- 反馈区分 ok/applied 与 checks。检测状态为 not_run、completed、partial、failed；completed 时也可能存在 issues。
- 默认 CLI 与 dispatch 已接入配置规则。可传 checker(changes, read_record) 替换内置检测器；它拿到前后记录与查询入口，一批只调用一次。
- 配置文件不存在不会被 CRUD 额外拦截；config_ref 原样存取，缺失配置由提交后的检测逐条报告 partial，其他目标继续。

## 完整读写

- read_layer/read_object 读取完整记录及发出的关联，层同时装载直属对象；不依赖配置文件可读。
- load_layer/load_object 按每条记录的 config_ref 还原 Python 派生实例，不递归父层、子层或关联目标。
- save_layer/save_object 新增或更新显式传入项；Python 实例按实际类取得配置，字典更新省略 config_ref 时保留原引用。层的 type 从配置取得，事务成功后回填编号。删除仍为显式操作。
- bind 采用包含 kind、project_id、id 的完整来源/目标字典，新建时可只填写目标，由保存入口补齐来源。
- config_ref 与 project_id 保持为存储元数据，不添加到基础类。常规 save 需要可解析的对应配置；缺配置的原始数据仍可通过 dispatch/CRUD 保存，再由检测逐条报告。省略 type 时必须能读取层配置，接口不猜测。

API 参数、保存范围与错误反馈见 [公共 API](src/runtime/API.md)。源码位置与后续工具开发说明见 [工具指南](tools/README.md)。

第一批四个内部工具为只读功能。第二批六个写入工具复用事务内请求工厂、日志和提交后检测，位置计算与写入使用同一事务。整层复制、关联重映射、跨项目搬移、视图、Skill／MCP 尚未实现。

## 目录职责

- configs/layers、configs/objects：基础约定与具体封装配置。
- src/models/layers、src/models/objects：Python 类。
- src/examples：模型示例、CRUD 全流程示例和 JSON 请求示例。
- src/runtime/storage：表结构、初始化、发号、CRUD、日志、完整记录组合与模型适配。
- src/runtime/api.py：内部工具的固定导入入口；operation.py 提供共享事务与提交后检测。
- src/runtime/dispatch.py、console.py：分流与 JSON 入口；validation 为模块化规则执行器，configuration 负责配置读取和继承。
- tests：存储、CRUD、事务日志、检测接口及 CLI 检查。
- output：可供使用的 SQLite 数据库。
- src/tools/common：通用内部工具，包括项目概览、对象检索、关联查询，以及位置编辑、接续新增和对象复制。
- src/tools/text：文字工具，目前为文本汇集；其他类型目录按实际需要创建。
- tools：已有工具用法与后续开发说明。

各分类可继续分子目录。原始模板与通用封装模板 V3 分开理解；配置合并遵循 defaults、固定约定与 options 的区分，见配置说明；工具如何挂入配置留待对应功能设计。

## 本次实现与后续事项

- 规则是普通函数，登记表集中记录触发字段、函数路径和检查范围；实际执行才导入模块。新增规则的完整示例见 [检测说明](src/runtime/validation/README.md)。
- 可调选项与固定约定分开；默认仅根层可设轴，根不必填轴。持续区间采用 [begin,end)，瞬间占一个点，允许首尾衔接。
- 配置缺失、未知规则、规则异常逐项报告，其他检查继续。主动复查直接使用 validate，不制造修改或日志。
- 已声明但未填的字段逐条 warn，open=true 不会掩盖漏填；保留附加内容，不自动改拼写。文本汇集遇到缺 text 也会提示。
- 位置工具用十进制计算并按 axis.precision 落点，默认继承根轴、自有轴优先；原始数据读写和时间筛选不做换算或自动取整。
- 按需导入已解决旧版包入口一次加载全部封装的耦合，保持 from models import Text 等用法。
- 后续推进项目内部工具、视图和明确提出的新用途；不预先增加资源检查或更多字段限制。
- 当前是源码和本地运行验证，尚未做独立 AI 的使用评测。

## 非可视化版本与可视化分支

非可视化核心长期保留并独立使用。`main` 继续开发核心、配置、检测和项目内部小工具；核心的导入与命令行使用不依赖界面或图形环境。

早期非可视化源码基线使用 Git 标签 `core-v0.1.0` 保存，后续核心读写与修复沿 `main` 继续。以后开始可视化时，从当时的主线创建 `visualization` 分支。视图调用核心接口；通用修复与工具回到主线维护，界面依赖留在可视化部分。现在不提前创建空的视图模块。

Git 保存源码、配置、测试和文档；`output/` 的实际数据库、`scratch/`、缓存与本地环境文件不纳入版本。新检出可使用上方初始化命令生成数据库；用户项目数据单独备份。标签保存源码版本，不代表项目数据快照。

## 参考来源

原项目：`D:\AiDefaultWorkSpace\claude\01_项目\2026-10_工具_未命名`。

- 用户原话：`01_企划/03_用户原话_v1.md`
- 层与对象定稿：`01_企划/04_层与对象_v2_定稿.md`
- 封装标准模板：`01_企划/05_封装标准模板_v3.md`
- 原始模板：`01_企划/06_原始模板_v1.md`
- 旧代码：`03_草稿/tool_v0/`

原目录保持原状。当前实现和本轮明确的约定以本项目文件为准，原项目保留作参考。

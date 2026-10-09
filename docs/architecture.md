# LayerWeave 核心与数据约定

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

另有 [Title 类](../src/models/objects/title.py) 和 [标题配置](../configs/objects/title.toml) 作为派生示例；继承 Text 的内容与约定，不新增非空或长度限制，也不新增标题层。

source 目前原样保存，由使用方解释。封装不读取资源，也不新增必填、资源存在性检查或格式白名单。主线、歌词、背景、原画等用途可通过实例名字区分，复用同一种封装。

## 数据库（四张业务表与日志表已实现）

采用 SQLite：

| 表 | 保存内容 |
|---|---|
| projects | id、name、max_id、tips |
| layers | project_id、id、name、type、config_ref、father、axis、tips |
| objects | project_id、id、name、config_ref、layer、begin、end、information、tips |
| binds | 内部 id，来源和目标各自的 kind、project_id、id，以及 tips |
| changes | id、operation_id、created_at、kind、project_id、target_id、action、before_data、after_data、undo_of |

编号与归属：

- 项目编号独立管理；每个项目内部，层和对象共用一套发号器。
- 实体的完整身份为 (project_id, id)。不同项目可重复局部编号，同一项目内层与对象不重号。
- projects.max_id 记录历史上已提交的最大实体编号，初始为 0，删除实体后不回退。项目编号本身不占这个计数，项目表独立自动发号。
- layer／object 是实体种类；text／image 等是封装类型，二者分开。
- 项目归属包含在实体的项目号中，不再另设项目归属关系表。跨项目通过 bind 引用，保留目标完整身份。
- binds 的两端是普通引用，可由检测通道报告失效目标。关联记录有自己的全库递增编号，删除后不复用，不参与项目内实体计数。
- allocate_id() 统一给本项目的层和对象发号，不自行提交。调用方将发号与记录写入放在同一个事务中，整个事务回滚时计数也回滚。
- 两个实体表的主键各自限制同表重号，跨表共享编号由统一发号方法保证；没有额外触发器追踪任意直接 SQL 写入。
- 向已有项目复制/剪切子树使用 transfer_subtree，按目标项目重新发号并返回映射；整项目换号尚未实现。
- 同项目 father、layer 引用可利用项目上下文解释。跨项目 bind 必须明确两端的项目和种类。
- 可视状态暂不持久化。轻量修改历史已使用独立 changes 表，日志不占项目内实体编号，也不对被记录的实体加外键。

存储方式：config_ref 保存相对于 configs/ 的配置路径，给按需装载正确的类提供依据；它是存储元数据，不加进基础类。axis、information 保存为 JSON 文本。层的 objects 和两类的 bind 分别从对象表、关联表反查，不重复保存在实体行里。

已启用项目归属、同项目父层和对象所属层的外键；father 可为 NULL，objects.layer 必须非空。没有级联删除或更新，也没有把时间、环、轴、资源或封装规则写成数据库检测。普通删除不级联；子树删除和跨项目剪切由工具显式编排成一个事务。

存储检查命令（从 src 执行）：

```sh
python -X utf8 -B -m unittest discover -s ../tests -v
```

测试覆盖配置继承、父约定保护、字段类型、区间边界、类型兼容、检测触发范围、逐项继续、批次最终状态、按需导入，以及存储、日志、迁移、完整记录/实例往返、关闭重开和 CLI。使用内存库和专用临时文件，不写入输出数据库。

当前包含工具目录迁移、空档查询、对象跨项目搬移、显式范围、跨界 split/keep/stretch/move、命令目录及帮助、顶层字段撤销等回归在内的 343 项测试通过。JSON 内容变化会区分 `1`、`1.0` 与 `true`，日志、批次最终状态和检测字段选择使用同一比较方式；字典键顺序不产生变化。无变化的字段在 SQL UPDATE 前跳过。

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
- 反馈区分操作与检查：operation.status 为 committed、unchanged、read 或 failed；operation.changes 列出已提交的动作和目标。保留 ok/applied 与 checks，诊断 error 不撤销已提交数据。检测状态仍为 not_run、completed、partial、failed。
- 内置诊断按目标逐条列出，scope 标注本次直接修改、关联检查或主动复查；不推断问题新旧。常见输入错误提供可选值、字段建议或同种配置候选。
- 外键错误仅在 SQL 失败时补充引用原因，正常写入不增加重复存在性检查；失败批次不返回临时成功记录。
- 默认 CLI 与 dispatch 已接入配置规则。可传 checker(changes, read_record) 替换内置检测器；它拿到前后记录与查询入口，一批只调用一次。
- 配置文件不存在不会被 CRUD 额外拦截；config_ref 原样存取，缺失配置由提交后的检测逐条报告 partial，其他目标继续。

## 完整读写

- read_layer/read_object 读取完整记录及发出的关联，层同时装载直属对象；不依赖配置文件可读。
- load_layer/load_object 按每条记录的 config_ref 还原 Python 派生实例，不递归父层、子层或关联目标。
- save_layer/save_object 新增或更新显式传入项；Python 实例按实际类取得配置，字典更新省略 config_ref 时保留原引用。层的 type 从配置取得，事务成功后回填编号。删除仍为显式操作。
- bind 采用包含 kind、project_id、id 的完整来源/目标字典，新建时可只填写目标，由保存入口补齐来源。
- config_ref 与 project_id 保持为存储元数据，不添加到基础类。常规 save 需要可解析的对应配置；缺配置的原始数据仍可通过 dispatch/CRUD 保存，再由检测逐条报告。省略 type 时必须能读取层配置，接口不猜测。

API 参数、保存范围与错误反馈见 [公共 API](../src/runtime/API.md)。源码位置与后续工具开发说明见 [工具指南](../src/tools/README.md)。

第一批四个内部工具为只读功能。第二批六个写入工具复用事务内请求工厂、日志和提交后检测，位置计算与写入使用同一事务。后续已加入复查、历史、撤销、子树删除/复制、分割、插空档，以及同库跨项目子树复制/剪切。视图、Skill／MCP 尚未实现。


## 扩展约定与实现边界

- 本轮通用工具已收尾：补齐空档查询 find_gaps、选中对象跨项目复制/剪切 transfer_objects，统一命令 help 可发现这两个入口。前者只读，后者沿用原数值、关联映射与整批撤销规则。用法见 [工具指南](../src/tools/README.md)。
- 数据库接入与可能的导入扩展单独记录在 [后续可能更新](FUTURE.md)，当前不新增导入工具。

- 规则是普通函数，登记表集中记录触发字段、函数路径和检查范围；实际执行才导入模块。新增规则的完整示例见 [检测说明](../src/runtime/validation/README.md)。
- 可调选项与固定约定分开；默认仅根层可设轴，根不必填轴。持续区间采用 [begin,end)，瞬间占一个点，允许首尾衔接。
- 配置缺失、未知规则、规则异常逐项报告，其他检查继续。主动复查直接使用 validate，不制造修改或日志。
- 约束与汇报等级分开；optional=true 是允许字段缺省的可继承约定，检查仍执行，填入后仍检查类型。模型/动作的 source/data 均可选。configs/logging/diagnostics.toml 设置 error/warn/none，路径覆盖不继承，未配置默认 warn；疑似拼写只建议，不自动改键名。相同配置失败按目标合并，保留受影响检查。
- 常规对象位置写入共用 runtime.positions，按 axis.precision 落点，无精度时默认 1e-6；跨项目迁移和撤销精确保留已有数值。起止、时长与重叠按同一整数刻度比较。修改轴或父层后复查受影响子树的位置关系，不批量重写旧坐标。原始读取与范围筛选不换算单位、不自动取整。
- 按需导入已解决旧版包入口一次加载全部封装的耦合，保持 from models import Text 等用法。
- 后续推进项目内部工具、视图和明确提出的新用途；不预先增加资源检查或更多字段限制。
- 详细展开保留范围内所有层，支持多棵子树去重和 compact 精简视图；缺失编号逐条提示，正文与关联引用保留。

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

# AI 制作工具（暂未命名）

创建日期：2026-10-08。当前状态：六类封装、SQLite 存储与日志、CRUD、配置继承、模块化检测和按需导入已实现。派生 Python 对象还原、工具和视图接入仍待后续。

## 快速开始

当前代码只使用 Python 标准库。本机核对环境为 Python 3.11.3、SQLite 3.40.1。读取 TOML 使用 tomllib；发号语句需要 SQLite 3.35+。

从本项目目录进入 src，运行完整示例：

```sh
cd src
python -X utf8 -B -m examples.crud
```

此示例使用内存数据库，演示创建项目和层、批量创建对象、修改、查询、删除、日志查询、内置配置检测和主动复查，不改动输出数据库。

纯模型示例仍可用：`python -X utf8 -B -m examples.all_layers` 或 `python -X utf8 -B -m examples.text`。其中手动编号和短编号 bind 只演示单项目内存结构。

初始化数据库（同样从 src 目录执行）：

```sh
python -X utf8 -B -m runtime.storage.database ../output/ai-production.sqlite3
```

已提供[可用数据库](output/ai-production.sqlite3)，没有写入示例数据。初始化会补建缺失表，并将旧版 objects.layer 升级为 NOT NULL，保留原数据；存在未归属的旧对象时停止迁移并列出编号，不自动猜测归属。

读取项目列表的 JSON 入口：

```sh
python -X utf8 -B -m runtime.console ../output/ai-production.sqlite3 --request examples/requests/read-projects.json
```

完整请求、批量事务和反馈格式见[运行接口说明](src/runtime/README.md)。

## 按任务找入口

| 要做什么 | 从哪里开始 |
|---|---|
| 理解层的基础结构 | [层基础类](src/models/layers/base.py)、[层基础配置](configs/layers/base.toml) |
| 理解对象的基础结构 | [对象基础类](src/models/objects/base.py)、[对象基础配置](configs/objects/base.toml) |
| 新增一种封装 | 对照 [文字层类](src/models/layers/text.py)、[文字对象类](src/models/objects/text.py)、[层配置](configs/layers/text.toml)、[对象配置](configs/objects/text.toml) |
| 看 CRUD、日志和检测组合 | [完整内存示例](src/examples/crud.py) |
| 看六类模型的创建装载 | [六类组合示例](src/examples/all_layers.py) |
| 修改配置读取与继承 | [配置读取器](src/runtime/configuration/loader.py)、[合并约定](src/runtime/configuration/README.md) |
| 设计工具接入 | [工具占位说明](tools/README.md) |
| 查看表结构与存储操作 | [建表脚本](src/runtime/storage/schema.sql)、[初始化与发号](src/runtime/storage/database.py)、[存储说明](src/runtime/storage/README.md) |
| 调用 CRUD 和查看日志 | [运行接口说明](src/runtime/README.md)、[CRUD](src/runtime/storage/crud.py)、[分流](src/runtime/dispatch.py) |
| 新增约束或主动复查 | [规则登记表](src/runtime/validation/registry.py)、[检测与扩充示例](src/runtime/validation/README.md) |
| 查看全部约束及检测设计 | [约束与触发时点](src/runtime/validation/README.md) |
| 继续实现对象还原 | 先读下方“存储映射待落实” |

新增一个与现有六类同样形式的封装，最少需要四个文件：层类、对象类、层配置、对象配置。配置中的 class 指向实际模块和类；extends 相对于当前配置文件。

可以直接从具体模块导入新增类。若还要支持统一的 `from models import ...` 入口，目前需要同步三个导出文件：`src/models/__init__.py`、`src/models/layers/__init__.py`、`src/models/objects/__init__.py`。这些入口现在只按请求加载对应模块，不导入全部封装。若不需要统一入口，只从具体模块导入即可。

## 核心约定

- 给 AI 用的制作辅助工具：用层、对象组织内容、关系及其在轴上的位置。
- 底层保持精简和自由。Layer、Object 只保存字段和返回自身；检测、配置读取、持久化由外部执行代码承担。
- Layer.type 是类上的层名，name 是创建实例时传入的名字；objects 实际装载对象实例。
- Object.layer 是必传关键字参数，保存时保证非空且层存在。information 是内容字典；Python 类型注解本身不做运行时拦截，所有封装保留 open = true。
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

存储方式：config_ref 保存相对于 configs/ 的配置路径，给后续读回正确的类提供依据；它是存储元数据，不加进基础类。axis、information 保存为 JSON 文本。层的 objects 和两类的 bind 分别从对象表、关联表反查，不重复保存在实体行里。

已启用项目归属、同项目父层和对象所属层的外键；father 可为 NULL，objects.layer 必须非空。没有级联删除或更新，也没有把时间、环、轴、资源或封装规则写成数据库检测。普通删除不级联，项目搬移接口仍待实现。

存储检查命令（从 src 执行）：

```sh
python -X utf8 -B -m unittest discover -s ../tests -v
```

测试覆盖配置继承、父约定保护、字段类型、区间边界、类型兼容、检测触发范围、逐项继续、批次最终状态、按需导入，以及存储、日志、迁移和 CLI。使用内存库和专用临时文件，不写入输出数据库。

## CRUD 与反馈

- create、read、update、delete 面向 project、layer、object、bind；另支持 read(kind="change") 查询日志。
- 层和对象通过 project_id 与 id 定位；项目、关联记录按独立 id 定位。
- read 按 id 返回单条或 null，未传 id 返回筛选列表；第一版支持普通列等值和空值条件。
- update 只修改传入字段，JSON 字段整体替换；身份与计数由系统管理。delete 不级联。记录不存在或数据未变化时不记日志，applied 为 false。
- 分流入口接收字典或字典列表，列表原子提交；使用中的连接不能已有待提交操作。
- 反馈区分 ok/applied 与 checks。检测状态为 not_run、completed、partial、failed；completed 时也可能存在 issues。
- 默认 CLI 与 dispatch 已接入配置规则。可传 checker(changes, read_record) 替换内置检测器；它拿到前后记录与查询入口，一批只调用一次。
- 配置文件不存在不会被 CRUD 额外拦截；config_ref 原样存取，缺失配置由提交后的检测逐条报告 partial，其他目标继续。

## 存储映射待落实

记录级读写已有对应字段，继续实现 Python 模型还原时需要接清楚：

1. 当前纯模型示例的 bind 是短编号形式；CRUD 的 bind 记录已经使用 kind、project_id、id 两端完整字段。把关系装回 Python 实例的格式尚未实现。
2. CRUD 已保存 config_ref 和层的 type 并返回记录字典，JSON 字段已还原；按配置找到并实例化对应 Python 类的适配仍待实现。普通 asdict() 不能单独完成这种还原。

尚未实现的部分为派生 Python 对象还原、完整关系装载、Skill／MCP、视图与工具接入。记录级 CRUD 与配置规则检测已经可用。

## 目录职责

- configs/layers、configs/objects：基础约定与具体封装配置。
- src/models/layers、src/models/objects：Python 类。
- src/examples：模型示例、CRUD 全流程示例和 JSON 请求示例。
- src/runtime/storage：表结构、初始化、发号、CRUD 和事务日志。
- src/runtime/dispatch.py、console.py：分流与 JSON 入口；validation 为模块化规则执行器，configuration 负责配置读取和继承。
- tests：存储、CRUD、事务日志、检测接口及 CLI 检查。
- output：可供使用的 SQLite 数据库。
- tools：工具入口，当前占位。

各分类可继续分子目录。原始模板与通用封装模板 V3 分开理解；配置合并遵循 defaults、固定约定与 options 的区分，见配置说明；工具如何挂入配置留待对应功能设计。

## 本次实现与后续事项

- 规则是普通函数，登记表集中记录触发字段、函数路径和检查范围；实际执行才导入模块。新增规则的完整示例见 [检测说明](src/runtime/validation/README.md)。
- 可调选项与固定约定分开；默认仅根层可设轴，根不必填轴。持续区间采用 [begin,end)，瞬间占一个点，允许首尾衔接。
- 配置缺失、未知规则、规则异常逐项报告，其他检查继续。主动复查直接使用 validate，不制造修改或日志。
- 按需导入已解决旧版包入口一次加载全部封装的耦合，保持 from models import Text 等用法。
- 后续只推进存储还原、工具接入、视图和明确提出的新用途；不预先增加资源检查或更多字段限制。
- 当前是源码和本地运行验证，尚未做独立 AI 的使用评测。

## 非可视化版本与可视化分支

非可视化核心长期保留并独立使用。`main` 继续开发核心、配置、检测和项目内部小工具；核心的导入与命令行使用不依赖界面或图形环境。

当前源码基线使用本地 Git 标签 `core-v0.1.0` 保存。以后开始可视化时，从当时的主线创建 `visualization` 分支。视图调用核心接口；通用修复与工具回到主线维护，界面依赖留在可视化部分。现在不提前创建空的视图模块。

Git 保存源码、配置、测试和文档；`output/` 的实际数据库、`scratch/`、缓存与本地环境文件不纳入版本。新检出可使用上方初始化命令生成数据库；用户项目数据单独备份。标签保存源码版本，不代表项目数据快照。

## 参考来源

原项目：`D:\AiDefaultWorkSpace\claude\01_项目\2026-10_工具_未命名`。

- 用户原话：`01_企划/03_用户原话_v1.md`
- 层与对象定稿：`01_企划/04_层与对象_v2_定稿.md`
- 封装标准模板：`01_企划/05_封装标准模板_v3.md`
- 原始模板：`01_企划/06_原始模板_v1.md`
- 旧代码：`03_草稿/tool_v0/`

原目录保持原状。当前实现和本轮明确的约定以本项目文件为准，原项目保留作参考。

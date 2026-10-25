# LayerWeave 开发指南

本页用于维护 LayerWeave 自身源码：准备环境、定位实现和验证改动。操作项目内容读[使用入口](../src/layerweave/tool/builtin/usage/README.md)；在自己工程中复用公共接口、编写工具或插件读[扩展指南](build-with-layerweave/README.md)。项目用途见[README](../README.md)，边界见[架构说明](architecture.md)。

## 准备环境

需要 Python 3.11+、SQLite 3.35+。基础运行时仅使用标准库；本分支不安装视图或 MCP SDK。源码通过本地可编辑安装导入，修改文件立即生效。

Windows PowerShell 中，在项目根执行：

```powershell
python -X utf8 -m venv .venv
.venv/Scripts/python.exe -X utf8 -m pip install -e .
.venv/Scripts/python.exe -X utf8 -B examples/read_write.py
```

下文的 python 指已安装本项目的解释器。启用虚拟环境后可以直接使用 python；未启用时使用上面的完整路径。其他系统使用各自虚拟环境的 Python 执行同样的 pip 和模块命令。

命令可以从其他工作目录运行。数据库、--data-file 等调用参数中的相对路径相对于调用目录；默认 TOML、内置工具与自带 skills 从 layerweave 包内定位；ZIP 安装默认写当前工作目录的 tool/skills，或由 --skills-root 指定。移动整个源码目录后重新执行可编辑安装。

### 可编辑安装与构建依赖

项目的 pyproject.toml 要求 setuptools>=77.0.3 和 wheel，用于构建及现代许可证元数据；它们不是核心的运行时依赖。pip 默认在临时隔离环境中准备构建依赖，所以当前虚拟环境已有 setuptools，也可能再次联网下载。详细机制见 [pip 构建说明](https://pip.pypa.io/en/stable/reference/build-system/)。

若停在 Installing build dependencies，先查看下载源、代理和网络错误。可在原安装命令中加 -v 查看进度；超时不等于项目源码有错，也不要为迁就旧 setuptools 降低声明中的最低版本。

网络可用或已有本地依赖来源时，可以先在目标虚拟环境准备构建依赖，再复用它们完成可编辑安装：

```powershell
.venv/Scripts/python.exe -X utf8 -m pip install "setuptools>=77.0.3" wheel
.venv/Scripts/python.exe -X utf8 -m pip install --no-build-isolation -e .
```

第一步仍可能联网；离线时需事先备齐适用的依赖 wheel，再通过 pip 的 --no-index 和 --find-links 指定本地目录。--no-build-isolation 只关闭临时构建环境，不会补齐依赖，也不等于禁用网络。只更新当前环境的 setuptools 后继续使用默认隔离安装，仍可能触发下载。

上面的最小安装不含可选 extra。开发验证按需使用本分支提供的 dev；完整分支接入 MCP 时增加 mcp，这些依赖也需提前准备或正常联网获取。普通使用者可安装完整分支的现成 wheel，避免构建 LayerWeave 本身；其可选运行依赖仍需安装。

## 按任务寻找入口

| 要做什么 | 入口 |
|---|---|
| 新增层或对象封装 | [模型](../src/layerweave/models/README.md)、[配置](../src/layerweave/configs/README.md)，参考 [Title](../examples/title.py) |
| 在一个事务中组合多个现成工具 | [事务内组合](build-with-layerweave/04-composing-tools.md)，失败抛出，外层提交与检查 |
| 让视图或缓存连续读取业务变化 | [增量接入](build-with-layerweave/05-incremental-reading.md)，初始快照与后续日志游标 |
| 新增或维护内部工具 | [工具开发](../src/layerweave/tool/builtin/developer/README.md)、[基础 API](../src/layerweave/support/API.md) |
| 设计组件目录、声明服务或定向读取 | [统一 MCP 入口](build-with-layerweave/06-mcp-components.md)、[声明服务](build-with-layerweave/07-declaration-services.md)、[project 分区技巧](build-with-layerweave/tip-project-scopes.md)；执行和路由由上层工具实现 |
| 工具包登记自己的层或对象类型 | [工具包登记类型](../src/layerweave/tool/builtin/developer/TOOL_TYPES.md) |
| 扩充 JSON 交换或新增模板 | [交换开发](../src/layerweave/tool/builtin/usage/exchange/DEVELOPMENT.md)，模板新增文件即发现 |
| 修改结构、事务或存储 | [基础支撑](../src/layerweave/support/README.md)、[表结构](../src/layerweave/support/storage/SCHEMA.md) |
| 给层或对象增加持久字段 | 先看[核心字段扩充前的兼容处理](FUTURE.md#核心字段扩充前的兼容处理待实施)，随字段变更处理旧库、历史快照、模型与配置 |
| 让工具的专属表接入统一管理 | [工具表开发指导](build-with-layerweave/03-managed-tables.md)，复用 register_tables 与现有写会话 |
| 让附着状态随交换复制换号，或复制时跳过 | [逻辑引用与复制策略](build-with-layerweave/03-managed-tables.md#逻辑引用与复制策略)，不增加硬外键 |
| 自定义记录 ID、登记发号规则与簇 | [编号模块](../src/layerweave/support/numbering/README.md)，provided 表或开发者发号接口 |
| 修改内容检测 | [检测包](../src/layerweave/tool/builtin/usage/validation/README.md) |
| 编写或安装外置技能 | [工具区](../src/layerweave/tool/README.md)、[ZIP 安装](../src/layerweave/tool/builtin/developer/SKILLS.md) |
| 管理本地 KEY 或接入其他模型服务的凭据 | [KEY 工具](../src/layerweave/tool/builtin/developer/keys/README.md)，不依赖业务数据库 |
| 声明、登记和核对组件版本 | [版本工具](../src/layerweave/tool/builtin/developer/versions/README.md)，每个完整组件维护自己的 component.toml |
| 修改文档 | [文档约定](documentation.md) |
| 查看尚未实现的候选方向 | [后续可能更新](FUTURE.md)；视图边界单独维护 |

## 源码位置

| 目录 | 职责 |
|---|---|
| [src/layerweave/core](../src/layerweave/core/README.md)、[src/layerweave/models](../src/layerweave/models/README.md) | 抽象结构、纯合并语义、按需导入的基础及派生类 |
| src/layerweave/configs/layers、src/layerweave/configs/objects | 与 Python 类对应的封装约定 |
| src/layerweave/configs/logging | 诊断汇报等级；不保存数据库操作历史 |
| [src/layerweave/support](../src/layerweave/support/README.md) | 存储与配置适配、统一写入、实例装配、CLI 和静态发现 |
| [src/layerweave/support/numbering](../src/layerweave/support/numbering/README.md) | 发号词条、普通规则函数、簇成员和计数恢复；属于基础支撑 |
| src/layerweave/tool/builtin | 可独立增减的完整工具包，按 usage/developer/view/shared 分类 |
| src/layerweave/tool/skills | 外置技能，供层配置中的 tools 引用 |
| examples、tests | 可运行例子、行为回归与隔离验收 |
| docs | 整体设计、开发和文档约定、后续候选 |
| output、scratch | 本地用户数据与交付物、可再生临时材料 |

查现行源码时可使用 `rg 关键词 src/layerweave tests examples docs`。scratch 保留开发备份和临时材料，已被 Git 忽略；递归扫描时排除 scratch、build、.venv，避免把旧副本当作当前实现，不需要为了检索而清理备份。

## 入口路径与调度标识

这些字段服务不同用途；名称相同或写法相似，不代表它们共用一套加载、执行或登记机制。

| 入口或标识 | 在哪里声明、如何定位 | 谁使用它 |
|---|---|---|
| Python API，例如 layerweave.support.api | Python 的 layerweave 包内模块；从任意工作目录导入 | 开发者直接调用，见[公共 API](../src/layerweave/support/API.md) |
| config_ref，例如 objects/title.toml | 相对于 configs 根目录；TOML 内的 extends 则相对于当前配置文件 | 存储和配置读取器，见[配置继承](../src/layerweave/support/configuration/README.md) |
| TOML 的 class，例如 layerweave.models.objects.title:Title | 模块名与类名，由对应封装声明 | 实例装配时导入并还原；与业务记录的名称分开 |
| 层配置 tools 中的 route | 技能文件位置，配合 tier/when；源码、自带安装资源和 ZIP 目标的基准不同 | 供 AI 阅读选择，不自动执行，见[技能定位](../src/layerweave/tool/README.md#选择与定位技能) |
| COMMANDS 的 input_schema、entrypoint、可选 cli 与 mcp | 模块内静态声明输入、入口及接入方式 | help 派生参数说明，MCP 按同一 Schema 与绑定执行；CLI 可省略，见[命令声明](../src/layerweave/tool/builtin/shared/help/COMMANDS.md) |
| PROVIDERS 的角色与函数入口 | 完整工具包的 `__init__.py` 中声明；例如 checker | 显式请求可选能力时查找提供者；默认检测在提交后执行，见[检测包](../src/layerweave/tool/builtin/usage/validation/README.md) |
| 发号词条与 rule | 词条、计数位置、成员保存于数据库；rule 对应本进程登记的函数 | allocate 在当前写会话中调度，见[编号模块](../src/layerweave/support/numbering/README.md) |
| component.toml 的 name | 组件目录内的稳定名称，例如 layerweave.versions；版本由该声明维护 | 版本工具扫描登记与核对，不以名称执行代码，见[版本工具](../src/layerweave/tool/builtin/developer/versions/README.md) |

增加功能时，先选择对应机制：新命令改自身 COMMANDS；技能绑定改层配置 tools；编号扩展登记词条与规则；组件说明改自身 component.toml。工具表的 kind 由 register_tables 登记，用来选择数据表，和上述组件名称、发号词条分别维护。

## 实现原则

1. 模型保存数据；不在构造与赋值时自动检查内容，不增加未经需要的资源解释。
2. 新工具使用 layerweave.support.api 的读取、transaction/run_operation、实例保存和位置计算。一个操作内先读后写共用同一写会话；组合高级工具使用公开 *_in_session 入口，不嵌套独立操作，不复制 SQL、发号或日志。
3. 包内业务代码随包一起增减；不借用另一个可卸载包的私有函数。共用 CLI 使用 layerweave.support.cli；每个命令在本模块声明字面量 COMMANDS，发现和示例排版来自 layerweave.support.commands。
4. 内容检测是可选公开能力。工具通过 layerweave.support.providers.optional_checker 请求默认提供者；没有提供者返回 not_run。基础支撑的 save 默认不接入检测，records 包提供带默认检测的保存函数。
5. 新封装同时提供类与 TOML，保留 config_ref 和 layers/objects 分区。修改继承、身份或恢复时先阅读对应专题和测试。
6. 写入结果与检查结果分开，复用 layerweave.support.feedback。MCP 复用已有事务与诊断，不复制业务规则；core/support 不依赖可选 SDK。当前未发布，不增设旧路径转接。

配置允许自定义说明段；接近内置段名的拼写由内置检测提示，不自动替换。自定义检测需要在规则包里实现和登记，仅写 TOML 不会使它自动生效。新增配置时先按[合并约定](../src/layerweave/support/configuration/README.md#合并约定)判断继承、默认值和允许收紧的项目。

## 验证

从项目根、使用已安装本项目的 Python：

```sh
python -X utf8 -B -m unittest discover -s tests -t . -v
```

test_namespace.py 验证宿主同名模块不会干扰公开导入、保存和还原。test_architecture.py 验证核心单独运行、无工具的支撑读写和 Title 往返、每次仅一个工具包的实际调用、外部目录启动，以及统一写入口的结构保证。隔离进程使用临时副本与 -S，不能借回完整仓库。

本分支按源码开发方式使用，不单独运行发行构建。安装开发依赖后运行以上完整回归；tests/architecture 还验证无工具基础层与各独立工具包。

```sh
python -X utf8 -m pip install -e ".[dev]"
```

按改动运行[示例](examples.md)，核对文档链接与 help。修改共用实现时，与 visualization 分支相同路径逐文件核对，避免维护两套业务逻辑；分支差异限定在视图/MCP 服务是否存在，以及安装元数据、导引与测试范围。

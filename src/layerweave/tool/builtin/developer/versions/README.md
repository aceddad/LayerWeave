# 组件版本登记

扫描 component.toml，有声明就自动登记，按名称与版本完全匹配。扫描范围内不再存在的版本标为失效，旧记录保留；没有声明的组件不登记，也不影响使用。本工具只管理信息，不决定权限、装卸、运行或升级。

## 使用

提供已经初始化的数据库。完成 LayerWeave 安装后，从任意目录执行：

```sh
python -m layerweave.tool.builtin.developer.versions.cli DATABASE sync --json
python -m layerweave.tool.builtin.developer.versions.cli DATABASE read --json
python -m layerweave.tool.builtin.developer.versions.cli DATABASE read --name layerweave.editing --status online
python -m layerweave.tool.builtin.developer.versions.cli DATABASE sync --root ./my-tools --json
```

DATABASE 替换为实际数据库路径。省略 action 时默认 sync，会写入；read 只返回上次登记结果，不扫描文件，也不会在未登记的数据库中建表。JSON 使用标准 operation/ok/data/checks 结构；data.items 是记录，counts 是状态计数。同步结果另有 roots、checked_at、status 和 issues。status=partial 表示部分声明读取失败；ok 仍只表示数据库操作成功，CLI 此时退出 0，并保留问题详情。

Python 的单一分流入口：

```python
from layerweave.tool.builtin.developer.versions import manage_versions

# connection 是已初始化且没有待提交事务的数据库连接。
result = manage_versions(connection)  # 默认扫描并同步
records = manage_versions(connection, "read", name="layerweave.versions")
```

也可直接调用 sync_versions(connection, roots=None) 或 read_versions(connection, name=None, status=None)。前者返回操作反馈；后者只返回 items/counts/registered 数据。

## 声明放在哪里

每个完整组件目录中放 component.toml；示例可直接保存：

```toml
name = "my-team.exporter"
kind = "tool"
version = "0.1.0"
description = "将选定层导出为字幕文件"
changes = "增加字幕文件导出"
```

name 是稳定名称；name/version 是必填非空字符串。kind 默认 tool；description/changes 默认空字符串；自定义字段允许保留在文件中，当前登记器只读取上述五项。所有版本按文本精确匹配，不解析大小顺序，不强制格式。

修改组件后，由维护者或 AI 在本文件更新 version 和 changes，再同步。只改说明会更新原记录；改名称或版本会登记新记录。同名同版本的多个位置合并到一条记录的 sources，说明取本次扫描中按路径排序的首份。代码改动未修改版本号不会被发现。

基础部分的声明位于 layerweave/component.toml，name=layerweave.foundation，core、models 与 support 等基础部分共同维护一个版本。内置工具按完整包声明，包括本版本登记工具。12 个完整工具包与基础部分最初均从 0.1.0 开始，当前版本以各自 component.toml 为准；usage/developer/shared 分类目录、规则子目录不另定版本。visualization 分支另有视图工具包（view），版本从 0.8.0 开始，沿用它在这条分支上的迭代编号（当前以 view/component.toml 为准）。外置 skills 维持自己的说明，只有提供 component.toml 并纳入扫描范围时才加入此登记。

changes 只保存当前版本的简短更新摘要。需要保留历次说明时，在组件目录维护 CHANGELOG.md，不把完整历史累积进每次查询都返回的字段。

pyproject.toml 的 project.version 仍是整个 Python 安装包的发布版本，与基础版本、各工具版本分别表达不同范围。工具版本不从安装包版本推导。

## 扫描范围与状态

默认仅扫描包内基础声明和 tool/builtin 目录。roots/--root 可提供多个目录或单个 component.toml，提供后替换默认范围；目录递归扫描，不进入目录符号链接，不导入或运行被发现的 Python 代码。相对路径相对于调用目录。

| 状态 | 含义 |
|---|---|
| online（在线） | 至少一个已记录位置的最近核对结果为声明存在且可读 |
| inactive（失效） | 所有已记录位置的最近核对结果均为不存在对应名称与版本 |
| unknown（无法核对） | 没有在线位置，但有声明损坏或目录无法读取；具体失败列在本次 issues |

例如同一声明从 0.1.0 改成 0.2.0 后同步，旧行失效、新行在线；两版在不同位置同时存在时都在线。删除声明、组件目录或指定扫描根目录后，同步该范围会标记失效，重新出现会恢复原记录编号。没有声明的普通目录被忽略。

局部扫描只更新本次范围内的位置，其他位置保留上次状态。因此在线表示最近观察到的声明存在，不承诺功能可用，也不是全机实时状态。完整检查时应传入需要管理的全部目录；软件搬家时可同时扫描旧位置与新位置。路径和时间保存在调用方选择的数据库，记录不是全局工具安装清单。

## 表与历史

首次 sync 通过公开 register_tables 声明 component_version，物理表为 tool_component_version，scoped=false。全库独立递增 id，不占用项目 max_id；一行表示一个 name/version，sources 记录各声明文件的绝对路径与最近状态，checked_at 为该行最近一次同步时间（UTC）。

字段为 name、version、kind、description、changes、status、sources、checked_at。版本表里的 changes 是组件更新说明；数据库的 changes 表仍由支撑记录真实写入历史。每次触及记录都会更新核对时间，重复同步不新增版本行，但时间变化会写日志。

同步先扫描，再通过统一写会话提交本批记录；失败共同回滚。表结构登记使用支撑独立的声明事务，数据失败后可能保留空表。现有历史、撤销、通用 CRUD 接口可处理 component_version；本工具不复制这些能力。撤销只恢复登记信息，不改变代码文件，下次同步会重新反映文件状态。

卸掉版本工具后，其他组件照常工作，已有表和日志保留，可继续通过基础 API 读取。基础层不依赖 component.toml 或本工具；想接入其他用途，直接新增声明并选择扫描范围即可。

## 修改实现时从哪里看

| 文件 | 维护内容 |
|---|---|
| [discovery.py](discovery.py) | 扫描 component.toml、定位范围和逐项读取问题 |
| [service.py](service.py) | 工具表声明、自动同步、存在状态和只读查询 |
| [cli.py](cli.py) | CLI、文字展示与同一份 COMMANDS 接口说明 |

增加普通组件只需在组件目录维护声明并纳入扫描范围，无需修改本包的组件名单。实际执行入口继续由组件自己的 Python 接口或 COMMANDS 说明。

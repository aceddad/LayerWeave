# LayerWeave 自身源码导览

先按[案例目录的 uv 步骤](../README.md#准备环境)设置 `$casePython`。本案例的源码定位与演练命令从下方指定的仓库根运行，不从案例目录运行。

从“这个能力在哪里实现”“修改这里还需看什么”“为什么这样分层”进入具体源码。本案例用 LayerWeave 自身的文字对象和标准 bind 保存职责、流程、开发路线与验证依据；完整源码和版本管理继续留在 Git。

包含 **4 个根、7 个层、46 个说明对象、68 条关联**。它是固定提交的人工导览，不是自动源码索引器，也不会随代码变更自动更新。

## 源码基线

| 项目 | 基线 |
|---|---|
| 仓库 | [layer-weave](https://gitee.com/emotion1354414/layer-weave) |
| 分支 | `visualization` |
| 完整 Git SHA | `042ad82c2131ed0e97658a2285e2dd7ce81f6498` |
| 包版本 | `0.7.6`，以 `src/layerweave/__init__.py` 的 `__version__` 为准 |
| 整理日期 | 2026-10-20 |

本提交的 README 约定：`visualization` 提供完整版本；`main` 保留无视图的开发源码、Python/CLI 入口及共用核心、支撑和非视图工具。视图、MCP 服务和发行封装在完整分支维护。本案例没有对另一个分支的当前 HEAD 作逐文件比较。

没有该版本源码时，可取一个单独副本，避免切换正在工作的 checkout：

```sh
git clone --branch visualization --single-branch https://gitee.com/emotion1354414/layer-weave.git code-navigation-source
git -C code-navigation-source switch --detach 042ad82c2131ed0e97658a2285e2dd7ce81f6498
git -C code-navigation-source rev-parse HEAD
```

使用 Python 3.11+，按该副本的 `docs/developer-conventions.md` 准备独立环境和可编辑安装。下文的 `$casePython` 指所选 LayerWeave 环境的解释器；导览内容仍以固定源码基线为准；所有源码相对路径都以该仓库根为基准。只阅读导览不需要 MCP、浏览器或外部服务。

## 导入一个新项目

`project.json` 是交换格式 v1，全部节点为 `op=add`，使用文档内唯一 `key` 和 `refs`。没有预置数据库 ID；再次导入会新增一份内容，不是更新已有案例。交付不依赖预制数据库或外部素材。

以下 PowerShell 命令从仓库根运行。集成后的案例路径是 `examples/showcases/code-navigation`；独立取得本交付时，将 `$navCase` 改为实际 `case` 目录的相对路径。为每次演练选择尚未使用的 `$navRun`。

```powershell
$navCase = "examples/showcases/code-navigation"
$navRun = "scratch/code-navigation-demo"
if (Test-Path -LiteralPath $navRun) { throw "请改用尚未使用的演练目录" }
New-Item -ItemType Directory -Path $navRun | Out-Null
& $casePython -X utf8 -m layerweave.tool.builtin.developer.database.cli "$navRun/navigation.sqlite3"
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply "$navRun/navigation.sqlite3" --data-file "$navCase/project.json" --new-project --result-file "$navRun/import-result.json"
$navImport = Get-Content -Raw -Encoding utf8 "$navRun/import-result.json" | ConvertFrom-Json
$navProjectId = $navImport.data.project_id
$navImport.data.counts
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_overview "$navRun/navigation.sqlite3" $navProjectId
& $casePython -X utf8 -m layerweave.tool.builtin.usage.validation.cli "$navRun/navigation.sqlite3" $navProjectId --json
```

预期 `ok=true`、`operation.status=committed`、`data.status=completed`；节点 `created=121`、`skipped=0`，项目创建另计。概览为 7 层、46 对象、4 根，复查无 error/warn。读取完整反馈里的 `checks` 和 `issues`，不能只看进程退出码。`data.id_map` 将文档 key 对应到本次真实身份；查询得到的 ID 同样可用。

## 根与阅读路线

| 根 | 从哪里读 | 预期获得什么 |
|---|---|---|
| 架构职责 | “抽象核心 · 身份与封装语义”→“支撑 · 公共 API 与统一写入”→“工具 · 可替换业务包” | core/models、support、工具、configs、skills 的边界，以及完整分支的视图/MCP 位置 |
| 执行链路 | “链路一 · 创建并保存文字对象”的 W1–W6 | 入口、配置推断、落点、发号、INSERT、日志、提交、内容检查及输入实例回填 |
| 执行链路 | “链路二 · 记录还原 Python 实例”的 R1–R3 | read 字典与 load 实例的区别，config_ref→TOML→class |
| 执行链路 | “链路三 · JSON 新建带关联项目”的 J1–J5 | 结构准备、节点登记、创建项目、待处理依赖、引用解析及 id_map |
| 开发任务 | 新增封装、增加命令、登记工具表、诊断已提交写入、假设参数修改 | 实际入口、声明、参考实现与相关测试 |
| 设计约定与测试 | 四个“约定”对象和相连的“验证”“参考”“工具”对象 | 有证据的边界、可运行例子、局部查询、复查和撤销入口 |

轴单位是“阅读序号”，第 n 个说明占 `[n,n+1)`；执行子层按本层步骤阅读，共享父根的同一序号单位。位置不表示代码行数、耗时或对象身份。关联文字明确区分“调用”“执行顺序”“依赖”“配置对应”“参考实现”“验证依据”和“相关阅读”。例如日志先于提交是一条顺序关系，不是日志函数直接调用提交。

## 定位对象与回到源码

先概览，再按名字或正文搜索，最后只展开相关对象或子树：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects "$navRun/navigation.sqlite3" $navProjectId --name "任务 · 新增层或对象封装"
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects "$navRun/navigation.sqlite3" $navProjectId --content "Loader.class_config"
```

将查询取得的实际对象编号用于 `query.relations` 和 `query.walk`；层编号取自概览。

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_details DATABASE PROJECT_ID --layer-id LAYER_ID --json
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.relations DATABASE PROJECT_ID object OBJECT_ID --direction both
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk DATABASE PROJECT_ID object OBJECT_ID --max-depth 1
```

这些大写名称都是待替换参数，不是固定 ID。逐步扩大深度，检查 `truncated`，避免一次展开整个关系图。AI 可以先按开发任务或符号搜索，再只读取邻域说明与相应源码。

源码定位的主要维护位置是对象的 `information.source_targets`：

| 自定义说明键 | 含义 |
|---|---|
| `text` | 职责或流程正文，供现有文字详情显示 |
| `navigation_key` | 案例内部检索键，与该文档对象 key 对应；不是数据库身份 |
| `category` | 源码、开发任务、设计约定、假设改动或测试等阅读分类 |
| `source_targets[].path` | 固定提交下的仓库相对路径 |
| `symbol` / `key` / `section` | 分别定位完整 Python 符号、TOML 键或文档章节 |
| `access` | 标记公共入口、工具入口、内部实现、声明、例子或测试；标有 `public via support.api` 时从公共导出使用 |
| `line_hint` | 仅该提交有效的阅读提示；不能代替路径和符号 |
| `evidence_basis` | 证据与案例编排的区别，避免把推测写成作者理由 |
| `review_state` | 人工复查说明；标记不会自动运行检查 |
| `public_entry` | 个别节点提供的公共导入提示 |

这些字段只是开放 `information` 中的说明资料，没有新增运行时接口。`internal` 目标可以阅读，不建议外部扩展依赖其路径。打开对应本机仓库文件后，用完整类/函数名定位；例如 `src/layerweave/support/storage/models.py` 下的 `restore_model`。也可从仓库根运行 `rg -n 'def restore_model' src/layerweave/support/storage/models.py`。同名方法用完整类名区分，如 `Importer._execute`、`Loader.load`。

案例对象跳转使用项目身份与 bind；源码定位使用仓库路径与符号。现有视图不承诺直接打开 IDE、修改代码或监听 Git。

## 五项体验任务

1. **我想新增一种对象类型。** 搜索“任务 · 新增层或对象封装”，沿一跳关联找到“参考 · Title 类、配置与往返示例”“配置 · class、type 与 config_ref”和“验证 · 类与配置身份”。预期找到 `Title` 的定义、`object.class/extends`、`examples/title.py:create_example` 与相关测试方法；新增层则沿同一参考找到 `TextLayer` 和层配置。可用 `config_help objects text title --dev --json` 查看开发说明。

2. **创建文字对象到底写到了哪里。** 从“W1 · Text 与带检查保存入口”进入，按 W2–W6 读源码。预期追到 `_save` 的 `run_operation`、`crud._insert` 发号后插入、`append_change` 写日志，再到 `transaction` 提交；`run_checks` 在其后执行，最后 `_save` 回填实例。基础保存默认不检查，带检查包装默认请求可选检测。可运行 `& $casePython -X utf8 -B examples/read_write.py` 对照往返与日志。

3. **从配置引用追到 Python 类。** 找“R1 · 原始记录读取”和“R2 · 按 config_ref 装配实例”，沿关联到 R3 与配置对象。预期从记录 `objects/text.toml` 找到 TOML 的 `layerweave.models.objects.text:Text`；`read_object` 返回含配置引用的字典，`load_object` 才导入并构造 Text。Title 例子展示派生类型没有被还原成 Text。配置失效时 read 仍可取数据，load 明确报错。

4. **JSON 的 key 如何变成关联端点。** 对照本次 `import-result.json` 的 `data.id_map` 和任意 `project.json` 中的 bind。沿 J1–J5 找到 `_flatten` 将 key 登记到节点、`_execute` 创建后设置 `identity`、`_resolve` 读取这个身份、`_payload` 填入 bind 完整端点。前向引用会 Pending 后重试；无法解开的依赖会跳过并报告，不猜编号。项目创建和工具表结构准备分别看，不把两者混作一个可撤销阶段。

5. **评估命令参数修改，并修改说明后撤销。** 搜索“假设修改 · 沿读增加 include_records 参数”，它标为“需复查”。直接核对沿读函数、CLI 透传、COMMANDS schema/返回/例子及“验证 · 命令声明与沿读行为”；MCP 与视图标为相关阅读，不能仅凭此图断言影响已穷尽。`include_records` 是假设，本版本没有实现。随后在临时案例库里运行下方演练，确认说明恢复且身份和双向关联保持不变。

将以下代码保存为演练目录中的 `review_and_undo.py`，运行 `& $casePython -X utf8 -B review_and_undo.py DATABASE PROJECT_ID`（脚本路径按实际位置填写）：

```python
from contextlib import closing
from copy import deepcopy
import sys
from layerweave.support.api import open_database, read_object, read_bindings
from layerweave.tool.builtin.usage.query.find_objects import find_objects
from layerweave.tool.builtin.usage.records.save import save_object_with_checks
from layerweave.tool.builtin.usage.undo.service import undo_operation

database, project_id = sys.argv[1], int(sys.argv[2])
with closing(open_database(database)) as connection:
    matches = find_objects(connection, project_id,
                           name="假设修改 · 沿读增加 include_records 参数")
    assert len(matches) == 1, "需要在单份案例项目内操作"
    object_id = matches[0]["id"]
    original = read_object(connection, project_id, object_id)
    bindings = read_bindings(connection, "object", project_id,
                             object_id, direction="both")
    information = deepcopy(original["information"])
    information["text"] += "\n演练：已经复核声明入口。"
    information["review_state"] = "演练已复核，随后撤销"
    changed = save_object_with_checks(connection, project_id,
                                     {"id": object_id, "information": information})
    assert changed["ok"] and changed["applied"], changed
    print("修改操作", changed["operation_id"], changed["checks"])
    undone = undo_operation(connection, changed["operation_id"])
    assert undone["ok"], undone
    assert read_object(connection, project_id, object_id) == original
    assert read_bindings(connection, "object", project_id, object_id,
                         direction="both") == bindings
    print("说明已恢复，身份与关系保持不变", project_id, object_id)
```

先复制完整 `information` 再改其中的键，因为它是整体替换字段。撤销产生新的历史，不清空已有日志，也不倒退发号计数。共享使用时如遇后来修改冲突，应先阅读撤销反馈。

## 在画布里读

完整分支的视图可打开同一个临时案例库。四个根对应四块画板；在“开发任务”中点说明对象，在详情里查看关系，再从“沿读”逐跳读相邻说明，“去看”定位相关案例对象。当前指南入口是 `src/layerweave/tool/builtin/view/GUIDE.md` 的“此刻”“沿读”“关系线”。不需要额外图像或插件才能保存和查询本案例的关系。

该基线的视图 CLI 没有状态目录参数。需要把演练状态也隔离时，可将下面代码保存到演练目录，运行 `& $casePython -X utf8 -B open_demo_view.py DATABASE PROJECT_ID STATE_DIRECTORY`。端口由系统分配，状态目录使用演练目录下的新子目录；打开打印的本机地址，Ctrl+C 关闭自己启动的服务。

```python
from pathlib import Path
import sys
from layerweave.tool.builtin.view.server import make_server

# 此固定版本的视图内部辅助入口，不是 support.api 的稳定公共接口。
server, url = make_server(Path(sys.argv[1]), port=0,
                          state_root=Path(sys.argv[3]))
print(url + "?project=" + str(int(sys.argv[2])), flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
```

## 维护

更新到新提交时，先记录新 SHA，再逐对象复核 `source_targets`、调用方向、配置含义与正文；复查三条执行链路和五项体验任务。定位与正文以 `project.json` 的对象记录为主，不手工维护第二套全量源码索引。README 只维护入口与使用说明。对已有导览修改使用原身份的 update；需要可移植的新建副本时用交换工具的 `op=add` 导出，勿把临时数据库固定编号当跨库引用。

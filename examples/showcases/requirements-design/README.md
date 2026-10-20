# 声隅：社区录音舱预约

先按[案例目录的 uv 步骤](../README.md#准备环境)设置 `$casePython`，再进入本案例目录执行以下 PowerShell 命令。

一个用于需求与设计审阅的原创虚构案例。居民查看空闲时间、确认预约、在开始前取消；评审者沿关联检查需求覆盖，并判断“单次 30 分钟改为 60 分钟”会影响哪些设计与验收。

交付包含完整交换数据与 3 张可编辑 SVG 草图。**录音舱应用尚未实现，10 条产品验收均为“未执行”。** 数据能导入、关联存在、草图能打开，都不表示产品功能已通过测试。

## 内容与阅读入口

| 根 | 内容 | 定位名称 |
|---|---|---|
| 背景与场景 | 使用者、目标、营业时间、时区、范围和 3 个场景 | B01 一间录音舱的预约边界；S01–S03 |
| 需求 | 6 条已定义需求，1 条刻意待决需求 | R01–R07 |
| 设计说明 | 3 项设计及 1 项未完成设计的边界说明 | D01–D04 |
| 界面草图 | 选择时段、核对提交、我的预约与取消 | UI01–UI03 |
| 验收 | 每条都含前提、步骤、预期与执行状态 | A01–A10 |
| 待决与变更 | 迟到策略问题、时长变更的两个备选方案 | Q01、C01 |

共 6 层、30 个对象、64 条标准关联。序号轴上的 `[n,n+1)` 只是阅读位置，和预约时间、数据库编号无关。对象名中的 R02 等是稳定的案例名称，不是数据库 ID。

| 需求 | 设计 → 草图 | 验收规格 |
|---|---|---|
| R01 看清可预约时段 | D01 → UI01 | A01、A09 |
| R02 原子占用一个时段 | D02 → UI02 | A02、A03、A07、A08、A09 |
| R03 每人只保留一条有效预约 | D01、D02 → UI01、UI02 | A04、A06 |
| R04 开始前确认取消 | D03 → UI03 | A05、A06 |
| R05 查看可信的预约状态 | D03 → UI03 | A02、A05、A06、A09 |
| R06 维护时段不可占用 | D01、D02 → UI01、UI02 | A01、A07 |
| R07 迟到保留与释放规则 | D04 → UI03（只标记缺口） | A10（被 Q01 阻塞） |

关系方向：场景 → 需求；需求 → 设计、验收；设计 → 草图；R07 → Q01；Q01 → 被阻塞的设计与验收；C01 → 需要复查的对象。关系说明在 `bind.tips`。一项设计可以响应多条需求，一条需求可以有多个验收场景。状态字段与关系是内容约定，软件不会据此自动认证“需求已实现”。

## 准备与导入

需要可运行 LayerWeave CLI 的 Python 环境，接口以所用版本的 `--help` 为准；本案例采用 0.7.6 的交换格式 v1。导入、查询、修改、复查与撤销使用普通 Python/CLI 即可，不需要 visualization。可先运行：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli --help
```

以下是 PowerShell 7（UTF-8）命令。从本 `case/` 目录开始，把整个目录复制到新的练习目录，数据库与 `assets/` 同级。不要只复制 JSON：交换工具不会搬运媒体文件。相对素材路径以**数据库所在目录**为基准。

```powershell
$practice = Join-Path (Split-Path (Get-Location).Path -Parent) 'requirements-practice'
if (Test-Path -LiteralPath $practice) { throw '请选一个尚不存在的练习目录' }
Copy-Item -LiteralPath (Get-Location).Path -Destination $practice -Recurse
Set-Location -LiteralPath $practice

& $casePython -X utf8 -m layerweave.tool.builtin.developer.database.cli case.sqlite3
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply case.sqlite3 --data-file project.json --new-project --result-file import-result.json
$import = Get-Content -Raw -Encoding UTF8 import-result.json | ConvertFrom-Json
$projectId = $import.data.project_id
$import.data.counts
$import.data.issues
$import.checks
```

本文件全部使用 `op=add`、唯一 `key` 和 `refs`，由目标库分配身份。正常结果应为 `ok=true`、`data.status=completed`、`created=100`、`skipped=0`（100=6 层+30 对象+64 关联，不含项目）。同时读取 `checks`；不要只看提交成功。重复导入会新增另一套内容。

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_overview case.sqlite3 $projectId
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_details case.sqlite3 $projectId --compact --json
& $casePython -X utf8 -m layerweave.tool.builtin.usage.validation.cli case.sqlite3 $projectId --json
```

下面各步延续同一 PowerShell 会话。用查询结果取实际 ID，不沿用其他数据库编号。

## 五个体验任务

### 1. 从一条需求找到草图和验收

```powershell
$r02 = @(& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects case.sqlite3 $projectId --name 'R02 原子占用一个时段' | ConvertFrom-Json)[0]
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk case.sqlite3 $projectId object $r02.id --direction outgoing --max-depth 2
```

预期找到 D02，再到 UI02；同时看到 A02、A03、A07、A08、A09 的前提、步骤和预期。它们分别覆盖成功、竞争、维护变化、重试、时间边界。打开 [UI02 核对并提交预约](assets/02-confirm.svg)，对照提交分支。返回结果的 `truncated` 应为 false；有数量截断时应扩大范围，而不是把未返回对象当作遗漏。

### 2. 发现刻意保留的决策缺口

```powershell
$r07 = @(& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects case.sqlite3 $projectId --name 'R07 迟到保留与释放规则' | ConvertFrom-Json)[0]
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk case.sqlite3 $projectId object $r07.id --direction outgoing --max-depth 2
```

预期看到 Q01、D04、A10，以及 UI03 的黄色评审注释。缺少的决策是：整段保留，还是有可信签到信号后按宽限期释放；还需确定时间、通知与争议处理。R07 的 `intentional_gap=true`、D04 的阻塞说明和 A10 的未决预期共同表明这是教学缺口。即使复查无错误也不能把它视为设计已完成。

### 3. 从界面反查多条需求

```powershell
$ui01 = @(& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects case.sqlite3 $projectId --name 'UI01 选日期与时段' | ConvertFrom-Json)[0]
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk case.sqlite3 $projectId object $ui01.id --direction incoming --max-depth 2
```

打开 [UI01 选日期与时段](assets/01-availability.svg)。预期沿入向找到 D01，以及 R01 的状态展示、R03 的个人配额、R06 的维护限制。结果还会出现 C01，因为这项变更也要求复查 D01；它不是新增需求。

### 4. 在临时副本修改需求、评估影响并撤销

先阅读 C01“单次改为六十分钟的备选评审”。方案 A 为统一 60 分钟、每半小时可开始、连续两档原子占用；方案 B 允许 30/60 分钟选择。两者均未批准。演练采用 A，只修改 R02，让关联帮助找出尚需复查的其他内容。

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.relations case.sqlite3 $projectId object $r02.id --direction both > before-relations.json
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli export case.sqlite3 $projectId --object-ids $r02.id --include-baseline --no-tools --output r02-change.json
```

用下面的普通 Python 代码修改导出的文件，保留导出的 ID、归属、摘要和全部其他信息；不修改 `project.json`。

```powershell
@'
import json
from pathlib import Path
p = Path('r02-change.json')
d = json.loads(p.read_text(encoding='utf-8'))
def visit(items):
    for n in items:
        info = n.get('data', {}).get('information', {})
        if info.get('source_key') == 'R02':
            info['text'] = info['text'].replace('固定 30 分钟', '固定 60 分钟', 1)
            info['text'] += '\n演练方案 A：连续两档整体占用；20:00 为最后合法起始；旧预约保留原时长；配额仍按一条预约。仅修改需求，设计与验收待复查。'
            info['duration_minutes'] = 60
            info['revision'] = 'exercise-A'
        visit(n.get('children', []))
visit(d.get('items', []))
p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
'@ | & $casePython -X utf8 -
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply case.sqlite3 --data-file r02-change.json --result-file change-result.json
$change = Get-Content -Raw -Encoding UTF8 change-result.json | ConvertFrom-Json
if (-not $change.ok -or $change.data.status -ne 'completed') { throw '更新未完整执行，请先检查反馈' }

$c01 = @(& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects case.sqlite3 $projectId --name 'C01 单次改为六十分钟的备选评审' | ConvertFrom-Json)[0]
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk case.sqlite3 $projectId object $c01.id --direction outgoing --max-depth 2
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects case.sqlite3 $projectId --name 'R02 原子占用一个时段'
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.relations case.sqlite3 $projectId object $r02.id --direction both > after-relations.json
Compare-Object (Get-Content before-relations.json) (Get-Content after-relations.json)
```

预期 R02 身份不变、时长变为 60、关系文件比较无差异。C01 的两步出向范围给出 D01–D03、UI01–UI03、A01–A09 和 R01–R06；C01 正文逐项解释影响。重点检查两档部分重叠竞争、取消同时释放两档、维护命中任一半档、20:00 最后起始，以及旧 30 分钟预约的保留。D04/A10 的待决问题仍未解决。

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.undo.cli case.sqlite3 $change.operation_id --json
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects case.sqlite3 $projectId --name 'R02 原子占用一个时段'
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.relations case.sqlite3 $projectId object $r02.id --direction both > restored-relations.json
Compare-Object (Get-Content before-relations.json) (Get-Content restored-relations.json)
& $casePython -X utf8 -m layerweave.tool.builtin.usage.validation.cli case.sqlite3 $projectId --json
```

预期原 ID、原正文、`duration_minutes=30`、`revision=baseline-v1` 和原有关联恢复。只撤销本次更新，不撤销整个初次导入；不要用其他操作编号替代 `$change.operation_id`。

### 5. 区分数据验证与产品验收

查询 A01–A10 的 `execution_status`，全部应为“未执行”。A10 额外被 Q01 阻塞。LayerWeave 的导入反馈和 `recheck` 负责当前数据与配置检查；SVG 打开检查负责素材可读性；它们都不会运行录音舱服务端的并发、权限、维护或取消逻辑。只有未来实现产品并实际执行对应步骤后，才能记录产品测试结果。

## 草图、编辑与可选视图

- [UI01 选日期与时段](assets/01-availability.svg)
- [UI02 核对并提交预约](assets/02-confirm.svg)
- [UI03 我的预约与取消](assets/03-my-booking.svg)

三份 SVG 同时是可打开素材与可编辑矢量源文件；可用浏览器查看、文本编辑器或矢量编辑器修改。它们是静态设计稿，按钮不执行预约。来源与使用说明见 [素材说明](assets/README.md)。编辑 SVG 不属于数据库撤销范围。

visualization 完整版用于 LayerWeave 画布、素材预览和关系侧栏；普通 CLI 版不包含这些视图。可选截图需本机 Chrome/Edge/Chromium，且完整版本已包含可用的前端资源。不需要付费服务、模型或素材。

如已安装完整版，可生成使用独立设置目录的画布截图（工具会启动并关闭自己的临时本机服务与无界面浏览器）：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.view.screenshot case.sqlite3 $projectId review.png --layers '界面草图' --tree --state-root ./view-state
```

如需交互查看，可用一个未占用的端口启动当前练习库：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.view.server case.sqlite3 --project $projectId --port 8877
```

打开命令返回的地址；不要停止其他项目的服务。画布视图是附加阅读方式，以上五个任务不依赖它。

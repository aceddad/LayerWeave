# 雾灯留给谁

先按[案例目录的 uv 步骤](../README.md#准备环境)设置 `$casePython`，再进入本案例目录执行以下 PowerShell 命令。

雨夜，白礁灯塔即将退役，最后一班补给船仍在雾里。你是来协助交接的维护员：旧塔最后一晚的光，应当照向哪里？

这是一个原创分支阅读与剧情审阅案例。7 个场景、11 个动作、2 项状态、3 个完整结局，单条路线约 10–15 分钟。用现有 LayerWeave 对象详情、关系跳转和“沿读”阅读；也可以只用 Python/CLI 查询。无需另建网页或安装游戏引擎。

## 文件与内容

- `project.json`：完整正文、条件、人物与物品、路径说明，以及连接它们的 bind；导入后可编辑。
- `paths.md`：三条逐步阅读路径及修改条件的检查清单，含剧透。

项目分为“01 场景”“02 选择与条件”“03 人物与线索”“04 结局”“05 路径与修改审阅”五个序号根层。每层第 n 项占 `[n,n+1)`；编号仅用于排布。剧情通过“场景 → 动作 → 场景/结局”关联连接，父链不表达剧情，也没有回环。对象名中的 S01、A06 等是稳定的阅读标签，不是数据库 ID。

正文由本案例原创，无外部文章、图片、音频、字体或素材路径，无需下载资源。无需 FFmpeg、付费服务或模型调用。

## 准备与导入

需要可运行 LayerWeave 的 Python 环境；以下命令适用于 0.7.6 接口。纯文本导入、查询、编辑、复查和撤销用普通版即可；网页画布与 `view.*` 命令需要 **visualization 完整版**。现有安装不含视图时，可以照下面的 CLI 路线完成所有阅读与审阅任务。

先把整个 `case/` 复制到自己的工作目录，进入副本后运行以下命令。数据库也放在这个副本根目录。将来添加媒体时，`information.source` 相对数据库目录解析，交换工具不会复制媒体。

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.developer.database.cli story.sqlite3
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply story.sqlite3 --data-file project.json --new-project --result-file import-result.json
```

检查 `import-result.json`：`ok=true`、`data.status=completed`、`counts.skipped=0`，共创建 5 层、30 对象、42 条 bind（节点共 77 个；项目另计）。同时检查 `checks`，写入成功不等于内容检查通过。`data.project_id` 是实际项目号；`data.id_map` 保存 key 与新身份的映射。不要预设项目号或对象号。再次导入这份 add 文件会另建项目，不能用于更新既有案例。

PowerShell 可这样取项目号、查看目录及入口：

```powershell
$imported = Get-Content -Raw -Encoding utf8 ./import-result.json | ConvertFrom-Json
$storyProject = $imported.data.project_id
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_overview story.sqlite3 $storyProject
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects story.sqlite3 $storyProject --name 'S01｜'
& $casePython -X utf8 -m layerweave.tool.builtin.usage.validation.cli story.sqlite3 $storyProject --json
```

### 在现有网页里阅读

visualization 完整版中运行：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.view.server story.sqlite3 --project $storyProject --port 0
```

`--port 0` 由系统选择空闲端口。打开终端打印的本机地址。顶栏搜索 `S01｜`，按回车定位对象，打开“此刻”中的对象详情；读正文后，在关系列表中选择标注“可选动作”的关联，再从动作详情中的“进入场景”关联跳到目的地。这些是现有对象关系链接。

比较路线时，在对象详情点“沿读”，方向设为“它指着谁”，步数先设 **1**。点“去看”定位目标，或“从这里读”继续下一步。作者可勾选顶栏“关系线”查看分支与汇合。选择全层显示时，编号相近的条目未必互相连通，始终以关联说明为准。

条件由你解释。画布不会检查物品、禁用关系链接、替你记状态或保存游戏进度。只有执行选定动作才改变状态；点开资料条目不算取得物品。每次从 S01 重新开始时，手动把 `tide_code`、`brass_key` 都记为 false。详见项目中的 `R00｜阅读约定与两项状态`。

### 不打开网页也能阅读

从 `find_objects` 的返回结果取得对象 ID，替换下方 `OBJECT_ID`，项目号同上：

```text
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.relations story.sqlite3 PROJECT_ID object OBJECT_ID --direction outgoing
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk story.sqlite3 PROJECT_ID object OBJECT_ID --max-depth 1 --direction outgoing
```

第一条列出出向关联及目标身份；第二条读取起点和一步关联的正文。只沿“可选动作”“进入场景”“进入结局”走故事，不沿“条件依据”“人物登场”等资料关联移动。将目标 ID 作为下一次起点，反复查询即可读到结局。

## 五个体验任务

1. **走一条完整路线。** 定位 `S01｜熄灯前的堤岸`，任选 A01 或 A02，经动作详情前进，直到 E01/E02/E03。预期：每次场景切换都经过一个具名动作；结局有完整正文且没有剧情出边。想要对照时打开 `paths.md`。
2. **查找门槛及取得位置。** 定位 `A06｜凭暗码和钥匙打开检修窗`，核对“双条件”。沿“条件依据”找到 R01/R02，再沿“线索出现位置”“物品出现位置”定位 S02/S03。预期：A03/A04 取得暗码，A05 取得钥匙；直接从 S01 去 S03 只能取得钥匙，不能合法选择 A06。
3. **查看汇合。** 定位 `S04｜旋梯口的两扇门`，查看入向关系，或在沿读里选“谁指着它”。预期：A04（直接从档案小屋上塔）和 A05（从守塔人处上塔）都以“进入场景”指向同一个 S04。汇合保留原状态，不自动补齐物品。
4. **比较结局。** 定位 E01、E02、E03，结合 P01/P02/P03 阅读。E01 要双条件并选 A06、A08、A09；E02 和 E03 都从 S06 出发，分别选择 A10、A11，无物品门槛。持有两件物品仍可主动选择后两种结局。
5. **修改并撤销一条条件。** 按下节在临时副本更新 A06；依 `P04｜把 A06 改宽之后检查什么` 和 `paths.md` 重新走查。预期：放宽到“只需钥匙”后，多出一条不掌握暗码却在 S05 使用暗码的矛盾路线；撤销后恢复原条件，对象身份与所有关联不变。

## 在临时副本修改 A06 并撤销

在新的练习目录中重新复制本案例、初始化数据库并导入。不要在自己的正式项目中练习；关闭针对练习库的服务后再复制数据库。用前面的查询命令取得 A06 的实际对象 ID，然后执行：

```text
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli export story.sqlite3 PROJECT_ID --object-ids A06_OBJECT_ID --include-baseline --output condition-change.json
```

用文本编辑器打开 `condition-change.json`：仅保留目标 A06 对象的 `op=update`，项目、层等上下文不设 op；删除本次文件中的 `records`（这表示不处理关联，不会删掉数据库关联）。保留 A06 的 `id`、`base`、归属和其余 data，仅修改 `data.information` 中这两处，其余 information 字段完整保留：

- `text` 的条件行改为 `条件：brass_key=true；本次练习暂不要求 tide_code。`。
- `requires` 改为 `{"brass_key": true}`。

```text
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply story.sqlite3 --project-id PROJECT_ID --data-file condition-change.json --result-file condition-result.json
```

`information` 整体替换，勿仅提交一条条件而丢掉正文。确认本次只有 A06 更新，然后记录返回的完整 `operation_id`。按 `paths.md` 检查三条原路线和新增的“只有钥匙 → A06”反例。检查器不会理解剧情矛盾，因此仍需人工审阅。比较更新前后的 ID、层、位置、入向“可选动作”、出向“进入场景”和两条“条件依据”关系。

```text
& $casePython -X utf8 -m layerweave.tool.builtin.usage.undo.cli story.sqlite3 OPERATION_ID --json
```

撤销后再查询 A06，确认原 text、双条件 requires 和所有关联完整恢复，P01/P02/P03 仍可到达原结局，“只有钥匙 → A06”再次不满足条件。撤销针对这次独立更新，不能拿导入操作号代替。

# 写得更快以后，谁来证明改动值得合入？

先按[案例目录的 uv 步骤](../README.md#准备环境)设置 `$casePython`，再进入本案例目录执行以下 PowerShell 命令。

这是一个以两篇工程文章为主题的 LayerWeave 精读案例。用完整中文短论练习从结论追溯依据、区分作者陈述与读者推断，并保留可讨论的论证边界。

**正文范围：**[article.md](assets/article.md) 是本案例原创的 10 段中文对读短论，P01—P10 逐段原样存入项目，约 1,350 字。它不是两篇英文文章的全文或译文。外部原文通过 S01/S02 打开，证据卡 E01—E04 提供网页定位词。阅读外部全文需要联网。

- [A：How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/)，2026-10-15。
- [B：Maintaining software with the GPT-6 family](https://developers.openai.com/blog/maintaining-software-with-the-gpt-6-family)，2026-10-14。

原创正文、解读、脚本与 SVG 可随案例分发和修改；外部文章权利归相应权利人。本包不转载外部全文或原图。来源核验日期为 2026-10-20。

## 文件与准备

保留整个目录结构：

```text
article-reading/
  README.md
  project.json
  explore.py
  assets/
    article.md
    argument-map.svg
    cost-boundary.svg
```

需要 Python 和已安装的 LayerWeave；本案例使用交换格式 v1，以 LayerWeave 0.7.8 验证。导入、查询、五个阅读任务、复查均使用基础 Python/CLI 工具，无需 visualization、模型服务或 API key。`explore.py` 仅依赖 Python 标准库及 LayerWeave 的公共查询工具，并以只读方式打开数据库。

画布、图片预览、关系线和拖动画板需要 **visualization 完整版**。SVG 也可以直接用浏览器打开，无需图片插件。讨论使用普通文字对象与关联，基础版可读；它们不是视图中的原生批注楼。

## 导入新项目

先把整个 `article-reading/` 复制到自己的工作目录，再在副本根目录运行以下 PowerShell 命令。数据库与 `assets/` 同级；素材路径相对于数据库目录解析，导入器不会复制媒体。

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.developer.database.cli reading.sqlite3
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply reading.sqlite3 --data-file project.json --new-project --result-file import-result.json
$caseImport = Get-Content -Raw -Encoding utf8 import-result.json | ConvertFrom-Json
$caseProjectId = $caseImport.data.project_id
if (-not $caseImport.ok -or $caseImport.data.status -ne 'completed' -or $caseImport.data.counts.skipped -ne 0) { throw '导入不完整，请检查 import-result.json' }
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_overview reading.sqlite3 $caseProjectId
& $casePython -X utf8 -m layerweave.tool.builtin.usage.validation.cli reading.sqlite3 $caseProjectId --json
```

应看到 8 个根层、32 个对象、68 条关联；导入节点计数为 108，项目创建另计，跳过数为 0。复查应无诊断。所有新增节点使用 `op=add`、唯一 key 与 refs，数据库身份由程序发放。再次导入会新建一份项目，不是更新。

其他终端中，同样运行两条导入命令，然后从 `import-result.json` 读取实际项目编号并传给后续 `--project`；不要把 P02、C01 等标签当作数据库 ID。

## 内容组织

| 根层 | 对象 | 用途 |
|---|---|---|
| 正文｜原创对读短论 | P01—P10 | 完整自然段，包含观察、推论、质疑与结论 |
| 解读｜读者如何理解 | I01—I05 | 一条解读可以解释多个段落 |
| 论点｜跨段命题 | C01—C03 | 结论、成本边界与推广条件 |
| 证据｜来源与可证明范围 | E01—E04 | 陈述出处、定位词、证据类型和推断边界 |
| 转折｜推理强度变化 | T01—T03 | 从观察到归纳，从质疑到试验 |
| 资料｜两篇外部原文 | S01—S02 | 原文链接、作者、发布日期 |
| 配图｜原创论证示意 | G01—G02 | 两幅可打开、可编辑的 SVG |
| 讨论｜锚定具体对象 | D01—D03 | 未解决问题，通过关联指向正文和依据 |

各根使用独立的序号轴，精度都是 1，第 n 项占 `[n,n+1)`。段落序号、解读序号和图序号各有含义；同一数值不表示语义对应，也不表示秒数。论点跨段通过关联表达，不用时间跨度模拟。

`information.attribution` 标明陈述归属；正文里还用 `[A]`/`[B]` 标出来源转述。P04 的跨文结构、P06 的反例、P09 的试验建议均由本案例作者提出。图也是读者绘制的论证示意。

## 五条阅读路线

下面命令延续导入步骤中的 `$caseProjectId`。每次按对象名称取得实际 ID，再沿关联读取局部内容；加 `--json` 可查看所有节点、关联两端和关系说明。

### 1. 从结论找两条不同依据

```powershell
& $casePython -X utf8 explore.py reading.sqlite3 --project $caseProjectId --task 1
```

定位 **C01 全文结论：可核查提案值得试验**，沿“观察依据 A/B”分别到 **P02 审查文章的实践观察**与 **P03 维护文章的取证观察**。P04 是推论桥梁，P10 是结论落点，C03 限制推广。预期：6 个局部节点，不能把观察误读为因果证明。

### 2. 从正文跳到解释和图

```powershell
& $casePython -X utf8 explore.py reading.sqlite3 --project $caseProjectId --task 2
```

从 **P02** 沿“阅读下一步”到 **I02 观察与解释的分界**和 **G01 从两条观察到有条件结论**；E01 是来源核查入口。打开 [论证结构图](assets/argument-map.svg)。预期：4 个节点，图中两条观察在 P04 汇合，结论仍带适用条件。

### 3. 区分作者明确陈述与读者推断

```powershell
& $casePython -X utf8 explore.py reading.sqlite3 --project $caseProjectId --task 3
```

从 **I02** 读 **P02/P03** 的正文与 `attribution`，再到 **E01/E03** 核对出处。需要外文上下文时，打开证据卡的 `url`，用 `locator` 查找。预期：来源简述和本文解释有明确边界；本文的统一提案结构没有被归给任一家作者。

### 4. 定位薄弱论证与具体批评

```powershell
& $casePython -X utf8 explore.py reading.sqlite3 --project $caseProjectId --task 4
```

从 **D01 质疑：相关变化能证明因果吗** 到 **P07 实践结果离因果证明还有距离**、**P02** 与 **E01**，再经 E01 到 S01。预期：讨论指向具体数据和具体推论，问题仍为 open；没有伪造对照实验。还可查 **D03**，阅读本文试点建议本身的薄弱处。

### 5. 不读全项目，只解释一个论点

```powershell
& $casePython -X utf8 explore.py reading.sqlite3 --project $caseProjectId --task 5 --json
```

起点 **C02 模型账单不是完整工程成本**，只读出向一跳：P05、P08、E04、I04、D02、G02，连同起点共 7 个对象、6 条关联。这里不会调用全项目详情，也不会展开其他正文。预期解释：E04 提供的是有范围的 API 成本与发现数量；人工核验、返工等数据尚缺，不能据此排名总工程成本。打开 [成本边界图](assets/cost-boundary.svg) 对照。

## 并排阅读与图形视图

使用 visualization 完整版，在同一个副本目录运行：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.view.server reading.sqlite3 --project $caseProjectId --port 8876
```

若该端口已被使用，另选空闲端口，不要停止已有服务。打开命令打印的本机地址。

1. 在目录中定位“正文｜原创对读短论”和“解读｜读者如何理解”，拖动画板标题，把正文放左、解读放右；这是空间摆放，不执行“左右接续”。两根轴的单位不同，不需要拼成共享轴。
2. 先读 P01/P04 与 I01，再读 P02/P03 与 I02；后者是一条解读对应两段正文，无需逐段机械对齐。
3. 选 P02，在“此刻”详情中沿关联选择 I02、G01 或 E01；要返回原位置，沿入向关联或目录选择即可。图对象详情使用实际素材文件。
4. 接着对读 P05/P08 与 I04、G02、D02，最后读 P09/P10 与 I05、D03。讨论所在根是普通可见文字层，可以像其他对象一样选中并沿关联定位。

在 C02 的详情中点“沿读”，选择“它指着谁”、步数 1，可在图形界面复现任务 5 的七对象局部阅读。

本案例没有预设画板排版；共享布局可通过现有导出工具随项目保存，个人视图状态保留在本机。语义关联保存在项目内，移动画板不会改变它们。文字在画布色块中可能被截短，选中后的详情与 CLI 读取包含完整正文。

## 编辑与保留身份

编辑解读或讨论时，先用 `find_objects` 按名称取得实际 ID，再更新该对象，保留关联。`source_key` 是内容稳定键；`information` 更新是整个字段替换，应带上原有归属等信息。通过写入反馈取得 `operation_id` 后，可用现有撤销工具恢复；不要重新导入整份 add 文件来修改一条批评。

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects reading.sqlite3 $caseProjectId --name 'D01 质疑：相关变化能证明因果吗'
```

外部网页会更新；本包不把网页链接当作冻结全文。调整本文结论时，也应复查对应 E/S 对象、图和讨论是否仍与之匹配。

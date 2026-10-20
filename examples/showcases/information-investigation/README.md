# 同看红外，为何还要三台望远镜？

先按[案例目录的 uv 步骤](../README.md#准备环境)设置 `$casePython`，再进入本案例目录执行以下 PowerShell 命令。

Webb（韦布）、Euclid（欧几里得）和 SPHEREx 都能观测红外，但它们提供的研究能力并不等价。这个案例调查三者在研究目标、波段、天空覆盖、光谱方式及性能判断条件上的区别，并展示如何把结论追溯到公开资料。

**调查截止：2026-10-20，Asia/Hong_Kong。** 八份官方或任务团队网页均在该日实际查阅。范围是公开设计与观测方式；没有下载科学数据进行统一性能实测，也没有核验最新数据覆盖率。来源中的未来计划和旧版本注记保留其原有时间条件。

## 先看结论

| 问题 | Webb | Euclid | SPHEREx |
|---|---|---|---|
| 主要研究尺度 | 选定对象的细节，涉及多类天体 | 暗宇宙、膨胀与结构的大样本统计 | 暴胀、星系总光及冰态分子的普查 |
| 波段概览 | 从约 0.6 μm 延伸到中红外；上限表述有差异 | VIS 约 0.55–0.9 μm；NISP 约 0.9–2 μm | 约 0.75–5 μm |
| 天空覆盖 | 单次视场随仪器、模式变化 | 目标超过全天三分之一；VIS 单次约 0.5 平方度 | 名义 25 个月科学观测设计为四轮全天扫描，另有更深的极区 |
| 光谱方式 | 狭缝、多目标、无缝、积分视场等 | NISP 的 Y/J/H 测光之外，还可用 grism 测光谱 | 渐变滤光片的 102 通道随多次指向累积 |
| 不能直接推出什么 | 波段越宽就一定越清晰 | 名义六年计划已经全部完成 | 全天各处同样深，或一次曝光取得同目标全部颜色 |

表中事实对应项目的 CW1–CW5、CE1–CE5、CS1–CS5；逐条来源、章节和条件见 [sources.md](sources.md)。这些差异支持“能力互补”的研究者判断，不构成预算效益证明或统一性能排名。

案例刻意保留一个真实差异：NASA 的仪器页写 0.6–27.9 μm，望远镜概览写 0.6–28.8 μm。**U1** 记录差异及仍缺少的版本/模式材料；它没有擅自解释差异成因。**U2** 保留同条件性能排名的证据缺口；**U3** 保留截止日数据发行与覆盖核验缺口。

## 文件与准备

- `project.json`：完整交换数据，全部新增节点使用 `op=add`、唯一 `key` 与 `refs`，没有预设数据库身份。
- `sources.md`：八份来源、查阅日期、章节位置、逐条主张对应和更新边界。
- `walkthrough.py`：运行下面五条体验路线；第五条只在新副本中修改并撤销。

需要一个已安装 **LayerWeave 0.7.6 或兼容交换格式 v1** 的 Python 环境，并包含 usage/developer 工具。基础版即可导入、查询、沿关联阅读、修改和撤销。`walkthrough.py` 仅依赖 Python 标准库和 LayerWeave，无其他包、密钥、付费服务或模型要求。

画布浏览需要含 `layerweave.tool.builtin.view` 的 **visualization 完整版**及浏览器；它是可选体验。此案例全部使用原创文字概括，没有外部媒体素材，导入后阅读无需联网。复核原始网页时需要联网。未打包第三方网页或图片。

## 导入一个新项目

将整个案例目录复制到自己的工作目录，进入这份副本。以下命令使用 uv 准备的 `$casePython` 解释器。数据库与案例文件放在同一目录；如果以后添加素材，相对路径以数据库目录为基准，交换工具不会代拷素材。

```powershell
& $casePython -X utf8 -m json.tool project.json parsed-project.json
& $casePython -X utf8 -m layerweave.tool.builtin.developer.database.cli investigation.sqlite3
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply investigation.sqlite3 --data-file project.json --new-project --result-file import-result.json
```

`parsed-project.json` 只是可删除的格式化副本。读取导入反馈：应当 `ok=true`、无 skipped、无 issues；共创建 **10 层、60 对象、119 关联**，另新建一个项目。重复执行 add 会再次创建内容，不用于更新已有案例。

在 PowerShell 中取得实际项目编号，再查概览、复查内容：

```powershell
$caseProject = (Get-Content -Raw import-result.json | ConvertFrom-Json).data.project_id
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_overview investigation.sqlite3 $caseProject
& $casePython -X utf8 -m layerweave.tool.builtin.usage.validation.cli investigation.sqlite3 $caseProject --json
```

在其他 shell 中使用 `import-result.json` 返回的真实项目编号替代 `$caseProject`。下方辅助脚本直接读取这个反馈文件，不需要手填任何 ID。

## 内容组织与标记

六个根分别为「调查问题与对象」「来源目录」「可核实主张」「证据摘记」「对照结论」「条件、差异与待确认」。主张按三个对象分子层，每个子层第 1–5 条依次回答 Q1–Q5；来源、证据和其他内容也是有序列表，第 n 条占 `[n,n+1)`，单位为序号。

阅读方向是 **结论 → 主张 → 证据 → 来源**；结论另连向适用条件和未知项。反方向可从来源查哪些主张与结论需要复核。更新来源记录不会自动重写其依赖者。

`information.text` 是完整可读正文；`code` 是稳定的人类标签，`category` 区分 question/subject/source/claim/evidence/conclusion/condition/unknown/method，`status` 区分文档所述 documented、计划 planned、附条件 conditional、文字差异 source_discrepancy、研究者推断 researcher_inference 和未知 unresolved 等。`as_of` 是本调查截止日。来源另有 `title/publisher/url/accessed_on/locator/temporal_note/usage`；证据有 `source_codes/locators`；主张有 `question_code/subject_code`。这些代码只是元数据标签，真正跨对象关联使用 bind，不在正文嵌入数据库 ID。

## 五条体验路线

直接运行前四条阅读路线：

```powershell
& $casePython -X utf8 walkthrough.py investigation.sqlite3 --import-result import-result.json
```

1. **从结论追溯来源和条件。** 定位「K04｜光谱：102 色不能直接战胜三个波段」，沿出向关联找到 CW4、CE4、CS4，再到 E04、E09、E14 和 S01、S04、S06、S08；同时阅读 P1、P2。预期看到：三个宽带测光波段并不代表 NISP 只有三个光谱采样点，SPHEREx 的完整光谱需要扫描累积。
2. **同一问题比较两个对象。** 比较 Q4 对应的「CW4｜Webb：光谱有多种模式」与「CE4｜Euclid：三个测光波段不等于三色光谱」。分别跟到 E04/S01 与 E09/S04。预期看到各自如何取光谱，而不是只数滤镜。
3. **定位尚不能确认的主张。** 阅读「U1｜Webb 上限差异的原因尚未证实」，经 CW2 到 E02、S01、S02。预期能够指出缺的是对应版本的仪器模式表和变更记录，不能凭猜测合并两个数字。
4. **追查来源更新的影响。** 从「S05｜Survey」沿入向走三步。预期结论集合为 K00、K02、K03、K05；路径经 E12/E13/E15 和 CS2/CS3/CS5。还会遇到 P3 与未知项，它们同样需要复核。S05 的未来计划或预测曲线更新后，应逐个核验依赖结论。
5. **在副本中修改一项记录并撤销。** 执行下面命令。脚本创建新副本，仅在 S05 正文追加明确标为练习的附注，检查其他记录、全部身份和关联保持，再按本次 `operation_id` 撤销；最后逐项比较原状态并复查。它拒绝覆盖已有副本。

```powershell
& $casePython -X utf8 walkthrough.py investigation.sqlite3 --import-result import-result.json --edit-copy edit-demo.sqlite3 --output experience-result.json
```

返回的 `experience-result.json` 包含实际节点、路径、修改与撤销操作编号以及恢复验证。再次练习时换一个未使用的副本名和报告名。

也可使用原生查询命令手动阅读。先按名称找到对象，再把查询返回的 `id` 填入 `$caseObject`：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects investigation.sqlite3 $caseProject --name 'K04｜'
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk investigation.sqlite3 $caseProject object $caseObject --direction outgoing --max-depth 3
```

## 可选画布

在 visualization 完整版中运行：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.view.server investigation.sqlite3 --project $caseProject --port 0
```

打开终端返回的本机地址；端口由系统分配。搜索 `K04｜` 后选择对象，在详情里读正文及关系，使用「沿读」查看出向三步；搜索 `S05｜`，切换入向三步查看影响。各根用序号轴，没有成片时间含义。缩小时对象卡片只作索引，完整文字在详情中阅读。

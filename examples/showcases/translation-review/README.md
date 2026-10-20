# 留下那声咔哒：翻译与校对

先按[案例目录的 uv 步骤](../README.md#准备环境)设置 `$casePython`，再进入本案例目录执行以下 PowerShell 命令。

一封关于旧收音机与家人记忆的原创英文书信，配有完整初译、推荐修订稿、术语约定和修改理由。通过这个案例，可以从译文追到依据，也可以观察一个英文句子怎样拆成两个中文条目。

**当前推荐阅读“修订译文（推荐）”。** 初译保留供比较；两个末句候选独立保存，不混入正文。

## 先读作品

- [英文原文：Leave the Click](assets/source-en.md)
- [中文修订稿：留下那声咔哒](assets/translation-zh.md)
- [完整初译](assets/translation-zh-initial.md)

英文由 Codex 于 2026-10-20 为本案例原创生成；人物和事件均为虚构，无外部引文或改写素材。英文含称呼、署名共 621 词，正文 616 词、6 个自然段。中文两版也都保留 6 个自然段。上述文本可随本案例分发、修改，不依赖外部许可素材或付费服务。

## 准备与导入

使用已安装 LayerWeave **0.7.6** 的 Python 环境。基础数据读写、查询、修改和撤销只需普通 Python/CLI 与 LayerWeave；本案例不需要图像、音视频、FFmpeg、模型密钥或新增第三方 Python 库。`explore.py` 只调用 LayerWeave 公共接口及 Python 标准库。

先把整个 `case/` 复制为自己的工作目录，例如 `translation-review-work/`，进入该目录后执行：

```powershell
& $casePython -X utf8 -m json.tool project.json parsed-project.json
& $casePython -X utf8 -m layerweave.tool.builtin.developer.database.cli review.sqlite3
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply review.sqlite3 --data-file project.json --new-project --result-file import-result.json
& $casePython -X utf8 explore.py review.sqlite3 overview
```

数据库必须与 `project.json` 同级，旁边保留 `assets/`。正文对象的 `information.source` 均为 `assets/…` 相对路径，以**数据库所在目录**为基准。交换工具不会复制素材；正文同时完整保存在 `information.text` 中，CLI 读取不必再打开素材文件。

导入应显示 `completed`，创建 **139** 个节点（6 层 + 38 对象 + 95 关联），跳过 **0**；新建项目另计。完整结果中的 `checks.issues` 应为空。不要重复执行 add 导入来尝试“更新”，否则会创建另一份项目。

`import-result.json` 的 `data.project_id` 和 `data.id_map` 提供实际项目及对象编号。下面的体验脚本按唯一项目名、对象名查询编号，不假定编号固定。如果库中存在多个同名项目，为每条命令追加 `--project-id 实际项目编号`。

## 内容怎样组织

| 根层 | 条目数 | 用途 |
|---|---:|---|
| 英文原文｜Leave the Click | 8 | 完整英文，含称呼与署名 |
| 中文初译（保留比较） | 8 | 完整初译，保留旧措辞 |
| 修订译文（推荐） | 9 | 当前推荐正文 |
| 术语与用词约定 | 5 | radio、tuning knob、static、service manual、click |
| 修改理由 | 6 | 语义、术语、拆句、语气、合理候选、用字约定 |
| 候选表达 | 2 | 已采用的 A 与仍合理的 B |

每个根用自己的条目轴，第 n 条占 `[n,n+1)`。各根的单位名称不同，避免在视图中把相同位置误读为自动对齐；对应关系只由 `bind` 表达。对象名中的 `P03A` 等是编辑定位标签，不是数据库 ID；条目位置也不是身份。

`information.paragraph` 保存自然段序号：原文的 `P03A/P03B` 合成第三段，修订稿的 `P03A1/P03A2/P03B` 合成第三段；两版的 `P06A/P06B` 都合成第六段。汇集全文时先按位置排序，再合并同一 paragraph，中文条目直接衔接，英文条目间加一个空格。首末条目已含称呼和署名。

修订对象沿出向关系连接原文、初译及重点修改理由；术语沿出向“用词例证”关系连接三份正文中所有明确出现该词或其已列变体的条目。术语覆盖范围是正文词例，不把说明文字、题名或每个代词也算成词例。题名的“咔哒”用字另由 T05 提醒核对。

## 五条体验路线

所有路线都可以用普通 Python/CLI 完成。输出的 `nodes` 包含名字、正文和实际 ID，`edges` 的 `tips` 说明关联含义；可以据此继续用 LayerWeave 原生查询工具定位。

### 1. 从修订句追到依据

```powershell
& $casePython -X utf8 explore.py review.sqlite3 trace
```

起点是 **REV-P03A1｜先听见咔哒声**：“今早，我转动调谐旋钮，听见了熟悉的咔哒声。”

沿出向关联找到 **EN-P03A｜咔哒声带回厨房**、**DRAFT-P03A｜咔哒声带回厨房**，以及 **R03｜一句拆成两句**。还可看到 R02 的术语统一与 R06 的拟声用字约定。预期观察：修订不是覆盖初译，原文与修改理由都有自己的身份。

### 2. 看一句怎样对应两句

```powershell
& $casePython -X utf8 explore.py review.sqlite3 split
```

起点是 **EN-P03A｜咔哒声带回厨房**，看入向“译文对应”关联，应同时找到 **REV-P03A1｜先听见咔哒声**与 **REV-P03A2｜再回到厨房**。另有一条初译依据关联和相关术语词例，不要把它们当成第三个修订译文。

原文只有一个句号，初译也保持一个长句；修订第一句写声音，第二句回到厨房，用“那声音”衔接。两条修订仍属于第三自然段。原文第 4 个条目是 P03B，修订第 4 个条目已经是 P03A2，因此不能按相同横坐标匹配。

### 3. 从术语找出全部词例

```powershell
& $casePython -X utf8 explore.py review.sqlite3 terms
```

起点 **T03｜static → 杂音** 应连到 **6 个正文条目**：原文 P02/P05、初译 P02/P05、修订 P02/P05。初译写“静电”，修订写“杂音”；这次修改纠正了具体语境里的词义。不是宣称 static 在任何语境下都译作“杂音”。

其他术语也可以用 `find_objects --name` 查出实际编号，再用 `query.relations` 或 `query.walk` 展开。例如：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects review.sqlite3 PROJECT_ID --name "T02｜tuning knob"
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk review.sqlite3 PROJECT_ID object OBJECT_ID --direction outgoing --max-depth 1
```

`PROJECT_ID`、`OBJECT_ID` 是占位参数，分别替换为导入结果和查询结果中的编号。T02 的“调台旋钮／调谐旋钮”统一属于编辑约定，与 static 的语义纠错性质不同。

### 4. 比较两种合理表达

```powershell
& $casePython -X utf8 explore.py review.sqlite3 compare
```

从 **R05｜末句的两种合理表达** 展开两步，比较：

- **A｜还有我们的位置（采用）**：“那片寂静里，还有我们的位置。”
- **B｜还容得下我们（保留）**：“那片寂静，还容得下我们。”

两者都连接 **EN-P06B｜寂静里的位置**和当前 **REV-P06B｜寂静里的位置**。A 呼应桌上各有位置的两台机器，语气克制；B 更突出寂静的容纳感。当前采用 A，B 保持 `valid-alternative`，没有被归为错译。

### 5. 修改用词，检查一致性，再撤销

```powershell
& $casePython -X utf8 explore.py review.sqlite3 edit-undo
```

脚本先在当前目录创建独立的 `exercise-随机后缀.sqlite3` 副本，然后执行以下过程，输入数据库保持原样：

1. 把 **REV-P02｜抽屉里的维修手册**的一处“杂音”改成“噪声”，用 update 保留原对象身份、位置和全部 information 附加字段。
2. 核对更新前后的对象身份和双向关联完全相同；沿 **T03** 查看全部词例，在输出的 `changed_recommended_examples` 中比较改后的 P02 与仍写“杂音”的 **REV-P05｜送出与留下**。需要再审查 T03 的约定和 **R01｜static 的语义**。这里“噪声”本身可用，问题是与本稿已选定用词不一致。
3. 使用这次更新实际返回的 `operation_id` 调用撤销，核对整个项目的内容、位置和关联恢复原状，输出 `whole_project_restored: true`。

这演示的是**沿关系人工识别一致性问题**。LayerWeave 的结构复查不会自动理解中文术语约定，更新后的 `checks.issues` 仍可为空。数据库改词也不会自动写回 Markdown 素材；正式编辑时需要自行同步，当前练习已撤销。

若手动用原生工具编辑，可从返回结果取操作编号，用以下命令撤销；不要误用导入那一批操作的编号：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.undo.cli exercise-实际后缀.sqlite3 OPERATION_ID --json
```

## 用原生工具继续阅读

以下参数中的编号均从查询或导入结果取得：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_overview review.sqlite3 PROJECT_ID
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_details review.sqlite3 PROJECT_ID --layer-id LAYER_ID --compact
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.relations review.sqlite3 PROJECT_ID object OBJECT_ID --direction both
& $casePython -X utf8 -m layerweave.tool.builtin.usage.validation.cli review.sqlite3 PROJECT_ID --json
```

修改理由与候选使用普通文字对象，而非 visualization 专属批注表，因此不影响基础版的导入和阅读。

## 可选：在画布中阅读

画布、搜索、关系线、对象详情和“沿读”需要 **visualization 完整版**以及浏览器，前面的五条路线均不依赖它。

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.view.server review.sqlite3 --project PROJECT_ID --port 8875
```

选择空闲端口；打开服务打印的本机地址，按上面的对象名搜索。在对象详情里打开“沿读”，选择“它指着谁”追译文依据，选择“谁指着它”看一句拆成两句。“术语与用词约定”根下选 T03，沿出向关系即可查看六个词例。

长段落请在对象详情或沿读中阅读完整内容。画布色块主要用于定位，各根的独立条目位置不表示逐句对齐。CLI、Markdown 文件与画布呈现的是同一份正文。

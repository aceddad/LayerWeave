# 替你保管到明天

先按[案例目录的 uv 步骤](../README.md#准备环境)设置 `$casePython`，再进入本案例目录执行以下 PowerShell 命令。

旧车站关门前，许枝来认领一只遗失十六年的手套。腕口多出的两针黄线，让她重新追问一场没等到的送别。

这是一个可以读完、导入和继续编辑的小说案例：五个场景、三位主要人物，正文约两千字。先读 [完整短篇](assets/story.md)，再沿关联查看创作依据。人物说明、事件表和伏笔含剧透。

## 内容怎么组织

| 根层 | 内容与轴含义 |
| --- | --- |
| 正文｜从这里读 | 唯一采用稿入口。阅读场景轴为 1—5，每场占 `[n,n+1)`；场景内存放实际正文。 |
| 事件｜发生顺序 | 七项实际事件，按先后编号；事件序位不是等长时间，具体日期或范围写在事件文字中。 |
| 人物｜目标与已知 | 三个人物、五条分时段的状态。记录目标、当时已知与未知、关键行为；状态条目不是时间线。 |
| 伏笔｜铺垫与回收 | 两条伏笔、叙事顺序说明与结尾留白。每条伏笔都指向具体场景，关联说明标明铺垫、回收和对应句子。 |
| 候选｜未采用，比较时再读 | 一段替换正文04后半段的候选及取舍理由。未进入正文或连续原稿。 |

轴上的数值只表示各自的序位，对象身份始终使用实际导入或查询返回的 ID。五种轴使用不同的单位名称，避免把阅读第3场和发生第3件事误对齐。关联可以跨轴。

`assets/story.md` 的五节正文，与 `project.json` 中正文层五个对象的 `information.text` 逐段一致；标题与来源说明不计入场景正文。数据库编辑不会自动回写 Markdown，修改采用稿后需同步这两个入口。其他根不是附加章节。

## 准备与导入

需要已安装 LayerWeave 的 Python 环境；本案例使用 0.7.6 的交换格式 v1 与公共工具接口。以下 PowerShell 命令从 `case/` 的父目录运行，`fiction-reading` 应为一个未使用的新目录。其他系统也可以手动复制整个 `case/`，进入副本后执行同样的 Python 模块命令。

```powershell
Copy-Item -Recurse ./case ./fiction-reading
Set-Location ./fiction-reading
& $casePython -X utf8 -m layerweave.tool.builtin.developer.database.cli story.sqlite3
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply story.sqlite3 --data-file project.json --new-project --result-file import-result.json

$importResult = Get-Content -Raw -Encoding UTF8 ./import-result.json | ConvertFrom-Json
$projectId = $importResult.data.project_id
$ids = @{}
$importResult.data.id_map | ForEach-Object {
    if ($_.source.key) { $ids[$_.source.key] = $_.target.id }
}
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_overview story.sqlite3 $projectId --json
& $casePython -X utf8 -m layerweave.tool.builtin.usage.validation.cli story.sqlite3 $projectId --json
```

导入应显示 71 个新增节点：5 个层、23 个对象、43 条关联；`data.status` 为 `completed`，`counts.skipped` 为 0。还要读取 `checks`，不能仅看提交成功。重复执行本例的 add 导入会另建一份内容；它不是更新命令。

数据库应与 `project.json` 同级，`assets/` 保持在旁边。正文对象的 `information.source` 使用 `assets/story.md`，按数据库所在目录解析。交换工具不会替你复制这个文件。

全文阅读、导入、检索、关联追踪、修改、复查与撤销均可用普通 Python/CLI 完成。网页画板和点击式沿读需要 **visualization 完整版**；它们不是完成下列任务的前提。本例没有图像、音视频或外部模型调用，不需要 FFmpeg、付费服务或额外媒体依赖。

## 路线一：从回收读回铺垫

在正文入口读完五场，再从“正文03｜十七点十二分（倒叙）”出发：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_details story.sqlite3 $projectId --layer-id ($ids['reading'])
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk story.sqlite3 $projectId object ($ids['s3']) --direction outgoing --max-depth 2
```

结果中，深度1出现“伏笔A｜两针黄线”与“伏笔B｜寄字下面的拾得”，深度2出现“正文01｜两针黄线”。读各节点的 `record.information.text` 和边的 `tips`：

- 黄线：正文01“不记得这两针” → 正文03拆包子黄棉线补缝 → 正文04“就两针”再次确认。
- 标签：正文01“拾得”下露出“寄” → 正文02旧册露出交物者姓名 → 正文03交代为何改字。

两个回收都对应真实的正文段落。正文03与伏笔之间存在双向可走的环；查询按身份去重，不表示重复发生了一次事件。

## 路线二：从行为找到动机与已知信息

选择正文03中许成“别说是我送来的”这个行为，逆向找创作依据：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk story.sqlite3 $projectId object ($ids['s3']) --direction incoming --max-depth 1
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects story.sqlite3 $projectId --name '动机｜许成·迟到那天'
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.relations story.sqlite3 $projectId object ($ids['m_cheng_past']) --direction outgoing
```

预期看到：许成知道车次、女儿没吃午饭和腕口破损，但不知道宿舍地址；他想靠近女儿又逃避先道歉。这个动机指向正文03与正文04，后者是他亲口承认当年的犹疑。现在的手抖不能解释十六年前的迟到。

## 路线三：对照两种顺序

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_details story.sqlite3 $projectId --layer-id ($ids['chronology'])
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.relations story.sqlite3 $projectId object ($ids['s3']) --direction outgoing
```

| 阅读场景 | 对应事件 | 读者此时获得什么 |
| --- | --- | --- |
| 正文01 | 事件04 | 先认出手套，尚不知道父亲来过。 |
| 正文02 | 主事件05；补述01、03 | 旧册揭开交物者身份，交代物品保存经过。 |
| 正文03（倒叙） | 事件01、02 | 回到2010年，补足迟到、补缝与隐瞒。 |
| 正文04 | 主事件06；补述03 | 由父亲确认事实并承担责任。 |
| 正文05 | 接续06；主事件07 | 完成认领并约定明天。 |

“事件03｜旧物转存”是一段跨年的背景范围，日期没有被假装精确到某一天。正文03放在阅读中段，是为了先让读者理解许枝的判断，再用新证据修正它；人物并未向读者藏起自己已经知道的答案。“留白｜明天还没有发生”说明了结尾为何不直接写和解。

## 路线四：改一次动机，列出复查范围，再撤销

在阅读副本目录中，把下面代码保存为 `try_motive.py`，运行 `& $casePython -X utf8 try_motive.py`。代码从当前项目导出 add 副本，创建专用临时目录和数据库，复制素材，再按名称查询副本中的实际身份。实验结束自动清理临时目录，当前阅读数据库保持原样。

```python
import copy
import json
import shutil
import tempfile
from contextlib import closing
from pathlib import Path
from layerweave.support.api import initialize_database, open_database, read_object
from layerweave.tool.builtin.usage.exchange import export_project, import_project
from layerweave.tool.builtin.usage.query.find_objects import find_objects
from layerweave.tool.builtin.usage.query.project_details import project_details
from layerweave.tool.builtin.usage.query.walk import walk_relations
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.tool.builtin.usage.undo.service import undo_operation
from layerweave.tool.builtin.usage.validation.recheck import recheck

meta = json.loads(Path("import-result.json").read_text(encoding="utf-8"))
project_id = meta["data"]["project_id"]
with closing(open_database("story.sqlite3")) as original:
    source_before = project_details(original, project_id)
    document = export_project(original, project_id, op="add")

with tempfile.TemporaryDirectory(prefix="fiction-edit-", dir=".") as temp:
    folder = Path(temp)
    assert folder.resolve().parent == Path.cwd().resolve()
    shutil.copytree("assets", folder / "assets")
    initialize_database(folder / "story.sqlite3")
    with closing(open_database(folder / "story.sqlite3")) as connection:
        result = import_project(connection, document, new_project=True)
        assert result["ok"] and result["data"]["status"] == "completed"
        copied_project = result["data"]["project_id"]
        before = project_details(connection, copied_project)
        matches = find_objects(connection, copied_project, name="动机｜许成·迟到那天")
        assert len(matches) == 1
        object_id = matches[0]["id"]
        old = read_object(connection, copied_project, object_id)
        information = copy.deepcopy(old["information"])
        information["text"] = information["text"].replace(
            "迟到后希望保留一个可以再接近女儿的机会，却不敢先道歉",
            "迟到后决定当天主动向女儿道歉，不再隐瞒自己来过")
        assert information != old["information"]
        edited = dispatch(connection, {
            "action": "update", "kind": "object",
            "project_id": copied_project, "id": object_id,
            "data": {"information": information}})
        assert edited["ok"] and edited["applied"]
        assert not edited["checks"]["issues"]
        current = read_object(connection, copied_project, object_id)
        assert current["information"] == information
        assert current["id"] == old["id"] and current["bind"] == old["bind"]
        impact = walk_relations(connection, copied_project, "object", object_id,
                                direction="outgoing", max_depth=1)
        assert not impact["truncated"]
        affected = [n["record"]["name"] for n in impact["nodes"] if n["depth"] == 1]
        print("需要复查：", *affected, sep="\n")
        assert set(affected) == {"正文03｜十七点十二分（倒叙）", "正文04｜电话那一头"}
        undone = undo_operation(connection, edited["operation_id"])
        assert undone["ok"] and undone["applied"]
        assert project_details(connection, copied_project) == before
        review = recheck(connection, copied_project)
        assert review["status"] == "completed" and not review["issues"]
        print("已撤销：内容、身份和关联均恢复。")

with closing(open_database("story.sqlite3")) as original:
    assert project_details(original, project_id) == source_before
print("原阅读项目保持不变。")
```

预期复查正文03的隐瞒行为和正文04对当年沉默的追问。如果父亲决定当天主动道歉，这两处就需要重新考虑；顺着正文的后续关联，还可以继续检查伏笔与结尾。这里先列出直接依赖的场景，再撤销实验。

软件复查验证结构和字段，不会自动判断人物心理是否自洽。关联给出复查范围，具体叙事矛盾仍由读者判断。撤销以本次更新返回的 `operation_id` 为准，不是候选稿切换，也不撤销外部 Markdown 文件。

## 比较候选与打开网页

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_details story.sqlite3 $projectId --layer-id ($ids['alternatives'])
```

“候选·未采用｜一次电话就和解”可与正文04后半段直接对读。“取舍说明｜保留仍然生气”解释为何舍弃：快速宽恕掩盖了父亲的选择，还把七分钟的登记时间差误当成精确迟到时长。正文并没有采用这些结论。查询整个项目会同时包含候选，连续阅读请限定正文根。

使用 visualization 完整版时，可在一个空闲端口启动本副本：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.view.server story.sqlite3 --project $projectId --port 8879
```

打开工具打印的本机地址。在目录选择“正文｜从这里读”，点正文03查看详情，再用“沿读”选择出向、两步，沿伏笔回到正文01。人物依据则从正文03向入向走一步；候选有独立根和明确的“未采用”名称。若端口被占用，选择别的空闲端口；不要停止其他服务。普通版没有网页工具时，使用上面的 CLI 路线即可。

## 素材与分发

`assets/story.md` 是本案例原创短篇；人物、地点、对话、候选稿和创作说明均为虚构创作，无外部图片、文章摘录或下载链接。素材可随案例一同分发。导入文件不携带数据库、日志或本机身份；全新节点使用 `op=add`、唯一 `key` 和内部 `refs`，由目标数据库发放身份。

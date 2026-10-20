# 借一点晴天

先按[案例目录的 uv 步骤](../README.md#准备环境)设置 `$casePython`，再进入本案例目录执行以下 PowerShell 命令。

一把被借走的红伞引起误会；伞下的两盆幼苗，让两位邻居学会先沟通、再一起行动。这是一个两页、八格的原创漫画案例，包含实际画面、剧情、对白、人物设定、旧稿、修订理由与跨页审阅。

**直接阅读：**用浏览器打开 [read.html](read.html)。也可打开 [第一页](assets/page-01.svg)、[第二页](assets/page-02.svg)，或使用不依赖本机中文字体的 [第一页 PNG](assets/page-01.png)、[第二页 PNG](assets/page-02.png)。每页依次读左上、右上、左下、右下。

## 内容组织

| 根层 | 坐标含义 | 内容 |
|---|---|---|
| 完整页面 | 页码 p 占 `[p,p+1)` | 两张完整页面图；入向关联能找到本页分格 |
| 全篇分格 | 全篇格序 n 占 `[n,n+1)` | 8 个分格说明；子层为当前画面、实际对白 |
| 剧情、人物与审阅 | 独立资料条目 `[n,n+1)` | 故事梗概、两人设定、场景、修订理由、审阅、制作说明 |
| 候选与旧稿 | 全篇格序，第 7 格 | 第七格旧对白及实际旧画面，明确未采用 |

第一页对应全篇 1–4 格，第二页对应 5–8 格。`P2-1` 表示第二页第一格，即全篇第 5 格；这些序号均不是数据库 ID，也不是时间。共有 7 层、42 个对象、96 条标准关联。14 句角色对白及 1 条旁白分别存储；同格多句共享格区间，用 `information.reading_order` 表示先后。

关联方向：对白 → 分格／当前画面／说话人，分格 → 所在页面／当前画面／下一格／场景。第七格还关联候选画面；修订理由关联旧稿、当前稿和第二页；审阅意见直接关联第 4、5 格。查询反向关系可以从页面找到分格，从分格找到对白。

审阅意见使用普通文字对象及标准关联，因此普通版也能阅读。它不是 visualization 专属的批注楼，不会出现在原生“批注”列表；请用搜索、对象详情或“沿读”进入。

## 准备与导入

- Python 3.11 或更新版本，使用已安装的 LayerWeave；本案例按 0.7.6 交换格式 v1 制作。
- 数据导入、概览、查询、复查、修改及撤销只需普通 Python/CLI，无第三方 Python 依赖。
- 浏览器直接读 SVG、PNG、HTML 不需要 LayerWeave。SVG 文本建议安装 Microsoft YaHei、Noto Sans CJK SC 或 PingFang SC 中任一中文字体。
- 交互画布、媒体预览和“沿读”侧栏需要 **visualization 完整版**。本案例没有视频或音频，不需要 FFmpeg；截图工具另需 Edge、Chrome 或 Chromium。

保留整个 `case/` 目录。媒体路径以**数据库所在目录**为基准；交换工具不会替你复制素材。推荐先复制一份 `case/` 作为工作副本，再将数据库创建在副本根目录。以下 PowerShell 命令在包含 `case/` 的目录运行，`comic-work` 应为尚不存在的目录：

```powershell
Copy-Item -LiteralPath ./case -Destination ./comic-work -Recurse
Set-Location ./comic-work
& $casePython -X utf8 -m json.tool ./project.json > $null
& $casePython -X utf8 -m layerweave.tool.builtin.developer.database.cli ./comic.sqlite3
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply ./comic.sqlite3 --data-file ./project.json --new-project --result-file ./import-result.json

$report = Get-Content -Raw -Encoding utf8 ./import-result.json | ConvertFrom-Json
$comicProjectId = [int]$report.data.project_id
function KeyId {
    param([string]$key)
    [int](($report.data.id_map | Where-Object { $_.source.key -eq $key }).target.id)
}

& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_overview ./comic.sqlite3 $comicProjectId
& $casePython -X utf8 -m layerweave.tool.builtin.usage.validation.cli ./comic.sqlite3 $comicProjectId --json
```

正常导入为 `completed`，创建 145 个节点（7 层 + 42 对象 + 96 关联），跳过 0；项目的创建另计。检查 `ok`、`operation.status`、`checks` 和跳过项，不要只看命令是否返回。再次执行新增导入会创建另一个项目；已有内容的编辑应更新原对象。

`KeyId` 从这次导入结果提取真实编号。也可通过以下查询按对象名称定位：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.find_objects ./comic.sqlite3 $comicProjectId --name '对白07-1'
```

## 五条体验路线

以下命令沿用导入步骤的变量与函数。CLI 路线完整可用；在 visualization 中可用搜索框找同名对象，点击关系中的目标跳转，或从对象详情打开“沿读”。

### 1. 从第二页找到分格顺序和对白

定位 **第2页｜晴天可以一起借**，读取入向关系，再展开全篇格序 `[5,9)`：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk ./comic.sqlite3 $comicProjectId object (KeyId 'page-2') --direction incoming --max-depth 1
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_details ./comic.sqlite3 $comicProjectId --layer-ids (KeyId 'sequence') --begin 5 --end 9 --json
```

预期顺序为 **P2-1｜把话说清楚 → P2-2｜一起搬 → P2-3｜下一次的约定 → P2-4｜借一点晴天**。每格两句对白，先后如下：

| 格 | 阿川／小禾实际对白（按阅读顺序） |
|---|---|
| P2-1 | 阿川：对不起，刚才没来得及问。／小禾：原来你在护着小苗。 |
| P2-2 | 小禾：我来搬，你撑稳。／阿川：好，慢慢来。 |
| P2-3 | 小禾：下次先喊我，我们一起搬。／阿川：一定。 |
| P2-4 | 小禾：走吧，晴天借给它们。／阿川：伞，我们一起用。 |

### 2. 点一条对白，找到分格和画面

定位 **对白07-1｜小禾**，沿出向关系读两步：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk ./comic.sqlite3 $comicProjectId object (KeyId 'line-7-1') --direction outgoing --max-depth 2
```

一步可到 **P2-3｜下一次的约定**、**画面07｜当前稿**及 **人物｜小禾**；两步可到第二页。画面来源是 `assets/panel-07.svg`。在视图中点击该图片对象预览，应该看到黄色外套的小禾说“下次先喊我，我们一起搬。”

### 3. 从审阅意见跳到相关两格

定位 **审阅｜第4格→第5格的伞与幼苗**：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk ./comic.sqlite3 $comicProjectId object (KeyId 'review') --direction outgoing --max-depth 1
```

它直接指向 **P1-4｜伞下的秘密**、**P2-1｜把话说清楚**。分别打开两格当前画面：第4格是近景，第5格拉远；阿川都在红伞右侧，用画面左侧的手臂握杆，两盆苗仍在伞下，没有交换左右。意见的 `status=open` 留作读者审阅，并不代表图片缺失或自动检测错误。

### 4. 比较旧稿与当前稿，读修改理由

定位 **修订理由｜从许可到协作**：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk ./comic.sqlite3 $comicProjectId object (KeyId 'revision') --direction outgoing --max-depth 1
```

对照 `assets/panel-07-draft.svg` 和 `assets/panel-07.svg`。旧稿“算了，这次原谅你。”保留单方面评判；当前稿“下次先喊我，我们一起搬。”让第6格的合作延续为沟通约定。两幅画面的差别就是小禾的气泡文字；第二页已采用当前稿。旧稿存在于独立根层，不会自动隐藏，也不替代数据库操作历史。

### 5. 修改一句对白，定位待重新排版页面，再撤销

只在工作副本操作。先沿路线 2 确认第二页为受影响页面，再运行附带练习工具：

```powershell
& $casePython -X utf8 ./edit-exercise.py ./comic.sqlite3 ./import-result.json edit
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.walk ./comic.sqlite3 $comicProjectId object (KeyId 'line-7-1') --max-depth 2
```

工具把原 **对白07-1｜小禾** 改为“下次叫上我，一起给小苗挡雨。”，同时将 **画面07｜当前稿** 和第二页的 `information.production_status` 设为 `needs_relayout`，并记录待重新制作说明。三个对象编号及所有关联保持不变。实际 SVG、PNG 仍显示原句：**改数据库文本不会自动更新图片**。在完成重新排版前，不应把图片当作更新后的成稿。

检查后撤销这个批次：

```powershell
& $casePython -X utf8 ./edit-exercise.py ./comic.sqlite3 ./import-result.json undo
& $casePython -X utf8 -m layerweave.tool.builtin.usage.validation.cli ./comic.sqlite3 $comicProjectId --json
```

预期对白、两个制作状态、编号和关联全部恢复；图片文件从未改动。工具将操作反馈写入副本的 `exercise-result.json`，撤销反馈写入 `exercise-undo.json`。如果已手动编辑外部 SVG，数据库撤销不能恢复那些文件。

## 用 visualization 阅读

在安装完整版的环境中，保持当前工作副本目录，选择一个空闲端口运行：

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.view.server ./comic.sqlite3 --project $comicProjectId --port 8876
```

打开工具打印的本机地址。目录中的“完整页面”能看到整页缩略图；搜索对象名可选中分格、对白、审阅或旧稿。对象详情列出关联，点击目标可跳转；“沿读”可调整方向和步数。审阅对象请从搜索进入，不用原生批注列表。若端口被占用，选择别的端口，不停止已有服务。

## 素材与编辑

所有媒体引用都是相对路径，11 个被引用 SVG 均随案例提供。两页 SVG 各自嵌入四格完整矢量内容，不依赖外链；两张 PNG 是相同页面的便携预览。SVG 即可编辑源文件，每页内用 `data-panel` 标记全篇格序。修改单格后需同步整页并重新导出 PNG。

素材、故事及对白均为本案例原创，按 CC0 1.0 提供。来源、尺寸、字体回退与具体使用方式见 [assets/SOURCE.md](assets/SOURCE.md)。离线阅读页和练习脚本也可随案例复制与修改；运行练习不需要访问网络。

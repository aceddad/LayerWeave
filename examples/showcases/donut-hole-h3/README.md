# 动态分镜 + H3：ドーナツホール（无视频阅读版）

用 60 个镜头组织歌曲段落、故事、构图、动作与实现方式，再把人物镜头交给 H3 补中间动作。公开版提供 40 张片段静帧，展示方案怎样对应到素材；它不播放原视频，不需要模型服务。

与[手书版](../donut-hole-tegaki/README.md)对照，可以看到同一内容怎样采用两套实现。先打开 [静帧浏览](read.html)，再沿镜头 → 所在段落 → 实现方式 → 片段静帧 → 模型阅读。

## 内容

| 位置 | 内容 |
|---|---|
| project.json | 30 层、228 个对象、210 条关联；5 个根分别组织歌曲、内涵、图片、视频和资源 |
| assets/stills | 从 40 个本地 H3 片段第 1 秒抽出的静帧，960 像素宽；保留构图，不模拟动作 |
| assets/public/h3/svg、assets/public/v9 | 少量动态 SVG 与静帧，供理解纯代码镜头 |
| source | 原网页原型源码，供阅读时间驱动、镜头复用与画面组合；完整运行需要另备素材 |
| generation | 镜头表、提示词与生成脚本，作为制作记录阅读 |

## 导入并阅读

先按[案例目录的 uv 步骤](../README.md#准备环境)准备 `$casePython`，然后进入本案例目录。完整版本含网页视图；数据阅读不需要 Node、FFmpeg 或 Key。

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.developer.database.cli h3.sqlite3
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply h3.sqlite3 --data-file project.json --new-project --result-file import-result.json
$caseImport = Get-Content -Raw -Encoding utf8 import-result.json | ConvertFrom-Json
if (-not $caseImport.ok) { throw '导入失败，请检查 import-result.json' }
$caseProjectId = $caseImport.data.project_id
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_overview h3.sqlite3 $caseProjectId
& $casePython -X utf8 -m layerweave.tool.builtin.view.server h3.sqlite3 --project $caseProjectId
```

打开服务打印的本机地址。数据库留在案例目录内，让图片相对路径可以直接解析；导入不会搬素材。再次导入会创建另一份项目。无需 LayerWeave 也可以直接用浏览器打开 [read.html](read.html) 看静帧。

## 数据与原制作的对应

“H3 片段”层在此版改为图片层，每个原视频对象改为图片对象；原编号导引、时间区间和全部关联不变，因此仍可看到镜头复用同一素材。未附歌曲以文字说明保留时长，外部视频参考以文字链接表示，不作为可直接解码的视频。

`information.original_media` 保存原来的 config_ref 和相对路径，仅供恢复时参考。以后自己补齐媒体，可通过正常 update 修改层、对象类型与 source，并移除这一说明字段；不要重新创建对象，以免丢失关联。这不是自动还原或下载功能。

建议依次看：镜头设计中的 60 个条目 → 相应实现方式 → H3 静帧 → 模型 → 内涵控制中的故事和意象。多个镜头共用同一片段的关系也保留。

## 源码与完整素材

source 原型会按时间读取 40 段视频；公开包没有这些文件，默认入口使用 read.html 和 LayerWeave 画布。完整播放须自行准备对应 assets/public/h3/视频、音频及歌词，源码所需 Node 版本由 source/package.json 声明。缺素材时不要把 npm run dev 当成完整案例验收。

生成方案分为 pair（首尾帧）、single（首帧）、reuse（复用）、code（代码镜头）。首尾帧原图和外部生成服务不随包提供；generation 脚本包含制作时的路径，需要自行适配，导入项目不会执行它们。提示词倾向固定镜头，推拉摇移由代码完成。

## 素材说明

静帧来自本地 AI 生成的 H3 视频；插画来自原制作使用的 AI 图片。歌曲及歌词文件不随包提供，外部参考保留来源链接；这些来源的权利不因软件采用 MIT 而改变。完整制作素材保留在本地，公开案例包只包含这里列出的阅读材料。

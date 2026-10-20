# 手书制作：ドーナツホール（无视频阅读版）

用 LayerWeave 管理从听感、故事到画面设计与实现的过程。这个版本保留项目结构、角色设定、全片总览静帧和源码，默认离线阅读；不附成片、歌曲、歌词文件和全部图片零件。

先打开 [总览静帧](read.html)，再看故事与画面设计如何对应。与[H3 版](../donut-hole-h3/README.md)对照时，可以比较静态插画加代码运动与生成视频的不同实现方案。

## 内容

| 位置 | 内容 |
|---|---|
| project.json | 29 层、101 个对象、43 条关联；5 个根组织歌曲、内涵、图片、视频和资源 |
| assets/preview/overview.jpg | 关闭歌词与字形效果后，从源工程重新渲染的 32 个时刻 |
| assets/character | 四张角色设定图 |
| source | 按时刻驱动画面的 React 源码，保留实现参考；不包含运行所需的全部素材 |

## 导入并阅读

先按[案例目录的 uv 步骤](../README.md#准备环境)准备 `$casePython`，然后进入本案例目录。完整版本含网页视图；数据阅读不需要 Node、FFmpeg 或 Key。

```powershell
& $casePython -X utf8 -m layerweave.tool.builtin.developer.database.cli tegaki.sqlite3
& $casePython -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply tegaki.sqlite3 --data-file project.json --new-project --result-file import-result.json
$caseImport = Get-Content -Raw -Encoding utf8 import-result.json | ConvertFrom-Json
if (-not $caseImport.ok) { throw '导入失败，请检查 import-result.json' }
$caseProjectId = $caseImport.data.project_id
& $casePython -X utf8 -m layerweave.tool.builtin.usage.query.project_overview tegaki.sqlite3 $caseProjectId
& $casePython -X utf8 -m layerweave.tool.builtin.view.server tegaki.sqlite3 --project $caseProjectId
```

打开服务打印的本机地址。数据库留在案例目录内，让图片相对路径可以直接解析；导入不会搬素材。再次导入会创建另一份项目。无需 LayerWeave 也可以直接用浏览器打开 [read.html](read.html) 看静帧。

## 建议阅读路线

1. 总览静帧：先了解各段画面。
2. 内涵控制中的“个人理解”和“故事”：看表达从哪里来。
3. 图片控制中的“画面设计”：沿关联回到歌曲段落和故事。
4. 视频控制中的“实现方式”：看每段使用什么部件和代码方法。
5. 资源管理中的角色设定、源工程与技术记录：了解可复用部分。

原“成片”视频对象在此版改为总览图片，所属层同步改为图片层；未附音频以文字说明保留原时长，外部视频参考以文字链接表示。时间位置、原编号导引及全部关联保留，静帧不表示动态效果。`information.original_media` 留下原资源路径与配置，供自己补素材后通过 update 恢复，不触发下载。

## 源码怎么读

- source/src/core/time.ts 和 clock.tsx：时间驱动。
- source/src/v10/kit.tsx：色场、地平线、粒子、窗口、歌词排版等画面部件。
- source/src/v10/parts.tsx：人物部件与姿态、嘴型。
- source/src/v10/s1.tsx–s4.tsx：14 段画面。

源码与生成脚本作为实现参考，不是完整素材的替代品。原型需要额外提供图片零件、歌曲及歌词；部分制作脚本含原工作区路径。公开版的阅读入口无需执行这些脚本或安装 Node。

## 素材说明

角色图与画面插画来自原制作使用的 AI 图片；总览从本地源工程重新渲染，未载入歌词文字，并关闭了字形效果；图片素材与构图保留。歌曲《ドーナツホール》、歌词及角色参考保留各自权利，软件 MIT 许可不改变这些内容的权利。公开包不含音视频，完整素材仍保留在本地。

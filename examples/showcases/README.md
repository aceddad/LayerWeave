# 场景演示

第一次使用从[文章解析](article-reading/README.md)开始：导入中文正文、解读、证据和配图，然后沿关联追溯一个论点。阅读本地案例不需要模型服务、API Key、FFmpeg 或 Node；打开外部原文时才需要联网。

十二个案例均保留可导入的 project.json。案例不安装进 Python 的 site-packages，放在使用者选择的工作目录中；源码包与独立案例 ZIP 提供相同的 examples/showcases 目录。项目 JSON 使用交换格式 v1，这组案例以 LayerWeave 0.7.8 验证。

## 准备环境

Windows 安装 [uv](https://docs.astral.sh/uv/getting-started/installation/) 后，将本版本 wheel 放进工作目录，并将案例目录解压或复制到同一工作目录的 examples/showcases。PowerShell 中执行：

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe ./layerweave-0.7.8-py3-none-any.whl
$casePython = (Resolve-Path .venv/Scripts/python.exe).Path
Set-Location examples/showcases/article-reading
```

uv 默认会下载缺少的 Python。这里使用本地 wheel，不假定 PyPI 已有同名版本；首次下载运行环境需要联网。只体验案例不需要 mcp extra，连接 AI 客户端时按软件的 MCP 说明加装 `[mcp]`。不需要激活环境。

已经按 main 的开发指南建立 uv 环境时，直接设置 `$casePython` 并使用现有安装，无需再装完整 wheel；需要画布时另用完整版本环境。

接着执行所选案例 README 的导入步骤；其中 `& $casePython` 始终指向上面准备的解释器。打开新 PowerShell 后先重新设置这个变量，例如 `$casePython = 'D:/my-project/.venv/Scripts/python.exe'`，再进入案例目录。选择其他案例时，把最后一条 Set-Location 的 article-reading 换成目录名即可。

数据库放在所选案例目录内，与 project.json 同级。媒体路径相对于数据库目录解析；JSON 导入不会复制素材。读取导入结果里的 project_id，不假定编号是 1；再次用 --new-project 导入会创建新副本。

## 选择案例

| 案例 | 展示什么 | 入口 |
|---|---|---|
| **文章解析 · 入门推荐** | 正文与解读并排阅读，从论点追溯证据、图与讨论 | [article-reading](article-reading/README.md) |
| 小说创作 | 故事正文、人物、事件与伏笔的关联 | [fiction-writing](fiction-writing/README.md) |
| 漫画创作 | 剧情、分镜、画格和页面，局部修改与回看 | [comic-creation](comic-creation/README.md) |
| 信息调查 | 来源、事实、比较与结论，明确推断边界 | [information-investigation](information-investigation/README.md) |
| 课程学习 | 概念、例题、图解与练习之间的关系 | [course-learning](course-learning/README.md) |
| 需求设计 | 需求、界面草图、约束与验收依据 | [requirements-design](requirements-design/README.md) |
| 翻译审校 | 原文、译文、术语与修改意见的逐项定位 | [translation-review](translation-review/README.md) |
| 互动故事 | 分支、条件与结局；用关联表示路线 | [interactive-story](interactive-story/README.md) |
| 代码梳理 | LayerWeave 自身的模块、入口与调用关系 | [code-navigation](code-navigation/README.md) |
| 多智能体协作：晚开的花 | 四幕动态 SVG 与 32 条协作批注 | [late-bloom-scroll](late-bloom-scroll/README.md) |
| 手书制作 · 无视频阅读版 | 歌曲段落、故事、画面设计、实现与总览静帧 | [donut-hole-tegaki](donut-hole-tegaki/README.md) |
| 动态分镜与 H3 · 无视频阅读版 | 60 个镜头、40 张片段静帧、生成方案与关联 | [donut-hole-h3](donut-hole-h3/README.md) |

前九个案例可通过基础 Python/CLI 阅读；画布操作需要完整版本。晚开的花含视图专属批注类型，使用完整版本导入。手书和 H3 的默认阅读无需音视频，参考网页和源工程的额外条件分别写在案例说明中。软件首页只推荐少量入门路线，完整清单在这里维护。

## 无视频案例与可选素材

手书和 H3 的公开 project.json 把本地视频改为图片展示，把未附音频与外部视频页面改为文字说明；保留对象起止位置、层级及关联。information.original_media 记录原资源位置与配置，仅供以后人工恢复参考，不触发下载。静帧不代表动态效果。

完整音视频、未选入的图片零件及制作工作目录不进入公开案例包。以后如提供素材补充包，可作为版本对应的 Release 附件，并在各案例中给出解压位置；当前没有自动下载器，也不要求安装案例时下载这些素材。

## 扩充自己的案例

每个案例单独一个目录，至少包含 README.md 与 project.json，图片、正文等按需放入 assets。README 说明目标、准备、导入与阅读路线；项目数据用现有交换接口生成，不另设导入协议。保持相对路径，不附本地密钥、数据库、依赖缓存或制作日志。

新增后补到本页，并实际导入、查询、复查及核对本地素材。记录素材来源与使用条件，第三方网页通过链接提供。修改后的排版可以通过现有交换工具导出，不要求案例使用固定层数或布局。

案例代码与本项目原创说明使用 [MIT](LICENSE)；外部文章、参考作品及素材遵循各案例的来源与权利说明。

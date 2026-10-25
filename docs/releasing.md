# 构建与发布验收

发行版本只在 `src/layerweave/__init__.py` 的 __version__ 维护，pyproject 和 MCP 服务读取同一来源。组件版本仍由各 component.toml 维护；视图版本同步到 frontend/view/package.json，SDK 快照通过构建生成。

## 准备和构建

从仓库根的开发虚拟环境执行：

```sh
python -X utf8 -m pip install -e ".[mcp,dev]"
```

改过网页或视图版本时，在 frontend/view 中执行 npm ci 与 npm run build。构建同时生成 SDK、语言资源和根目录 THIRD_PARTY_NOTICES.md；后者取自实际打入网页的依赖包及其许可证，不手改生成文本。

构建前确认工作区要发布的文件已纳入版本控制，移走或清理已确认可再生成的 build 目录，避免旧资源残留；保留 scratch、output、skills 和本地配置。然后执行：

```sh
python -X utf8 -m build --sdist --wheel --outdir dist
python -X utf8 -m tests.packaging.check_wheel dist/layerweave-0.7.10b1-py3-none-any.whl
python -X utf8 -m tests.packaging.check_launcher dist/layerweave-0.7.10b1-py3-none-any.whl
python -X utf8 -m tests.packaging.check_mcp_wheel dist/layerweave-0.7.10b1-py3-none-any.whl
python -X utf8 -m tests.packaging.check_sdist dist/layerweave-0.7.10b1.tar.gz
```

上述步骤只在本地构建和验收，不上传包仓库。上传位置、版本标签和正式发行说明应在实际发布时明确选择。

统一入口版本为 Python 0.7.10b1 与 npm 0.7.10-beta.1，npm 预览使用 next 通道。npm 版本与固定的 Python 版本在 distribution/npm/package.json 声明，版本一致性由 npm 测试验证。在 distribution/npm 下执行 `npm test` 与 `npm pack --pack-destination ../../dist` 生成独立启动包。

构建钩子 setup.py/build_support.py 从 examples/showcases 自动生成案例清单，并只把 distribution/demos.json 声明的文章案例压缩进 wheel；其他案例保留版本固定的远端 ZIP 与 SHA-256。不要手改生成资源或把个人案例库放入安装包。

发布到 PyPI 前，维护者需要 PyPI 账号与首次发布授权，可配置 GitHub Trusted Publishing；npm 需要独立账号和首次发布授权。先验收同一批 wheel、sdist 和 npm tarball，再上传；GitHub Release 与 PyPI 使用同一份 Python 发行物，不分别重建。包名简写只在对应索引发布后写成可直接执行的安装说明。此前发布的 0.7.8 保持原样。

0.7.8 已作为公开预览版发布。GitHub 的默认展示分支与 Release 目标均使用 visualization，main 保持无视图开发源码。后续使用与 Python 发行版本对应的新标签（本轮预览为 v0.7.10b1），不覆盖已发布版本；预览版标记 pre-release。官方插件使用独立仓库与各自版本，不随宿主自动安装。地址与授权就绪后再创建新 Release，本地准备不等于发布。

## 软件发行物与案例包

源码包同时包含 README.md 和 README.en.md，两份首页的安装命令及分支说明保持一致。GitHub/Gitee 多平台发布时，从同一提交构建一次，上传相同版本、相同文件和校验值，避免分别打包。仓库和发行地址确认存在后再加入首页；可编辑分支与已发布的版本标签分别标明。

普通使用优先通过 uv 准备 Python 与隔离环境并安装下载的 wheel；已有 Python 也可用 pip；MCP 的 uvx 用法见其安装说明。公开下载 URL 就绪后可验证 URL 安装，再提供对应命令；PyPI 发布完成后才提供按包名安装的命令。不把本地路径示例写成已经上线的网络安装器。独立 Windows 安装器或自带运行环境的便携包仍是另一项交付工作。

wheel 只安装 layerweave 命名空间、运行所需配置/技能/网页资源、启动器预置的文章案例、模块手册和许可文件；不安装 tests、其余案例、前端开发依赖或本地数据库。预置案例使用时复制到工作目录，不直接编辑安装资源。使用接口从实时 help 查询；需要完整仓库文档、示例和网页源码时取得 sdist 或仓库源码。

本页的发行物来自 visualization。main 用作无视图的开发源码，核心、支撑与非视图工具同步，保留可编辑安装需要的最小元数据，不另行发布同名同版本的开发分支 wheel。视图、MCP 服务与发行构建在完整分支维护；两分支都使用 layerweave 导入名，开发环境按用途选择一份源码安装。

sdist 包含 Python 源码、完整文档、示例、测试夹具、前端源码与锁文件，以及已经编译的网页。用户从 sdist 安装 Python 包无需先装 Node；修改网页再执行前端构建。验收会解包到临时目录重建 wheel，确认不依赖原工作区的 scratch、node_modules 或临时文件。

技能允许携带支持脚本和素材；本地缓存、.env、密钥 JSON、日志和 SQLite 文件由打包排除规则过滤。验证同时检查归档内容；不能把 .gitignore 当成所有构建后端的资源过滤规则。

## 维护和接口边界

按[测试导引](../tests/README.md)执行完整 Python 回归，记录任何跳过项；前端构建也须通过对应测试。修改基础入口时保留核心/支撑独立运行和各完整工具包隔离验收。

稳定 Python 入口包括 core/models 的显式导出、support.api、编号接口、工具公开声明及专题中明确说明的开发辅助入口（如 commands/providers/feedback/paths）。内部模块仍可读取与调试，__all__ 和下划线不是安全屏障；不因为实现细节可导入就把它自动登记成 MCP 能力。原始读写、会话组合与恢复保留给工具开发者，模型调用继续走已声明命令。

LayerWeave 自身采用 [MIT](../LICENSE)，网页中第三方内容保留其原许可与版权声明。当前发行物包含 MIT、ISC 和 BSD-3-Clause 组件，因此分发元数据记录组合表达式 MIT AND ISC AND BSD-3-Clause；这不改变项目自身的 MIT 授权。升级前端依赖时同时核对生成声明与该表达式。许可文本参考 [OSI MIT](https://opensource.org/license/mit)，分发元数据依照 [Python Packaging 的组合许可示例](https://packaging.python.org/en/latest/guides/licensing-examples-and-user-scenarios/)维护；独立安装的插件、技能和外部服务仍遵循自身条件。

## 案例分发

examples/showcases 保存十二个案例的公开副本，文章解析为首页入门路线。手书与 H3 使用静帧版 project.json：保留层级、位置与关联，不附音视频；完整制作交付留在本地归档，不能从归档目录构建公开包。各案例说明标明原型源码需要另备的素材，不承诺缺素材的原型可完整播放。

全部案例随 sdist 提供；wheel 只预置文章解析，其余按需下载既有案例包。更新远端案例包时，也可独立打 ZIP。在完成归档内容检查后，从干净源码目录执行：

```powershell
python -X utf8 -m zipfile -c dist/layerweave-showcases-0.7.8.zip examples/showcases
```

ZIP 顶层是 showcases，使用者解压到自己工作目录的 examples 中。验证其中没有音视频、SQLite、密钥、日志、node_modules 或 Python 缓存；本地导入产生的数据库和反馈文件不应带入包。核对所有 project.json 能从新库导入、媒体相对路径存在，并用普通安装的 wheel 运行文章解析。分别记录 wheel、sdist、案例 ZIP 的 SHA-256。

源码包清单单独排除案例音视频与制作缓存，不仅依赖 .gitignore。可选媒体以后若作为 Release 附件分发，应匹配案例版本，写明来源、解压位置和恢复方式；启动器可按需下载已发布的案例包，不自动取得完整制作媒体。发布时使用真实下载地址，准备阶段不写未上线的 PyPI 命令。

## PyPI 可信发布

.github/workflows/publish-pypi.yml 由维护者手动指定已公开的 GitHub Release 标签执行，只下载已经验收的 wheel、sdist 和 SHA256SUMS，逐文件核对后原样上传，不重新构建。先公开 Release 再启动此工作流；只读工作流无法取得草稿附件。PyPI 的可信发布者绑定 GitHub owner aceddad、repository LayerWeave、workflow publish-pypi.yml、environment pypi；使用短期 OIDC 凭据，无需在仓库保存 PyPI token。首次发布需先在 PyPI 账号的 Publishing 页面登记 pending publisher。

## 包索引介绍

根目录 README.md 与 README.en.md 是介绍文案的唯一来源。distribution/prepare_readmes.py 用同一套转换生成 distribution/PYPI_README.md 和 distribution/npm/README.md、README.en.md：图片使用版本标签下的 raw URL，文档与章节跳转使用对应标签下的 GitHub URL，代码示例保持原样。npm 专有的运行环境与缓存说明集中在[启动器手册](../src/layerweave/tool/builtin/shared/launcher/README.md#npm-运行环境)。

Python 构建钩子和 npm 的 prepack 都调用该生成器。维护者执行 npm pack 前须激活开发用 Python 3.11+ 环境；生成器仅依赖标准库，普通 npm 用户安装包时不会运行它。可在仓库根用 `python -X utf8 distribution/prepare_readmes.py` 提前更新并检查生成文件；npm 的两份生成文档提交到仓库，但不手工编辑。

PyPI 和 npm 的在线介绍保留发布时的快照，不随仓库提交自动刷新。仅修改文档也使用新版本号，npm 的版本和固定 Python 版本一起更新；保留此前发行物。发布验收核对 wheel 元数据里的介绍与 npm tarball 的 README.md 完全一致，中英文命令一致，图片及文档链接在对应版本标签下可访问。

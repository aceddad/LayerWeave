# 视图插件：使用与开发协议 v1

接缝、一览、预览和网页在[独立插件仓库](https://gitee.com/emotion1354414/layerweave-plugins)发布，由用户选装。插件管理自视图 0.28.0 提供，网页插件需要视图 0.31.0+。主程序不携带它们的执行文件，零插件时可以正常使用画布。插件管理不改业务数据库。

## 先查，再选择安装

```sh
python -X utf8 -m layerweave.tool.builtin.view.plugins market
python -X utf8 -m layerweave.tool.builtin.view.plugins info layerweave.preview
python -X utf8 -m layerweave.tool.builtin.view.plugins install layerweave.preview
python -X utf8 -m layerweave.tool.builtin.view.plugins list
```

网页顶栏的「插件」使用同一份管理逻辑，直接展示官方推荐和可安装版本、来源。查看目录、项目或链接都不会自动安装；详情可能下载并缓存 ZIP 以读取 README，但不会登记或执行它。

| 动作 | 用途 |
|---|---|
| 不带动作 / `list` | 本机已登记插件、版本、开关、安装方式和问题 |
| `market [ID] [--catalog 引用]` | 目录概览；给 ID 时展开各版本和兼容条件 |
| `info ID [--catalog 引用] [--version 版本]` | 本机详情优先；显式选择远端时读取对应声明、参数和 README |
| `install ID [--catalog 引用] [--version 版本]` | 选择兼容版本安装；指定版本可以切回旧版 |
| `install --file 路径.zip` | 离线安装完整发布包，身份从包内读取 |
| `update [ID]` | 从原安装目录更新指定或全部受管理插件，保留开关；只在明确调用时执行 |
| `add 路径 [--name 短名]` | 链接开发目录或 JS 文件；不复制源码 |
| `on ID` / `off ID` | 只切换开关，不下载安装 |
| `remove ID` | 解除登记，保留文件 |
| `remove ID --files` | 解除登记，并将安装器拥有的文件移至可恢复目录；不删除链接源码 |
| `migrate` | 显式迁移旧清单，保留原始备份与开关偏好，不自动安装官方插件 |

所有动作支持 `--json`，测试和独立环境可用 `--state-root 临时目录`。Python 入口为 `plugins.plugin(action, target, *, root=None, catalog=None, version=None, file=None, files=False, name=None)`。安装结果和页面加载结果分开：包可以安装成功，但页面工厂或组件仍可能出错；CLI 没有实际页面证据时返回 `runtime="unverified"`。

批量更新逐项报告，不因一项失败破坏其他已成功项。新版本下载、检查或准备失败时旧登记不动。已经安装的插件不依赖市场在线；开发链接和离线安装没有目录更新来源，`update` 会跳过并解释。

## 身份和本机位置

完整 ID 是 `publisher.name`，如 `layerweave.preview`、`alice.preview`。两部分分别满足 `[a-z][a-z0-9_-]{0,39}`，不含点；`label` 和 `author` 是展示文字，可以使用中文。作者展示名不参与身份，发布方标识也不代表认证。

页面、侧栏和截图都使用完整 ID：`view=layerweave.preview`、`--view layerweave.preview`。同名不同发布方可以并存；相同 ID 不能从另一个目录或开发链接静默覆盖，切换来源先明确解除登记。

本机清单是 `~/.layerweave/view/plugins.json`：

```json
{
  "format": 1,
  "catalog": "https://gitee.com/emotion1354414/layerweave-plugins/raw/main/catalog/index.json",
  "plugins": []
}
```

这是空清单格式示例，不要覆盖已有清单。`catalog` 可省略，也可以填本机 `index.json`；`--catalog` 只覆盖本次查询或安装。更换默认目录不会改变已有插件的更新来源。

安装记录保存 `id`、`kind`、`mode`、`root`、`entry`、`version`、`on`。受管理的 `mode="managed"` 还保存 `origin`：真实目录、实际包位置、大小和 SHA-256；开发链接用 `mode="link"`。受管理文件在 `plugins/_managed/pkg-<ID>/<版本>/`，旁边保存安装收据；缓存和准备目录不代表已安装。

`remove --files` 回收的位置由结果的 `recycled` 返回，当前位于 `plugins/.trash/`；无文件归属证据时只解除登记。旧版本文件可保留，但同一 ID 只有一个当前登记。

旧清单读取时先做只读预览并返回 `migration_pending`。用户明确执行 `migrate` 后才备份为 `plugins.pre-v1-<时间>.json` 并写新格式。原开发链接保留路径和开关，默认身份为 `local.<原名>`；冲突或不可转换项留在 `unresolved_legacy`，不会被悄悄丢弃。已知官方短名只映射到对应 `layerweave.*`，不猜第三方。

## `plugin.json`

公开发布的视图插件在 ZIP 根目录提供这份声明。完整最小示例：

```json
{
  "format": 1,
  "kind": "view-plugin",
  "publisher": "alice",
  "name": "example",
  "version": "1.0.0",
  "label": "示例页面",
  "description": "按给出的对象编号展示项目内容。",
  "requires": {"view": ">=0.27.0", "host_api": [3]},
  "entry": "dist/plugin.js",
  "usage": "README.md",
  "slots": ["page"],
  "params": {
    "object_ids": {
      "type": "array",
      "items": {"type": "integer"},
      "required": true,
      "description": "需要查看的对象编号。"
    }
  }
}
```

该例子是假设的插件声明，不代表官方预览支持 `object_ids`。ZIP 还需要实际的 `dist/plugin.js`、配套资源与 README。

| 字段 | 约定 |
|---|---|
| `format`、`kind` | 必填，目前为 `1`、`view-plugin` |
| `publisher`、`name`、`version` | 必填；ID 计算得到，不在 manifest 重复手写 |
| `label`、`description` | 必填，名称和用途；统一用 description |
| `requires` | 必填，视图版本范围与明确支持的 host_api 代数列表 |
| `entry` | 默认 plugin.js；相对于包根，支持子目录 |
| `usage` | 默认 README.md，发布包中必须存在 |
| `params` | 默认空对象，按参数名索引 |
| `handles`、`slots` | 可选说明性数组，实际运行贡献由 JS 返回 |
| `locales` | 可选的语言代码 → 包内语言文件路径；消息、展示元数据和说明见[语言包](LANGUAGES.md) |
| `author`、`license`、`license_file`、`languages` | 可选作者、许可、许可文件和语言说明；不推测作者许可 |

未知字段可保留，未知格式明确报告。本地 `add` 可以没有 manifest，这时生成 `local.<短名>`，兼容性标为“未声明”；有 manifest 时不能用 `--name` 改写身份。说明文件至少写用途、适用场景、参数、完整例子和依赖条件。

## 参数与兼容版本

参数项必填 `type`、`description`，`required` 默认 false，可选 `default`。支持 string、integer、number、boolean、array、object；数组提供 `items.type`。不递归分析对象的业务字段。参数名使用 `[a-z][a-z0-9_]{0,31}`，不能占用项目、截图控制等宿主字段。

`default` 描述插件实现的默认值，宿主不替插件注入默认参数；`required=true` 不同时声明 default。动态默认行为写在 description 中。

截图仍使用重复的 `--param 名字=值` 参数。多个不同参数用多个 `--param`；一个参数的多个值用 JSON 数组文本，例如 `--param 'object_ids=[12,18]'`。重复同名参数采用最后一个值。字符串如 `1f` 原样传递，布尔写 `true/false`，对象写 JSON 文本。

显式页面的必填缺失或类型不符时停止截图；未声明参数 warn 后照常传入。没有 manifest 时只检查参数名和宿主保留字段。复制链接与 `--link` 保留插件参数，显式 `--param` 覆盖链接里的同名值。侧栏参数不做跨插件合并，仍由插件解释。

插件版本使用三段数字，按数字比较；范围支持 `>=最低版本` 或 `>=最低版本,<最高版本`，例如 `>=0.29.0`、`>=0.29.0,<1.0.0`，不支持通配符、预发布、`^`、`~`。当前视图版本和 `host.api` 必须分别满足声明；`host_api: [3]` 不自动支持 4。安装与每次加载都检查。未指定版本时选最高兼容版本，不要求一定是目录最新版本。

## 运行接口与类型快照

插件默认导出 `(host) => ViewPlugin`，入口使用已构建的 ES 模块。React 从 `host.React` 取得，不打包第二套。样式用 `host.addStyle`；插件停用时宿主移除已登记的贡献和样式。

视图 0.29.0 增加 `host.t()` 和 `host.useI18n()`，使用它们需声明相应最低视图版本。`host` 还提供 `useView()`、对象选择和跳转、截图就绪通知，以及图片、帧、波形、分页等组件。完整类型从实际源码生成并随包提供：[host-api-3 类型入口](sdk/host-api-3/index.d.ts)。声明文件只有类型，没有宿主实现。开发仓库固定复制此目录，通过 `import type` 引用，不引用主仓库源码。

| `ViewPlugin` 栏位 | 用途 |
|---|---|
| `page` | 顶栏专用页面 |
| `side` | 侧栏标签 |
| `objectDetail` | 选中对象的补充详情 |
| `jumpPoints` | `[ ]` 键的跳转位置 |

`label` 是运行标签，`handles` 可限定对象种类。运行身份以清单为准，通常无需返回 `name`。`host.api = 3` 是接口代数：1 提供页面和跳转点，2 曾增加画布格子，3 收回格子栏位。`block` 当前不可用。

插件页面实际画完后调用 `host.markReady()`。截图会等待媒体和页面就绪；未安装、已关闭、不兼容、缺少目标栏位、加载或渲染失败、等待超时都报告失败，不静默生成画布截图。正常交互可明确选择返回画布。普通插件失败不影响其他插件。

资源地址包含 ID 和修订标识，相对导入也随版本换地址，避免入口更新而分块仍用旧缓存。资源从包根解析，不从 entry 的父目录猜测。开发文件改动后可完整刷新页面，不承诺源码树热更新。

### 本地 HTML 资源入口

视图 0.31.0 在 host.api 3 上新增 `host.openDocument(file, root?)`，返回 `{url, name}`。相对路径基于数据库目录；默认资源范围是 HTML 所在目录，也可明确提供包含它的共同目录。目录内相对图片、CSS、JavaScript 模块和 JSON 可随页面读取，超出该目录的路径不提供。

入口只在当前服务进程中登记，不写数据库或本机状态，因此截图模式也可使用。临时 URL 不应保存进项目；项目保存原始文件路径。HTML 响应保留脚本能力，但用 CSP sandbox 隔离其来源；资源响应允许该隔离页面读取，项目 API 不开放对应跨源读取。支持相对资源，不自动重写站点根路径或启动开发服务器。

独立网页插件使用这个接口；其它插件也可以复用。参数、对象字段与外部网站的嵌入限制以 `view_plugin info layerweave.web` 的说明为准。

## ZIP 与静态目录

一个 ZIP 对应一个 ID 的一个版本，根目录直接放 plugin.json，不套额外仓库目录。只分发已构建网页资源和说明，安装时不运行脚本、不执行 npm/pip、不处理 Python 依赖。

独立仓库的 `tools/package_plugin.py` 从各插件 dist 和说明生成可重复 ZIP；`tools/build_index.py` 读取版本 ZIP 生成目录。作者不用手工同步两份元数据或计算哈希。语言文件及其说明按 manifest 声明显式打包，目录只提取本地化的名称和简介。先发布包，再更新目录；同 ID、同版本的内容不原地修改。

目录结构为 `{"format":1,"plugins":[...]}`，每项有 `id`、`publisher`、`name`、`kind`、`version`、`label`、`description`、`requires` 和 `archive`。archive 包含实际 URL、ZIP 字节数 size、64 位十六进制 sha256；相对 URL 以目录文件为基准。同 ID 可保存多个版本。单条损坏单独报告，其余继续显示；未知种类标为暂不支持安装。

下载核对大小、哈希和声明一致性，ZIP 路径须留在准备目录、不接受符号链接，入口与说明文件须存在；全部准备好才切换清单。SHA-256 证明内容与选定目录一致，不是安全认证。插件仍在当前页面执行。

## 源码维护与扩展位置

| 模块 | 职责 |
|---|---|
| `plugin_manifest.py` | 声明、兼容范围、基础参数解释 |
| `plugin_store.py` | 本机清单、锁、原子写、显式迁移 |
| `plugin_market.py` | 目录、发布包、安装更新、详情与回收 |
| `plugins.py` | 对外 Python/CLI、查询与开发链接 |
| `server.py`、前端 `src/plugin/`、`PluginManager.tsx` | 同一管理能力的网页接入和运行加载 |

宿主 `frontend/view` 执行 `npm run build` 时生成 SDK 和网页，不再构建官方插件。官方仓库分别构建、测试和发布；宿主验收使用 `tests/fixtures/view-plugin`，不能重新依赖某个官方插件已安装。

`kind="python-component"` 仅预留查询和分流位置，当前不能安装。未来采用正常 Python 包和组件声明，不要求重复 plugin.json；发行环境、发现和执行另定。component.toml 用于组件声明与版本登记，不执行安装或发现 Python 组件。

## 插件语言包

视图 0.29.0 在 host.api 3 上增加 `host.t` 和 `host.useI18n`，并读取 manifest 可选 `locales`。工厂和组件不会因切换语言而重新创建；声明格式、资源放置与示例见[中英语言包](LANGUAGES.md#插件提供自己的语言包)。依赖这些方法的插件声明 `requires.view >=0.29.0`。

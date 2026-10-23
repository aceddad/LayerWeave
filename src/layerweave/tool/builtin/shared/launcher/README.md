# 统一启动入口

完整分支的启动工具包。uv、npm 和 `python -X utf8 -m layerweave` 共用这里的逻辑；复用现有建库、交换、模板、视图和 MCP 接口。核心不依赖本包。

## 使用

安装含启动器的 Python 包后，执行：

```sh
layerweave demo
layerweave demo --list
layerweave demo comic-creation --dir ./my-comic
layerweave view ./my-comic
layerweave view ./project.sqlite3 --project 1
layerweave new ./my-project --template subtitles
layerweave help project_overview
layerweave mcp --config ./mcp.json
```

`demo` 默认文章解析。首次准备到当前目录的 `layerweave-demo/<案例名>`，`--dir` 可指定其他位置。准备完成后打开浏览器，终端持续运行服务；Ctrl+C 停止服务，数据保留。`--no-browser` 只打印本机访问地址；`--port` 默认 0，由系统选择空闲端口。新项目默认字幕模板，其他名称来自现有 `template_help`。

`layerweave.json` 记录项目编号和来源，数据库固定为同目录的 `project.sqlite3`。再次运行会读取已保存的编号，保留对象、批注、布局和素材修改；不重新导入。整个目录可以搬走，再用 `layerweave view 新目录` 打开。已有的普通数据库也可直接交给 view；多个项目可用 --project 选择。

目标目录存在但没有启动器元数据，或属于其他案例/模板时，命令会提示换个目录；不会覆盖已有文件。初次准备在同一父目录的临时目录完成，成功后移到目标位置，失败后可直接重试。MCP 仍需 `layerweave[mcp]` 可选依赖；原来的 layerweave-mcp 入口继续可用。

## uv / npm 启动

Python 版本为 `0.7.9b3`，npm 版本为 `0.7.9-beta.3`。在自己的工作目录选择一种方式：

```powershell
uvx layerweave@0.7.9b3 demo
npx --yes layerweave@0.7.9-beta.3 demo
```

npm 自动管理运行环境，支持 Windows x64、Node.js 20+；无需预先安装 Python 或 uv，详细机制见下方 npm 运行环境。已有本地 wheel 时也可使用 `uvx --python 3.11 --from ./layerweave-0.7.9b3-py3-none-any.whl layerweave demo`。npm 使用预览通道 next，上面的明确版本命令不受通道变更影响。

## npm 运行环境

npm 包只准备运行环境并转交参数，案例、数据库、视图与 MCP 使用同一份 Python 实现。安装 npm 包不会创建项目；首次执行才准备运行环境。MCP 自动选择固定版本的 mcp extra，stdout 保留给协议，准备提示写到 stderr。

优先使用 PATH 中可用的 uv >= 0.13.4；没有或版本过旧时下载固定版本的官方 uv，核对 SHA-256 后解压到用户缓存。显式指定的 LAYERWEAVE_UV 若版本过旧则提示更新。该最低版本包含 emSign 证书事件的修复，详见 [uv 安全公告](https://github.com/astral-sh/uv/security/advisories/GHSA-hq85-5cpj-mr62)。uv 自动准备独立的 Python 3.11 与 LayerWeave 环境，不修改 PATH 或 shell 配置。首次准备需要网络，后续可复用缓存。

| 环境变量 | 用途 |
|---|---|
| LAYERWEAVE_CACHE_DIR | 更改缓存位置，默认 `%LOCALAPPDATA%/LayerWeave/cache`；项目数据单独保存 |
| LAYERWEAVE_UV | 指定已有的 uv >= 0.13.4 可执行文件 |
| LAYERWEAVE_PYTHON_PACKAGE | 开发验收时指定本地 wheel 或完整 Python requirement；应匹配 npm 固定的 Python 版本，需要 MCP 时包含 mcp extra |

启动器源码在 distribution/npm/lib/launch.mjs，官方 uv 地址与校验值在 runtime.json。包中不含用户数据库、安装后脚本或另一份 Python 实现。维护者构建 npm 包时需要开发环境的 Python 3.11+ 来生成介绍文案；普通用户安装和运行仍由启动器准备环境。构建与上传流程见[发布指南](../../../../../../docs/releasing.md)。

## 资源与扩展

文章解析的原稿在 examples/showcases/article-reading；构建时生成安装资源，不维护第二份案例源码。安装包只预置该案例，其他案例第一次使用时下载版本固定、带 SHA-256 的案例 ZIP，并复用缓存。仅把选中案例复制到工作目录。后续打开已准备项目无需下载；用户数据不放入缓存。

下载缓存默认在 Windows 的 `%LOCALAPPDATA%/LayerWeave/cache`；可用 LAYERWEAVE_CACHE_DIR 改位置。缓存删除后可以重新下载，项目数据不受影响。

案例清单由 examples/showcases 下的 project.json 自动生成。distribution/demos.json 指定预置案例与远端案例包的版本、地址及校验值；新增远端案例时更新对应发布包和校验值，保持清单与档案一致。只增加入口组合时改本包，业务行为继续改对应工具；不把启动器登记为可由运行中 MCP 再次启动的动作。

对开发者开放的文件分工：catalog.py 管理案例来源和下载缓存，projects.py 管理一次性准备与重开，__main__.py 管理命令分流。视图仍由 view.server 提供；旧 serve 调用默认不会打开浏览器。

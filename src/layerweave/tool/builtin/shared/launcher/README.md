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

## 本地候选包与包索引

本次版本为 Python `0.7.9b1`、npm `0.7.9-beta.1`。PyPI/npm 发布授权完成前，使用本地构建包：

```powershell
uvx --python 3.11 --from ./layerweave-0.7.9b1-py3-none-any.whl layerweave demo
```

npm 启动器的本地包调用见[分发入口](../../../../../../distribution/npm/README.md)。包索引发布后，等价命令为 `uvx layerweave@0.7.9b1 demo` 与 `npx --yes layerweave@0.7.9-beta.1 demo`。这些版本目前尚未发布到索引。

## 资源与扩展

文章解析的原稿在 examples/showcases/article-reading；构建时生成安装资源，不维护第二份案例源码。安装包只预置该案例，其他案例第一次使用时下载版本固定、带 SHA-256 的案例 ZIP，并复用缓存。仅把选中案例复制到工作目录。后续打开已准备项目无需下载；用户数据不放入缓存。

下载缓存默认在 Windows 的 `%LOCALAPPDATA%/LayerWeave/cache`；可用 LAYERWEAVE_CACHE_DIR 改位置。缓存删除后可以重新下载，项目数据不受影响。

案例清单由 examples/showcases 下的 project.json 自动生成。distribution/demos.json 指定预置案例与远端案例包的版本、地址及校验值；新增远端案例时更新对应发布包和校验值，保持清单与档案一致。只增加入口组合时改本包，业务行为继续改对应工具；不把启动器登记为可由运行中 MCP 再次启动的动作。

对开发者开放的文件分工：catalog.py 管理案例来源和下载缓存，projects.py 管理一次性准备与重开，__main__.py 管理命令分流。视图仍由 view.server 提供；旧 serve 调用默认不会打开浏览器。

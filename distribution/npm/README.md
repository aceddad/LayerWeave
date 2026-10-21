# LayerWeave npm 启动器

简体中文 | [English](https://github.com/aceddad/LayerWeave/blob/v0.7.9b1/distribution/npm/README.en.md)

在 Windows x64 上，以一条命令启动 LayerWeave。npm 包只准备运行环境并转交参数，案例、数据库、视图与 MCP 的业务逻辑全部来自同一份 Python 包。

## 快速开始

在自己的工作目录中执行：

```powershell
npx --yes layerweave@0.7.9-beta.1 demo
```

本次 npm 预览版使用 next 通道，固定匹配 Python `0.7.9b1`。支持 Windows x64、Node.js 20+；不需要预先安装 Python 或 uv。

## 命令

- `demo`：准备并打开文章解析，默认保存到 `./layerweave-demo/article-reading`。
- `demo --list`：列出全部案例；其他案例按需下载。
- `demo comic-creation --dir ./my-comic`：在指定目录体验漫画案例。
- `view ./project.sqlite3` 或 `view ./my-comic`：打开已有内容。
- `new ./my-project --template subtitles`：创建自己的模板项目。
- `help project_overview`：查看现有详细 help。
- `mcp --config ./mcp.json`：启动 MCP；启动器自动选用对应版本的 mcp extra。

项目重复打开时保留修改。服务在前台运行，Ctrl+C 停止服务。`--no-browser` 只打印地址，`--port` 可指定端口。MCP 的 stdout 保留给协议，环境准备提示写到 stderr。

## 环境与维护

优先使用 PATH 中可用的 uv >= 0.9；没有时下载固定版本的官方 uv，核对 SHA-256 后解压到用户缓存。uv 自动准备独立的 Python 3.11 与 LayerWeave 环境，不修改 PATH 或 shell 配置。首次准备需要网络，后续可复用缓存。源码在 lib/launch.mjs，官方 uv 地址与校验值在 runtime.json。

默认缓存为 `%LOCALAPPDATA%/LayerWeave/cache`。LAYERWEAVE_CACHE_DIR 可改缓存位置；LAYERWEAVE_UV 可指定已有 uv；LAYERWEAVE_PYTHON_PACKAGE 可指定本地 wheel 或完整 Python requirement，供未发布包验证。自定义来源时请使用与 npm 版本相符的 Python 包；需要 MCP 时提供含 mcp extra 的 requirement。

构建 npm 包执行 `npm pack`；验证执行 `npm test`。包中没有项目数据库、用户素材、安装后脚本或另一份 Python 实现。发布需要维护者账号与授权，详见仓库发布说明。

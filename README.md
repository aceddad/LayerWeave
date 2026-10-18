# LayerWeave

用层、对象和关联组织内容，让 AI 与程序按需读取、编辑和扩充项目。

LayerWeave 提供 Python API、命令行工具、可选 MCP 接入和本机网页视图。它可以表达字幕、分镜、素材清单和有序信息列表：对象保存内容与起止位置，层组织结构，关联连接相关条目，轴说明位置数值的含义。

## 能做什么

- 查询层树、展开子树和时间区间，按名字或稳定键更新内容。
- 接续、分割、平移、复制与搬移对象，通过 JSON 批量导入导出。
- 用 SQLite 保存数据和修改历史，按操作撤销与重做。
- 通过 Python 类、TOML 配置和工具自有表扩充业务。
- 在画布上查看项目、添加批注、与 AI 协作；按需安装一览、接缝和预览插件。

图片、音视频等对象保存资源引用；具体媒体生成与处理由技能或调用方完成。界面支持中文和英文，用户内容保持原文。

## 开始使用

需要 Python 3.11+ 和 SQLite 3.35+。命令示例显式使用 `-X utf8`，让 AI 等程序通过 UTF-8 管道读取中文输出；也可在启动环境中设置 `PYTHONUTF8=1`，见[命令行编码](src/layerweave/tool/builtin/usage/README.md#命令行编码)。

取得 wheel 安装包后，在自己的虚拟环境中运行（路径换成实际文件）：

```sh
python -X utf8 -m pip install ./layerweave-0.7.5-py3-none-any.whl
```

需要 MCP 时安装对应可选依赖并配置客户端，见[连接 MCP](src/layerweave/tool/builtin/shared/mcp/README.md)。也可以取得源码后安装并运行示例：

```sh
python -X utf8 -m pip install -e .
python -X utf8 -B examples/read_write.py
```

示例使用临时数据库，演示创建、读取、关闭重开和再次保存。更多 Python 用法见[完整示例](docs/examples.md)。

从零开始时，先建数据库，再从场景模板建一个项目：

```sh
python -X utf8 -m layerweave.tool.builtin.developer.database.cli DATABASE
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli templates
python -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply DATABASE --template subtitles --new-project
```

templates 列出可用模板及用途；输出会给出新项目的编号。不用模板时，按 [CRUD 请求协议](src/layerweave/tool/builtin/usage/CRUD.md)自行创建项目和层。

已有数据库时，查看结构或打开视图：

```sh
python -X utf8 -m layerweave.tool.builtin.usage.query.project_overview DATABASE PROJECT_ID
python -X utf8 -m layerweave.tool.builtin.view.server DATABASE --project PROJECT_ID
```

DATABASE 与 PROJECT_ID 换成实际值；网页地址由服务输出。使用视图不需要 Node，开发前端才需要构建环境。当前包的 Python、CLI 和 MCP 可以直接使用，无需启动视图。main 是无视图开发源码分支，同步核心、支撑和非视图工具，供直接 Python/CLI 开发；视图、MCP 服务和发行封装在本 visualization 分支维护。

查询可用工具，无需数据库：

```sh
python -X utf8 -m layerweave.tool.builtin.shared.help.command_help
```

## 文档

- [使用 LayerWeave](src/layerweave/tool/builtin/usage/README.md)：AI 或程序操作项目，从任务选择工具并查询现有 help。
- [连接 MCP](src/layerweave/tool/builtin/shared/mcp/README.md)：安装可选依赖，用分层 help、直接 JSON 与常用独立入口操作项目。
- [开发自己的扩展](docs/build-with-layerweave/README.md)：通过公共接口开发工具、封装、自有表或视图插件。
- [维护 LayerWeave 源码](docs/developer-conventions.md)：修改本仓库的实现，准备开发环境并验证改动。
- [文档目录](docs/README.md)：各条路径的专题与完整示例。
- [官方视图插件](https://gitee.com/emotion1354414/layerweave-plugins)：独立选装，主程序不自动安装。

## 许可证

LayerWeave 自身采用 [MIT](LICENSE)。网页构建包含的第三方组件保留各自许可，见[第三方声明](THIRD_PARTY_NOTICES.md)。独立安装的插件和技能遵循其自身说明。

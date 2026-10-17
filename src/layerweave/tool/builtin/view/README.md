# 内部工具 · 视图工具

用本机网页查看层、对象、时序和关联，并通过批注与 AI 协作。每个根层及其子树是一块画板，可以拖动、缩放和拼接；AI 可读取当前位置、查看内容、截图和回复批注。[返回内部工具](../README.md)。

## 打开已有项目

安装带视图的 visualization 分支后运行：

```sh
python -X utf8 -m layerweave.tool.builtin.view.server DATABASE --project PROJECT_ID --port 8765
```

DATABASE 换成数据库路径，PROJECT_ID 换成已有项目编号；也可以省略 --project。打开命令输出的本机地址。服务只监听 127.0.0.1，网页已编译并随包提供，使用者不需要 Node。

顶栏可切换中文 / English，切换保留草稿、选择和插件状态。图片、视频和音频按对象引用显示；FFmpeg 可通过 PATH 或 `FFMPEG` 环境变量提供。AI 截图另外需要 Chrome、Edge 或 Chromium。

## 可选插件

一览、接缝、预览从[独立插件仓库](https://gitee.com/emotion1354414/layerweave-plugins)选装，零插件也能使用画布。顶栏“插件”可查询、安装和更新；CLI 入口为：

```sh
python -X utf8 -m layerweave.tool.builtin.view.plugins market
python -X utf8 -m layerweave.tool.builtin.view.plugins info layerweave.preview
```

查询不会自动安装。已安装旧插件需明确更新才使用新版本的语言资源，详见[插件说明](PLUGINS.md)。

## 数据写入范围

视图读取项目内容；需要修改作品数据时使用[使用工具](../usage/README.md)。视图自身允许写批注及其关联、折叠和已读状态，这些写入经过支撑层并记录历史。画板排版、当前视图位置、语言偏好和插件清单保存在本机，不写项目业务表。截图页面不执行这些写操作。

## 按任务阅读

| 任务 | 说明 |
|---|---|
| 画布操作、目录、批注、与 AI 协作 | [使用指南](GUIDE.md) |
| 选择 AI 读取、截图或批注命令 | [AI 工具入口](GUIDE.md#给-ai-用) |
| 修改数据接入、视图表或网页源码 | [开发说明](DEVELOPMENT.md) |
| 选装、编写和发布插件 | [插件协议](PLUGINS.md) |
| 中英使用、词条和插件语言包 | [语言包](LANGUAGES.md) |
| 测量性能、调整媒体绘制 | [性能说明](PERFORMANCE.md) |
| 读取快照、增量同步与缓存失效 | [增量协议](INCREMENTAL.md) |

当前版本以同目录 component.toml 为准。后续候选统一记录在[后续方向](../../../../../docs/FUTURE.md)，尚未实现的功能不作为当前接口承诺。

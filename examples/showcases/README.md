# 场景演示

这里存放面向使用者的完整场景案例，展示如何用层、对象、关联与视图完成实际工作。当前尚未收录完成的案例。

Python 接口的可运行示例见[示例指南](../../docs/examples.md)；预设层结构的起始模板见[JSON 交换与模板](../../src/layerweave/tool/builtin/usage/exchange/README.md)。[返回项目首页](../../README.md)。

## 每个案例一个目录

目录按场景命名，例如 article-reading。以下是布局示意，实际文件在需要时添加：

```text
examples/showcases/
├─ README.md
└─ <case-name>/
   ├─ README.md       # 场景目标、准备与导入步骤、建议阅读路线
   ├─ project.json    # 可通过交换工具导入的案例数据
   └─ assets/         # 按需提供的文章、配图等素材
```

案例说明写清楚能看到什么、怎样复现，以及需要的可选工具或视图插件。项目数据使用现有交换格式；导入、查询与修改复用现有工具和 help。素材位置与来源在各案例中说明；交换工具导入 JSON 不会自动搬运媒体文件。

案例按需从源码目录获取，不自动安装进 Python 包。需要视图的步骤使用 visualization 完整版本；可以只读写数据的部分注明 Python、CLI 或 MCP 的调用方式。添加案例时，在本页补上名称、用途和入口。

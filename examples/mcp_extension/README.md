# 无 CLI 的外部 MCP 工具

从 LayerWeave 源码根目录运行 `python -X utf8 -m pip install -e examples/mcp_extension`，重启 MCP。默认可发现 demo.summarize_text，独立入口为 demo_summarize_text，输入 `{"text":"第一行\n第二行"}`。函数只统计传入文本，不写数据库或文件。

不安装时，也可在 MCP 配置的 sources 中加入：

```json
{
  "namespace": "demo",
  "path": "examples/mcp_extension/src/layerweave_demo_tools/commands.py",
  "import_root": "examples/mcp_extension/src"
}
```

这些路径相对于 MCP workspace。实际可编辑安装若无法静态定位，也可使用这个目录声明；不会为了发现命令而执行模块。通常选择安装或目录配置一种来源，避免重复登记同一个完整身份。

将 exposure 中的 demo.summarize_text 设为 routed 可收起独立入口；通用 query 仍可调用。设为 disabled 列表中的成员则两条路径都不可用。完整说明见[MCP](../../src/layerweave/tool/builtin/shared/mcp/README.md)。

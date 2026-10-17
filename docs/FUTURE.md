# 后续可能更新

本页记录候选方向，不代表已经实现或确定实施。[返回开发指南](developer-conventions.md)。

## 数据库接入

现有[JSON 交换工具](../src/layerweave/tool/builtin/usage/exchange/README.md)支持项目、子树和对象导出、批量写回、复制时编号映射及工具表逻辑引用。交换 JSON 可以用于在不同数据库间搬运选定内容。

兼容的 SQLite 数据库可以通过现有入口直接打开；受支持的旧表结构由 initialize_database 显式升级。封装所需的 TOML 和 Python 类仍由运行环境提供，不存在数据库里。

如果后续需要直接适配不兼容版本或其他派生项目的数据库，再明确结构、配置和迁移关系。目前没有直接合并任意 SQLite 文件的通用适配器；优先复用已有交换格式和升级机制。

## 发行与对外接入

- 正式安装包、发行渠道和支持的平台范围。
- MCP 暴露哪些能力、如何分组以及怎样装载；当前公开调用仍为 Python 和 CLI。
- Python 组件的标准安装、发现与环境接入；视图插件市场目前只执行 view-plugin 的安装流程。

## 视图

视图、独立选装插件与中英界面已经实现。后续可按实际需求继续改善超大项目的偶发长帧和面板首次绘制；测量方式见[性能说明](../src/layerweave/tool/builtin/view/PERFORMANCE.md)。

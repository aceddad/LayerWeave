# 可运行示例

从项目 src 目录运行。示例使用内存或专用临时数据库。

在 src 目录运行完整数据读写示例：

```sh
python -X utf8 -B -m examples.read_write
```

此示例使用自己的临时数据库文件，演示创建层与对象、关闭重开、还原 Python 实例、修改并再次保存、读取关联和日志，不改动输出数据库。原有记录 CRUD 示例仍可用：`python -X utf8 -B -m examples.crud`。

反馈示例：`python -X utf8 -B -m examples.feedback`。先单列写入结果，再逐条显示诊断目标、字段、原因和检查范围；JSON CLI 可加 `--text` 使用同一格式。

诊断与精度示例：`python -X utf8 -B -m examples.diagnostics`。汇报等级在 [diagnostics.toml](../configs/logging/diagnostics.toml) 配置，完整格式见 [诊断配置说明](../src/runtime/validation/DIAGNOSTICS.md)。

派生封装示例：`python -X utf8 -B -m examples.title`。Title 继承 Text，标题 TOML 继承文字 TOML 并绑定 Title；普通文字层可同时装载两种对象，保存时不需要额外指定配置。

纯模型示例仍可用：`python -X utf8 -B -m examples.all_layers` 或 `python -X utf8 -B -m examples.text`。其中手动编号只用于演示内存结构，持久化时由核心分配编号。

查看第一批四个工具的完整演示：`python -X utf8 -B -m examples.first_batch`。只查看项目概览可运行 `python -X utf8 -B -m examples.project_overview`。真实数据库的用法和结果格式见 [内部工具说明](../src/tools/README.md)。

第二批六个写入工具的内存演示：`python -X utf8 -B -m examples.second_batch`，涵盖接续新增、连续排列、平移、对齐、修改时长和复制。

详细展开的内存演示：`python -X utf8 -B -m examples.project_details`，展示多棵子树按数值筛选后的精简结果；未命中的层仍显示 0 个直属对象。支持完整/精简文字与 JSON，不做单位换算。

复查、历史与撤销演示：`python -X utf8 -B -m examples.review_history`。复查支持项目、多棵子树和指定对象；历史按操作展示字段变化；撤销保留原编号和发号进度，发生冲突时整批不写，撤销的再撤销即重做。Python/CLI 参数见 [完整说明](../src/runtime/storage/HISTORY.md)。

子树工具演示：`python -X utf8 -B -m examples.subtrees`。一次删除完整子树及其出向关联，或在同项目、同父层复制一个新版本，自动重映射内部引用并返回编号对应表。两项操作均可整批撤销，用法见 [子树工具说明](../src/runtime/storage/SUBTREES.md)。

编辑工具演示：`python -X utf8 -B -m examples.editing`。分割由调用者提供切点和各段内容；平移支持按子树与起点选择；插空档明确指定范围，对跨界对象选择 split/keep/stretch/move；跨项目复制/剪切支持子树或选中对象，保留原数值，剪切使外部入向关联跟随新地址。写入使用已有事务和撤销，另演示只读空档查询，详见 [编辑工具说明](../src/runtime/storage/EDITING.md)和[工具指南](../src/tools/README.md)。

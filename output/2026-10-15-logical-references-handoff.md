# 逻辑引用与复制策略：视图层接入说明

日期：2026-10-15。基于 main 的交换工具版本 5fdbbb8 补充通用能力，未修改 visualization 分支、视图代码或真实项目数据库。

安装包版本升为 0.6.0，foundation 组件 0.5.0，exchange 组件 0.2.0。已有公共函数签名不变，交换格式仍为 v1；更新代码后在当前环境重新安装 LayerWeave。组件版本和安装包版本是分别记录的。

## 本轮解决什么

工具表现在可声明 logical_references，让交换工具知道某些整数列指向层、对象或其他工具记录。这些声明用于选取相关记录和复制换号，不产生 SQL 外键，不阻止删层、删对象或撤销目标创建。

exchange.on_copy 可选 include（默认）或 skip。skip 表示已有状态不随复制写入，适合已读进度。导出仍携带状态与声明，原项目的 update 可以继续使用它；复制导入时明确报告跳过。

两项都保存在现有 _layerweave_tables 的声明里，不增加业务表或列，不需要重建现有工具表。普通 references 仍是硬外键，行为没有改变。

## Claude 需要修改的声明

按目前视图代码的结构：

| 源码与声明 | 增加什么 | 目的 |
|---|---|---|
| view/fold.py 的 TABLE[KIND]，kind 为 view_layer | logical_references 指向 layer | view_layer 的 (project_id, id) 跟随目标层换号 |
| view/notes/reads.py 的 READ_TABLE[READ_KIND]，kind 为 view_note | logical_references 指向 object；exchange.on_copy=skip | 原项目更新可保留已读状态，复制的新项目重新记录 |

在原有完整声明中加入：

~~~python
# fold.py；已有 id_source、fields、默认值等保持原样。
"logical_references": [
    {"fields": ["project_id", "id"], "kind": "layer"},
],

# notes/reads.py；已有 reads 列继续保持 TEXT，不改成其他类型。
"logical_references": [
    {"fields": ["project_id", "id"], "kind": "object"},
],
"exchange": {"on_copy": "skip"},
~~~

view_note.id 对应批注对象；reads 的 TEXT 内容还含有读者和已读位置。工具不会解析这些嵌套编号。因此本轮选择整个已读状态不复制，避免只换行主键却留下旧游标。此策略不是清空源库，也不会删除目标库已有的已读记录。

## 旧库必须补登记

仅更新 Python 常量不会更新现有数据库。请在视图的初始化或显式升级路径中，以没有待提交事务的连接调用 register_tables，并在此之后导出。不要等下一次折叠/标记已读才触发，也不要让普通只读查询隐式写库。

两处声明已加入上述元信息后，可复用完整声明：

~~~python
from layerweave.support.api import register_tables, table_specs
from layerweave.tool.builtin.view.fold import KIND, TABLE
from layerweave.tool.builtin.view.notes.reads import READ_KIND, READ_TABLE

# connection 是视图已有的 LayerWeave 数据库连接，没有待提交事务。
register_tables(connection, {**TABLE, **READ_TABLE})

specs = table_specs(connection)
assert specs[KIND]["logical_references"] == [
    {"fields": ["project_id", "id"], "kind": "layer"},
]
assert specs[READ_KIND]["exchange"] == {"on_copy": "skip"}
~~~

这里的 view 导入路径属于 visualization 分支，不是 main 的可运行示例。main 中独立可运行的通用例子是 [examples/logical_references.py](../examples/logical_references.py)。

重复登记相同声明可以直接执行；补元信息不改写数据、编号或业务日志。声明修改不属于内容撤销。旧声明省略新属性时会保留已登记的值；显式 logical_references=[] 可清除，显式 exchange={"on_copy":"include"} 可恢复默认复制。

源库补登记后重新导出最稳妥；旧文件本身没有这些引用含义。目标库若已经登记新声明，导入旧文件也会保留目标规则。已有错误副本不会被自动修复；本轮不猜测历史编号对应关系。

## 导入导出及反馈

原有调用不变：

~~~python
from layerweave.tool.builtin.usage.exchange import export_project, import_project

# source、target 是两端已初始化的连接；项目编号使用实际查询结果。
document = export_project(source, source_project_id, op="add")
result = import_project(target, document, project_id=target_project_id)
~~~

完整项目和局部子树均根据声明处理工具数据；保持 include_tools=True（默认）。可以先导出 update，修改后写回；把节点操作改为 add 时，同样会执行复制策略。

导入把“op=add 且节点 id 为正整数”理解为复制旧记录。对 on_copy=skip 的节点：

- 不创建状态行，不为该行写改动日志。
- issues 中返回 code=copy_policy、effect=skipped、pointer、kind、source_id。
- counts.skipped 增加，data.status 为 partial；ok=true 表示其余实际业务写入成功提交。
- 依赖这个被跳过节点的记录也明确跳过，不会借用目标库同号旧记录。

全新 add 不带节点旧 id。provided 表需要指定目标身份时，在 data.id 中提供，或用 refs.id 指向文件内新层/对象；这种新建不受 on_copy=skip 限制。update/delete、没有 op 的上下文，以及普通 CRUD 也不受限制。

表准备时保留目标已有逻辑引用，并补入来源引用；相同引用名含义不一致则报错。任一方声明 skip 就保留 skip，旧文件不会解除目标规则。需要调整元信息时由开发者显式 register_tables。

## 保留的边界

- 逻辑引用不改变删除和恢复的依赖检查；scoped 工具表原有的项目外键仍在，删除整个项目仍需处理项目下工具记录。
- 不推断业务列、JSON 或 TEXT 内的引用，不引入针对 view_layer/view_note 名称的特殊分支。
- 本轮接入的是 exchange 导入导出；editing 的 copy_subtree、跨项目剪切等入口不会因此自动复制全部工具数据。
- 表声明必须能够说明真实的引用含义；找不到来源映射时，默认跳过并报告，不以相同数字替代身份。
- 业务写入仍共用事务和日志，实际复制的记录可以按操作编号一起撤销；表准备与元信息登记不随业务撤销回退。

详细契约见[工具表开发指导](../docs/build-with-layerweave/03-managed-tables.md#逻辑引用与复制策略)和[交换格式](../src/layerweave/tool/builtin/usage/exchange/FORMAT.md#工具表)。

## 验证结果

- 完整回归 584 项：583 项通过，1 项因当前 Windows 环境不支持测试目录符号链接而跳过；无失败。
- 新增 20 项专项测试，覆盖错开编号、局部导出、普通业务列与独立工具表引用、复制跳过、依赖传播、旧库补登记、旧文件兼容、硬外键及撤销边界。
- 无工具的支撑层、每次仅保留一个完整工具包的隔离验收通过；exchange 单独安装时可消费新声明。
- 0.6.0 wheel 的普通安装验收通过，104 项资源与源码一致，33 个命令正常发现；没有借用可编辑源码。
- logical_references.py、exchange.py、tool_tables.py 三个示例实际执行通过；469 个本地文档链接与章节跳转检查通过。

专项复现中，来源故事层编号 2 在目标变为 3，折叠状态随之变为 3；已读状态明确跳过，复制的业务记录可整批撤销。

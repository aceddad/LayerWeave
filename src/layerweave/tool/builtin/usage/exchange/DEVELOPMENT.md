# 扩充交换工具

这是一整个可增减的内部工具包。仅依赖 core/support，不导入其他可选工具包；格式见 [FORMAT](FORMAT.md)，调用见 [README](README.md)。

## 按任务修改

局部导出的表定义从实际工具记录出发，递归补齐硬引用与逻辑引用的目标定义；使用访问集合处理循环，补定义不扩张记录选择。compact 只在输出时省略定义和来源发号说明，不改变选中数据、引用映射、复制策略与基线检查。JSON、文件包装和 CLI 复用 export_project 的 compact 参数。

| 任务 | 修改位置 |
|---|---|
| 新增场景模板 | templates 中增加 JSON，或放在外部模板目录；填写 name/when，template_help 自动发现 |
| 让已有工具数据一起交换 | 用 register_tables 声明字段、身份、硬引用或逻辑引用；导出器读取数据库中的声明 |
| 让某类旧状态不参与复制 | 表声明 exchange.on_copy=skip；不改变普通 CRUD 和原项目更新 |
| 新增文档元信息或调整摘要 | format.py；不要让展示信息变成数据库字段 |
| 调整导出范围、工具依赖收集 | exporting.py；始终共用 read_snapshot |
| 调整归属、跳过、编号和引用解析 | importing.py 的 Importer；写入仍走 write 原语 |
| 新增操作符 | format.OPS、Importer._execute 及 CLI/COMMANDS；补充 FORMAT 与行为测试 |
| 新增格式或文件读写方式 | files.py；第一版仅支持 JSON |
| 增加命令参数、就地帮助 | cli.py 中的解析器与字面量 COMMANDS |

不需要为新模板改 Python 或维护中央清单。模板若要创建新封装，调用环境先安装相应类/TOML；JSON 只引用 config_ref。

## 与现有写会话组合

表结构声明使用独立事务，先在外层准备，再组合业务操作：

~~~python
from layerweave.support.api import run_operation
from layerweave.support.providers import optional_checker
from layerweave.tool.builtin.usage.exchange import prepare_exchange, import_project_in_session

prepare_exchange(connection, document)

def work(write):
    report = import_project_in_session(write, document, project_id=project_id)
    write.update("project", project_id, {"tips": "导入后补充说明"})
    return report

result = run_operation(connection, work, checker=optional_checker())
~~~

connection/document/project_id 由调用方提供。表已准备时可以省略 prepare_exchange；不要在已有写会话中调用独立 import_project。事务内入口不提交、不运行内容检测，由最外层决定检查与回滚。

## 执行边界

解析器先建立文档身份与 key 索引，再按父子次序执行。未知新身份的引用进入待处理队列；目标完成后再处理。归属不一致、基线不匹配、外部引用未映射及依赖被跳过，都产生不执行的 warn。无进展的引用循环明确报告，不能悄悄使用旧编号。

已经决定不执行的节点不写日志；其他业务写入共用事务。最终引用约束失败时这批写入回滚；反馈中仍保留已经发现的跳过原因。不要把所有 SQL 异常都转成警告，否则可能提交不能解释的半批结果。

从目标表声明识别可写字段、引用与 provided 身份；不把任意 JSON 数字当成引用。若扩展数据在 information 中自定义了引用，可以在自己的工具里转换为明确操作，或扩充此包的解析器；支撑无需猜测。

format.relation_definitions 合并硬引用和逻辑引用，供收集与导入共用。逻辑引用不进入支撑的外键检查和撤销依赖；不要为复制重新生成 SQL 外键。复制策略在 Importer 执行节点时处理，因而导出文件可从 update 改为 add，事务内入口也使用目标表策略。具体判定见 [FORMAT](FORMAT.md#工具表)。

prepare_exchange 对逻辑引用只补充不清除，对复制策略保留任一方的 skip，防止旧文件丢失目标元信息。工具维护者通过 register_tables 可以显式调整这些元信息，不需要重建业务表。修改 Python 声明后，在工具初始化或显式升级阶段补登记；只读导出不会自动运行工具升级代码。

## 验证

在仓库根使用已安装本项目的 Python：

~~~sh
python -X utf8 -B -m unittest discover -s tests -p test_exchange.py -v
python -X utf8 -B -m unittest discover -s tests -p test_logical_references.py -v
python -X utf8 -B examples/exchange.py
python -X utf8 -B examples/logical_references.py
python -X utf8 -B -m unittest discover -s tests -v
~~~

涉及资源或导入路径时还应构建 wheel 并运行 tests/check_wheel.py。模板、README、FORMAT、DEVELOPMENT 都随 exchange 包安装；隔离验收会只留下这一工具包，确认它不依赖其他工具。

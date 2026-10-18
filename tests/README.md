# 测试导引

从仓库根、使用已安装本项目的解释器运行。所有业务测试使用临时或内存数据，不写实际项目库。

| 目录 | 覆盖范围 |
|---|---|
| architecture | 单包隔离、无工具的基础运行、导入命名空间和工具目录约定 |
| foundation | 配置、记录、编号、事务、日志、读取快照及工具表 |
| tools | 内部工具的编辑、查询、交换、历史、验证、KEY 与技能安装 |
| _support | 无测试方法的共享夹具、路径和独立进程场景 |

```sh
python -X utf8 -B -m unittest discover -s tests -t . -v
python -X utf8 -B -m unittest discover -s tests/foundation -t . -v
python -X utf8 -B -m unittest discover -s tests/tools -t . -v
python -X utf8 -B -m unittest tests.tools.test_exchange -v
```

本分支只运行基础支撑与非视图工具的测试，不需要 MCP SDK、浏览器或 Node。涉及符号链接权限的用例会明确记录跳过原因。

共享准备逻辑放进 _support 中普通 mixin 或函数；不要从另一份 test 模块导入测试类或借用其 setUp。回归按行为分类，不按某次审查或开发批次组织。合并重复用例时先核对触发条件、事务边界及验证结果，不能仅因函数名称相似就删除。

基础与工具的隔离测试保留，即使整套安装下的集成测试已经通过，也不能替代它们。

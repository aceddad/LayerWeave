# 测试导引

从仓库根、使用已安装本项目的解释器运行。所有业务测试使用临时或内存数据，不写实际项目库。

| 目录 | 覆盖范围 |
|---|---|
| architecture | 单包隔离、无工具的基础运行、导入命名空间和工具目录约定 |
| foundation | 配置、记录、编号、事务、日志、读取快照及工具表 |
| tools | 内部工具的编辑、查询、交换、历史、验证、KEY 与技能安装 |
| mcp | SDK/stdio、帮助发现、参数、分页、扩展安装和视图适配 |
| view | 视图后端、插件、语言、增量读取、媒体与真实浏览器交互 |
| packaging | wheel 普通安装与 sdist 重建验收脚本，不混入普通用例 |
| _support | 无测试方法的共享夹具、路径和独立进程场景 |
| fixtures | 有意保留的测试素材；不随运行时 wheel 安装 |

```sh
python -X utf8 -B -m unittest discover -s tests -t . -v
python -X utf8 -B -m unittest discover -s tests/foundation -t . -v
python -X utf8 -B -m unittest discover -s tests/tools -t . -v
python -X utf8 -B -m unittest discover -s tests/mcp -t . -v
python -X utf8 -B -m unittest tests.tools.test_exchange -v
```

MCP 测试需要 `.[mcp]`；浏览器测试需要 Chrome/Edge/Chromium，媒体测试按需使用 FFmpeg。不存在时相应用例会标明跳过，发布验收应核对跳过原因。实际浏览器测试不要并行启动多份，以免影响交互与性能测量。

共享准备逻辑放进 _support 中普通 mixin 或函数；不要从另一份 test 模块导入测试类或借用其 setUp。回归按行为分类，不按某次审查或开发批次组织。合并重复用例时先核对触发条件、事务边界及验证结果，不能仅因函数名称相似就删除。

发行物检查见[发布指南](../docs/releasing.md)。基础与工具的隔离测试保留，即使整套安装下的集成测试已经通过，也不能替代它们。

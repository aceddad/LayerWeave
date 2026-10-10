# 内部工具 · 开发工具

准备运行环境、扩充封装或维护软件时从这里开始。[返回内部工具](../README.md)。项目内容操作见[使用工具](../usage/README.md)。

## 选择开发任务

| 任务 | 阅读入口 |
|---|---|
| 用 LayerWeave 搭建自己的工具 | [AI 开发指导](../../../../../docs/build-with-layerweave/README.md)，嵌套时序与有序管理等分篇示例 |
| 新增 Python 层类或对象类 | [模型](../../../models/README.md)和[配置](../../../configs/README.md)，参考 [Title](../../../../../examples/title.py) |
| 新增内部工具 | 本页的开发流程、[公共 API](../../../support/API.md)、[命令声明](../shared/help/COMMANDS.md) |
| 安装下载的技能 ZIP | [技能安装](SKILLS.md)，选择层目录或场景补充区 |
| 管理本地 API KEY 与连接说明 | [KEY 管理](keys/README.md)，used 可记录任意使用方，公开查询不显示密钥 |
| 调整配置继承 | [配置读取与继承](../../../support/configuration/README.md) |
| 新增检查规则 | [检测执行与扩展](../usage/validation/RULES.md) |
| 调整诊断汇报 | [诊断配置](../../../support/DIAGNOSTICS.md) |
| 修改存储、编号、日志或恢复 | [存储入口](../../../support/storage/README.md) |
| 查完整封装定义 | [配置 help](../shared/help/CONFIG_HELP.md)，使用既有 --dev 模式 |

修改前阅读[开发指南](../../../../../docs/developer-conventions.md)，只展开当前任务需要的专题。文档与示例的维护方式见[文档约定](../../../../../docs/documentation.md)。

## 导入技能 ZIP

完成可编辑安装后运行：

```sh
python -m layerweave.tool.builtin.developer.skills.cli SKILL.zip --layer text --json
```

安装后返回 route，实际绑定由 AI 决定；场景区、多技能 ZIP 和重名处理见[技能安装说明](SKILLS.md)。

## 初始化与升级数据库

完成可编辑安装后运行：

```sh
python -X utf8 -B -m layerweave.tool.builtin.developer.database.cli output/ai-production.sqlite3
```

[database.py](database/cli.py) 是命令入口；表结构、升级和发号实现仍在 support。升级行为见[存储说明](../../../support/storage/SCHEMA.md)。

## 本地 KEY 与连接信息

```sh
python -m layerweave.tool.builtin.developer.keys.cli init --json
python -m layerweave.tool.builtin.developer.keys.cli connections --json
python -m layerweave.tool.builtin.developer.keys.cli export --output keys.example.json --json
```

上例用于本地 JSON 管理；KEY 已在环境变量中时，技能可直接用 --key-env，无需先 init。真实 JSON 配置默认保存到用户目录的 .layerweave/keys.json，只在本机维护。示例保留名称和 used，清空 KEY，并以中文提示替代连接字段的值。两种调用方式、录入密钥与程序读取见[KEY 管理说明](keys/README.md)。

## 开发内部工具

1. 按用途在 usage、developer 或 shared 下创建完整包；业务辅助放包内，避免对另一个可卸载包的私有依赖。
2. 从 layerweave.support.api 复用读取、保存、事务和位置计算；读后写在同一 transaction 或 run_operation 的 write 会话内组合；只返回业务结果，日志由支撑自动收集。
3. 用普通函数表达业务，明确输入、修改范围和返回。新增 CLI 复用 [support/cli.py](../../../support/cli.py)，在自身模块声明 COMMANDS。
4. 更新主要使用说明及可运行示例，执行与改动相符的检查。测试使用独立数据库。

load/save、读取快照和检查器等能力直接由开发 API 提供，不逐个包装成新命令。具体事务、声明与验证要求见开发指南。

命令行的 `--a-b` 对应 Python 的 `a_b`；argparse 默认完成这项映射，例如 --layer-ids 对应 layer_ids。COMMANDS 以 Python 参数名说明接口，CLI 示例使用命令行写法。

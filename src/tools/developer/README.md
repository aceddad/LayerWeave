# 内部工具 · 开发工具

准备运行环境、扩充封装或维护软件时从这里开始。[返回内部工具](../README.md)。项目内容操作见[使用工具](../usage/README.md)。

## 选择开发任务

| 任务 | 阅读入口 |
|---|---|
| 新增 Python 层类或对象类 | [模型](../../models/README.md)和[配置](../../../configs/README.md)，参考 [Title](../../examples/title.py) |
| 新增内部工具 | 本页的开发流程、[公共 API](../../runtime/API.md)、[命令声明](../shared/COMMANDS.md) |
| 安装下载的技能 ZIP | [技能安装](SKILLS.md)，选择层目录或场景补充区 |
| 调整配置继承 | [配置读取与继承](../../runtime/configuration/README.md) |
| 新增检查规则 | [检测执行与扩展](../../runtime/validation/RULES.md) |
| 调整诊断汇报 | [诊断配置](../../runtime/validation/DIAGNOSTICS.md) |
| 修改存储、编号、日志或恢复 | [存储入口](../../runtime/storage/README.md) |
| 查完整封装定义 | [配置 help](../shared/CONFIG_HELP.md)，使用既有 --dev 模式 |

修改前阅读[开发指南](../../../docs/developer-conventions.md)，只展开当前任务需要的专题。文档与示例的维护方式见[文档约定](../../../docs/documentation.md)。

## 导入技能 ZIP

从项目 src 运行：

```sh
python -m tools.developer.skills SKILL.zip --layer text --json
```

安装后返回 route，实际绑定由 AI 决定；场景区、多技能 ZIP 和重名处理见[技能安装说明](SKILLS.md)。

## 初始化与升级数据库

从项目 src 运行：

```sh
python -X utf8 -B -m tools.developer.database ../output/ai-production.sqlite3
```

[database.py](database.py) 是命令入口；表结构、升级和发号实现仍在 runtime。升级行为见[存储说明](../../runtime/storage/SCHEMA.md)。

## 开发内部工具

1. 按用途放入 usage/common、usage 对应内容类型目录、developer 或 shared。
2. 从 runtime.api 复用读取、保存、事务和位置计算；读后计算再写入的动作使用 dispatch 请求工厂，复杂批次复用 run_operation。
3. 用普通函数表达业务，明确输入、修改范围和返回。新增 CLI 复用 [shared/_cli.py](../shared/_cli.py)，在自身模块声明 COMMANDS。
4. 更新主要使用说明及可运行示例，执行与改动相符的检查。测试使用独立数据库。

load/save、读取快照和检查器等能力直接由开发 API 提供，不逐个包装成新命令。具体事务、声明与验证要求见开发指南。

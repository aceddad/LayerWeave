# 核心执行模块

runtime 提供配置读取、数据存储、事务、日志、检测与公共 API。内部工具调用这些能力，模型类保持简单。[返回项目首页](../../README.md)。

## 按任务查阅

| 任务 | 主要说明 |
|---|---|
| 从 Python 读写记录或装载模型 | [公共 API](API.md) |
| 发送 JSON CRUD 请求、处理操作与检测反馈 | [请求协议](PROTOCOL.md) |
| 理解配置继承、合并与类绑定 | [配置模块](configuration/README.md) |
| 理解数据表、编号、事务和日志 | [存储模块](storage/README.md) |
| 修改检查时点或新增规则 | [检测模块](validation/README.md) |

## 代码职责

| 模块 | 职责 |
|---|---|
| [api.py](api.py) | 内部工具的统一导入入口，按需加载较重能力 |
| [dispatch.py](dispatch.py) | 单条、批量或请求工厂的 CRUD 分流 |
| [operation.py](operation.py) | 一次事务、操作编号与提交后检测 |
| [feedback.py](feedback.py) | 操作状态、错误线索和逐条诊断格式 |
| [positions.py](positions.py) | 十进制位置计算与轴精度处理 |
| [values.py](values.py) | JSON 值的类型与内容比较 |
| configuration/、storage/、validation/ | 对应模块的具体实现 |

CLI 位于 [tools/usage/crud.py](../tools/usage/crud.py)；数据库准备入口位于 [tools/developer/database.py](../tools/developer/database.py)。核心函数的 Python 导入位置保持不变。

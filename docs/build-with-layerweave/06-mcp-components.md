# 用法六：通过统一 MCP 入口按需发现与调用组件

当 AI 需要使用很多自定义组件时，可以让它先通过一个固定的 MCP 查询入口读目录，再展开当前需要的组件。LayerWeave 保存分类、用途和调用声明，适配工具解释这些声明并连接实际实现。[返回开发指导](README.md)。

本篇描述可基于现有内核实现的接入方式，不表示已经内置了由项目数据驱动的 MCP 动态加载器。

## 先看目录，再读需要的说明

```text
AI → 固定 MCP 查询入口 → 层树与能力分类
                         → 目标组件的用途、参数和入口
                         → 交给约定的调用方式执行

组件目录（project 或一个 root）
├─ 文本处理（层）
│  ├─ 文本检索（对象）
│  └─ 摘要生成（对象）
└─ 资料管理（层）
   └─ 重建索引（对象）
```

先读层树可以知道有哪些分类及直属对象数量；对象中的具体入口和参数需要进一步展开。目录很大时按层、名称或明确的对象身份读取，不必把所有组件的完整说明一次塞进 AI 上下文。

下面是一个对象 information 的示意。字段由适配工具约定，示例模块并不存在，也不会因保存这段数据而自动加载：

```json
{
  "text": "在指定范围内检索文本，返回命中对象及摘要。",
  "component": "text.search",
  "when": "需要从已有内容定位相关片段时",
  "entrypoint": "example_plugin.search:run",
  "input_schema": {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"]
  }
}
```

条目可以使用[有序列表](02-ordered-metadata.md)的序号位置；分类和存储先复用现有层/对象。需要稳定的专用字段约定时，再按原规则增加对应 Python 类与 TOML，不必修改内核。

## 用现有读取接口支撑发现

前提：connection 已打开，directory_project_id 和 capabilities_layer_id 来自实际存在的目录项目和层。

```python
from layerweave.support.api import query_objects
from layerweave.tool.builtin.usage.query.project_overview import project_overview

overview = project_overview(connection, directory_project_id)
candidates = query_objects(
    connection, directory_project_id,
    layer_id=capabilities_layer_id, name="文本检索",
)
```

project_overview 返回层树摘要；query_objects 返回匹配的对象记录。name 是字面子串筛选，不保证只命中一个对象；后续用实际返回的 project_id/id 定位。适配器可将结果整理成简短目录和单项详情，具体读取参数继续见[基础 API](../../src/layerweave/support/API.md#通用只读查询)。

这些调用只读取声明。代码导入、远程连接、参数转换和执行由适配工具完成；需要跟随目录变化更新自己的缓存时，可复用[持续读取变化](05-incremental-reading.md)。

## 固定入口与实际调用

查询入口解决“有什么、何时用、如何访问”。执行可交给组件已有的调用方式、统一调度入口，或由同一个 MCP 入口明确区分查询与调用。只承担查询的入口保持只读；若还承担写入或执行，就按实际行为描述操作。

这样，新增组件接入目录和调度方式后，可以被 AI 发现和使用，不要求每个组件都单独成为顶层 MCP 工具。实际组件代码仍由外部包提供，登记一条声明不等于创建了实现。

如果需要让客户端原生工具列表也发生变化，则需由 MCP 适配器维护工具列表，并按所用协议版本处理变更通知；返回一段组件说明不会自动完成注册。参见 [MCP 工具发现与列表变更](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)。

## 复用已有 help 和声明来源

已有组件的用途、参数和入口若已写在 COMMANDS、TOML 或其他正式声明里，可在目录中保存来源引用，或由工具汇集这些信息。若选择对象本身作为正式声明，就让执行端读取同一份数据，避免手工维护两套容易分歧的说明。

当前 LayerWeave MCP 服务位于 visualization，启动时根据命令声明建立绑定目录；向数据库添加组件对象，不会使该服务自动新增工具或热重载。接入其现有机制，继续使用[命令声明与 help](../../src/layerweave/tool/builtin/shared/help/COMMANDS.md)和[完整版本的 MCP 说明](https://github.com/aceddad/LayerWeave/blob/visualization/src/layerweave/tool/builtin/shared/mcp/README.md)。main 的开发者也可以复用基础 API 编写自己的适配器。

这个用法关注 AI 如何按需取得并使用能力。钩子和协议条目的管理见[声明服务](07-declaration-services.md)；目录需要独立管理范围时，可结合 [project 分区技巧](tip-project-scopes.md)。

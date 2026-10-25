# 技巧：用 project 分区和外置关系组织定向读取

project 可以作为一个独立的管理范围，装业务内容、组件声明或公共约定。同一个数据库统一保存这些数据，外部工具通过关系表决定各个组件读取哪些 project、层或对象。[返回开发指导](README.md)。

这是一种可以与多种用法组合的技巧，不是新增的隔离模块或访问接口。

## 统一存储，分别选择读取范围

```text
统一数据库
  project A：业务内容
  project B：组件声明
  project C：公共协议

外置关系表
  组件甲 → A 的指定层
  组件乙 → A 的另一组对象
  组件甲、乙 → C 的同一份协议
```

多个消费者可以指向同一份记录，无需为每个消费者复制数据。这里的“分布读取”指不同消费者按各自范围取数据，不要求它们运行在不同机器。

project 提供项目内编号与查询范围，层和对象仍保存在统一的 layers/objects 表中；它不是独立数据库、进程或权限屏障。使用者只拿到哪些数据，由上层工具如何查询和提供结果决定。

按业务归属或生命周期选择 project；同一范围内的分类通常用 root 或子层即可，不要求每个组件、分类都新建 project。层的 father 仍只组织同一项目内的父子关系。

## 由外部关系表达谁读取什么

外置关系表可保存消费者标识、目标项目、目标层/对象以及工具自己的用途说明。它可以由工具独立管理；需要接入统一事务、编号和日志时，按[工具表方式](03-managed-tables.md)登记即可。“外置”指由工具定义业务语义，不要求存到另一个数据库。

例如 read_route 是外部工具已登记的非 scoped 工具表，含 consumer（TEXT）、target_project_id 和 target_layer_id（均为非空 INTEGER），目标为已存在的层。本例只演示按层读取，其他范围由工具自行约定。connection 已打开，consumer 为当前消费者标识：

```python
from layerweave.support.api import read_record, query_objects, read_snapshot

with read_snapshot(connection):
    routes = read_record(connection, "read_route", filters={"consumer": consumer})
    selected = []
    for route in routes:
        project_id = route["target_project_id"]
        layer_id = route["target_layer_id"]
        selected.append({
            "project_id": project_id,
            "layer_id": layer_id,
            "objects": query_objects(connection, project_id, layer_id=layer_id),
        })
```

关系与目标内容在同一次读取快照中获取；selected 交给相应组件。query_objects 的 layer_id 只选直属对象，需要子树时使用现有 read_project_details 的层范围。接口参数见[基础 API](../../src/layerweave/support/API.md)。

读取和关系中都保留 project_id；不同项目可以出现相同的局部编号，不能仅用 id 指认对象。需要区分层和对象时同时保存 kind。组件标识以及“读取整个项目、指定层或指定对象”的表达方式属于外部工具约定。

原有 bind 适合连接同库的层/对象，也能跨 project；消费者到 project、读取规则等业务关系可以使用工具自己的表，不必强行套进 bind。硬引用或逻辑引用的取舍继续沿用工具表声明规则，关系表不会因为记录了一条路由就自动限制其他数据库调用。

## 与远程执行的关系

统一目录可以登记远程组件的地址，再由各组件分别读取或处理所需内容。执行节点分布在不同机器，不影响集中维护目录这一用法。

若数据本身位于多个独立数据库，外部关系还需记录库或服务的位置，仅凭 project_id/id 无法定位跨库目标；同步、冲突处理和远程调用由上层系统负责。增加目录层级可以表达节点和位置，不自动实现分布式数据库。

这个技巧可以用于[统一 MCP 入口](06-mcp-components.md)的组件目录，也可以用于[声明服务](07-declaration-services.md)和普通业务数据。project 划分管理范围，关系表达定向访问，消费工具决定如何使用结果。

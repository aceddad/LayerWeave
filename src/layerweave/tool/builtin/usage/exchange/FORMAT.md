# 交换格式 v1

使用普通 JSON；第一版不实现 JSONL。文件既可承载实际导出数据，也可作为预先写好的操作模板。操作和引用字段在本页维护，调用示例见 [README](README.md)。

## 文档与节点

~~~json
{
  "format_version": 1,
  "name": "可选的文件名称",
  "when": "可选的用途说明",
  "project_id": 1,
  "items": [
    {
      "kind": "layer",
      "id": 4,
      "children": [
        {
          "kind": "object",
          "op": "update",
          "id": 8,
          "data": {"information": {"text": "新正文"}}
        }
      ]
    }
  ]
}
~~~

项目和编号为示意。没有 op 的节点只提供上下文，data 即使存在也不写入。items 是层次入口列表，records 是标准关联和工具记录的平面列表；两者共用节点语义。只有 layer 可装载 children。顶层入口不必是真正的 root。

| 文档字段 | 含义 |
|---|---|
| format_version | 必须为整数 1 |
| project_id | 来源项目，同时是未指定目标时的默认已有项目 |
| project | 可选的项目操作，含 op、data 和可选 base；data 仅 name/tips 等可写项目字段 |
| items、records | 可省略的节点列表 |
| tables | 工具 kind 到表声明的字典，独立结构准备使用 |
| preserve_positions | 导出文件为 true，复制和对象更新保留原始数值；手写文件默认 false，沿用普通落点 |
| source_numbering | 来源发号词条说明，不自动替换目标库注册 |
| scope、counts、external_references、omitted_tool_records | 导出的范围、计数和遗漏/外部引用说明，不是操作指令 |

| 节点字段 | 含义 |
|---|---|
| kind | layer、object、bind 或已登记工具 kind；项目操作放在 project 区域，change 不可写 |
| op | add/update/delete；省略或 null 为上下文 |
| id | update/delete/上下文需要正整数；add 的旧 ID 只作为来源身份 |
| key | 可选、文档内唯一的字符串，引用尚未发号的新节点 |
| data | 实际可写字段，不混入 children、op 等传输字段 |
| children | 本层下的后续节点 |
| parent_id | 可选的声明归属，null 表示声明为根层；嵌套父节点或调用方附着层优先 |
| refs | 标准或已声明的引用，详见下节 |
| base | 可选的原始状态摘要，由导出器产生，更新或删除前核对 |

一个来源身份只声明一次，不在多个分支重复列同一节点；需引用时用 refs。自动发号 add 不用提供 id；若保留了正整数旧 ID，它参与来源映射，不能重复而造成引用歧义。非正整数等占位 id 不作为自动表来源身份。

## 项目、归属和执行

明确传 project_id 时，导入到该已有项目；否则默认使用文档的 project_id。文档没有来源项目，或完整导出带 project.op=add 且未指定目标时，新建项目；也可明确 new_project=True。new_project 不会把其他节点的 update 偷换成 add，因此复制应先导出 op=add。

新建项目使用 project.data；缺席时用文档 name。导入到已有项目时，project.op=add 仅提供项目上下文，不另外新建或改名；update/delete 则执行明确的项目操作。完整项目导出提供 project.op，局部导出省略，以免处理局部内容时误改或删除项目。

按父节点到子节点解析。新增下级默认取得父层的新编号；已有节点先核对 ID 及声明的直属归属。归属不符跳过该节点、其下级以及依赖它的操作，最后集中 warn；其他独立分支继续。没有父层上下文也没有 parent_id 时，按完整身份直接定位。节点位置本身不会搬移已有记录；data 中明确提供 father/layer 才是修改归属。

目标不存在、未知 op/kind、非法字段或实际存储失败属于 error，整批实际业务写入回滚。删除使用延迟引用检查，支持先父后子，但不会替文件补齐未声明的子项删除；最终引用仍不成立就回滚。新增引用可等后面的目标创建后再处理；普通父子节点保持先父后子。

更新只覆盖提交字段，information/axis 等 JSON 字段整体替换。未提供的节点保留，未提供的字段保留，相同数据不制造新日志。提交后的内容检查仍独立运行，检查 error 不回滚已提交业务。

## 文档内引用与外部引用

新增层、对象和一条引用：

~~~json
{
  "format_version": 1,
  "items": [
    {"kind": "layer", "op": "add", "key": "story", "data": {"config_ref": "layers/text.toml"},
     "children": [
       {"kind": "object", "op": "add", "key": "line",
        "data": {"config_ref": "objects/text.toml", "information": {"text": "正文"}}}
     ]}
  ],
  "records": [
    {"kind": "bind", "op": "add",
     "refs": {"source": {"key": "line"}, "target": {"key": "story"}}}
  ]
}
~~~

引用有三种表达：

- {"key":"line"}：指向本文件节点。
- {"kind":"object","project_id":1,"id":8}：来源完整身份，优先查本文件映射。
- 在完整身份上加 external=true：明确直接使用该目标库身份，不做来源映射。

层的引用名为 father，对象为 layer，bind 为 source/target；工具表使用 references 中最后一列的名称，例如 object_id，或使用 id 表示“本表身份引用某个层”。转换仅发生在这些声明位置，不扫描 information 内部数字。

导出文件的普通数字引用会自动按来源身份映射，无需手工改写为 refs。add 若引用文件外目标，默认跳过依赖项并报告；external_refs=preserve 明确保留原完整引用。也可传 reference_map：

~~~json
[
  {
    "source": {"kind": "layer", "project_id": 1, "id": 4},
    "target": {"kind": "layer", "project_id": 9, "id": 12}
  }
]
~~~

复制子树时，parent_layer_id 可指定顶层节点的新附着层。父子层和对象归属不能跨项目；跨项目联系通过 bind 表达。入向关联属于范围外来源，不随被引用子树复制；局部导出包含选中实体发出的关联。完整项目导出保留来源项目为该项目的所有 bind，包括来源实体已经失效的关联；复制时未映射的失效引用会明确报告。

若新记录相互依赖而无法确定任何一方的新身份，节点以 unresolved_dependency 跳过，不猜测旧 ID。可分为先创建后更新；provided 身份明确时也可由调用方提供显式映射。引用被跳过的新节点时，不回退到目标库同号的旧记录。

## 工具表

tables 沿用 register_tables 的声明：table、fields、scoped、id_source、references。导入先独立准备这些表；已有列、身份及引用不能被文件改写，目标表后来增加的其他列保留。业务失败或撤销不会删除已准备的空表，schema 字段明确报告这个阶段。

scoped 工具表在当前项目内处理；独立表按本表 ID 定位。完整项目导出包含本项目全部 scoped 工具记录，以及明确引用该项目的全局工具记录；局部导出根据声明引用收集相关工具记录，并补足这些记录明确引用的工具数据。用于 update/delete 的时间范围中，上下文层不作为收集其关联及工具状态的起点。删除导出中，仅为补足引用而带入的共享工具资料没有 op，不随从属记录删除；显式 include_global 选中的记录仍使用所选 op。未被选中的全局记录用 omitted_tool_records 计数；include_global=True 才额外带入所有全局工具记录。

auto 表创建时由目标发号；provided 表若 id 声明为其他记录的引用，跟随引用映射，否则使用节点 id 或明确的 data.id。冲突会报错，不自动覆盖或随机重编号。需要特殊 ID/簇规则时，先在目标登记相应规则和词条；source_numbering 是来源说明，不自动加载代码或更换已有簇。

## 原状态摘要与反馈

include_baseline=True 导出 base；导入只在 base 存在且 check_baseline=True 时检查。比较导出时与数据库当前状态，不比较修改后的 data。摘要针对该行可写字段，排除发号计数，不包含其子项；冲突跳过并报告 source_changed。project 冲突会跳过整份项目上下文。模板不需要 base，add 忽略它；明确覆盖用 check_baseline=False。

成功返回 data.status、project_id、project_action、counts、items、issues、id_map。counts 区分 created/updated/deleted/unchanged/selected/skipped，不把项目操作混入节点计数。每项有原 JSON pointer 与状态；成功的节点带实际 target。id_map 给出新建项目和记录的来源到目标映射。

ok/applied/operation/checks 保留原含义。存在跳过时 data.status=partial；真实写入可以成功提交。失败时不返回 data/id_map，已有跳过警告放在 import_issues；结构准备信息仍在 schema。数据日志和撤销只覆盖真正发生的业务修改。

本格式交换数据库业务数据及引用，不打包媒体文件、TOML、Python 类、技能或 KEY，也不把源 changes 日志或 project.max_id 当作可写数据。文件路径保持原值，搬到其他环境后由调用方适配。

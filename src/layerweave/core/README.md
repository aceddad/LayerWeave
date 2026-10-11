# 抽象核心

核心定义层、对象与封装继承的语义，不读取数据库、TOML 或工具。Python 基础类及派生类保持在 [models](../models/README.md)，可从 layerweave.core 导入 Layer/Object，也可沿原有 models/layers 和 models/objects 分区开发。

identity_key 与 reference 表达身份和普通引用：层/对象保留项目编号，project/bind/change 使用独立编号。扩展记录保留调用方提供的项目范围，独立编号记录传入 None。它们只组织数据，不读取工具表声明或查询端点；具体表的范围由支撑解析。

encapsulation.merge_definition 合并纯字典约定：父约定不放宽，optional 和 open 可以由 true 收紧为 false；具体继承行为见[合并约定](../support/configuration/README.md#合并约定)。layerweave.support.configuration.Loader 使用这份语义读取 TOML，没有另一套合并实现。

类导入按需进行，仅使用合并函数不会预加载模型。身份范围、关系和支撑保证见[架构](../../../docs/architecture.md)。

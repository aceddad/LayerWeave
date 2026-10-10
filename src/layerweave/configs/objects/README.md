# 对象配置

[返回配置入口](../README.md)。

基础约定、六种封装及 Title 派生示例放在这里，可按需继续分子目录。工具包登记的对象类型也放在这里，class 指向工具包，用 `requires` 写明依赖，例如视图工具的批注对象 note.toml（继承 text.toml）。对应 Python 类在 src/layerweave/models/objects/，读取与继承见 [配置说明](../../support/configuration/README.md)。

每份封装明确声明自己的 type 与 class，一个类只绑定一份配置。title.toml 继承 text.toml，绑定继承 Text 的独立 Title 类；沿用文字约定，不添加限制，也不需要新建标题层。

对象 layer 必须指向同项目实际存在的层。base.toml 说明字段与固定约定，默认 duration=any、visibility=true。optional=true 允许字段缺省并随字段继承；已填写时仍检查类型。未声明 optional 按 false 检查缺失。模型/动作的 source/data 均声明 optional=true。产生诊断后，等级在 ../logging/diagnostics.toml 管理，路径覆盖不继承，未配置默认 warn。所有内置类型 open=true，允许附加内容键。

text 使用 information.text；image/audio/movie/model/active 使用 information.source 引用资源；model/active 另可使用 information.data 字典。引用原样保存，资源解释与工具接入后续实现。

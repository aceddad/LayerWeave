# 对象配置

基础约定与六种封装放在这里，可按需继续分子目录。对应 Python 类在 src/models/objects/，读取与继承见 [配置说明](../../src/runtime/configuration/README.md)。

对象 layer 必须指向同项目实际存在的层。base.toml 说明字段与固定约定，默认 duration=any、visibility=true。配置声明字段类型，但目前没有 text/source/data 的必填要求；所有内置类型 open=true。

text 使用 information.text；image/audio/movie/model/active 使用 information.source 引用资源；model/active 另可使用 information.data 字典。引用原样保存，资源解释与工具接入后续实现。

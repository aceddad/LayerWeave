# 层配置

基础约定与六种封装放在这里，可按需继续分子目录。对应 Python 类在 src/models/layers/，读取与继承见 [配置说明](../../src/runtime/configuration/README.md)。

base.toml 说明字段、返回方法、固定规则、默认取值和可调选项。默认 overlap=true、visibility=true；具体封装的显式 constraint/display 成为固定父约定。axis_only_on_root 是明确可调选项，默认 true，根层不必填写轴。

层的 objects 按对象配置 type 唯一定位，接受该类型及其派生配置。六种内置层分别为 text、image、audio、movie、model、active。

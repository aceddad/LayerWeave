# 层配置

[返回配置入口](../README.md)。

基础约定与六种封装放在这里，可按需继续分子目录。对应 Python 类在 src/models/layers/，读取与继承见 [配置说明](../../src/runtime/configuration/README.md)。

每份封装明确声明自己的 type 与 class，一个类只绑定一份配置。type 字符串只在 TOML 定义，由保存接口写入层记录，Python 层类不重复声明。

base.toml 说明字段、返回方法、固定规则、默认取值和可调选项。默认 overlap=true、visibility=true；具体封装的显式 constraint/display 成为固定父约定。axis_only_on_root 是明确可调选项，默认 true，根层不必填写轴。

层的 objects 按对象配置 type 唯一定位，接受该类型及其派生配置。六种内置层分别为 text、image、audio、movie、model、active。

axis.precision 是位置写入、工具和检查共用的正数步长。子层未声明轴时沿父链取得轴，默认来自根；显式自有轴覆盖上级轴。没有轴或当前轴没有 precision 时默认 1e-6。所有对象位置写入按精度落点，比较使用同一整数刻度；不换算单位或 fps。读取保持原始存储数值，不批量重写旧数据。

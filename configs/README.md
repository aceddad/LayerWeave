# 配置入口

这里保存 LayerWeave 的 TOML 声明。[返回项目首页](../README.md)。

| 目录 | 内容 | 何时阅读 |
|---|---|---|
| [layers/](layers/README.md) | 层的基础约定和具体封装 | 定义层及其接受的对象类型 |
| [objects/](objects/README.md) | 对象的基础约定和具体封装 | 定义对象内容字段或派生封装 |
| [logging/](logging/README.md) | 检查结果的汇报等级 | 调整某种问题的显示等级 |

一份层/对象封装 TOML 对应一个 [Python 类](../src/models/README.md)。base.toml 是基础约定，具体封装通过 extends 延续约定；继承合并、收紧与类绑定规则见[配置读取器说明](../src/runtime/configuration/README.md)。

只想知道可以使用什么层或对象时，调用[配置 help](../src/tools/shared/CONFIG_HELP.md)即可。开发封装时再阅读对应 TOML 和类文件。

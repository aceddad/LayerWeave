# 层原型的外置工具

这里存放供层原型 `tools` 引用的技能包。技能内容可以独立编写和使用，AI 再按实际需要将其引用填入层 TOML。[返回项目介绍](../README.md)。

软件自身的读写、编辑与撤销能力仍在 [src/tools](../src/tools/README.md)。本目录中的技能可以使用自己的脚本、外部软件或服务。

## 存放方式

```text
tool/
  skills/
    layers/                         按层原型归类的常规技能
      text/
        text-normalize/
          SKILL.md                  用途、输入输出和使用方法
          scripts/normalize_text.py 独立脚本
    scenarios/                      特殊场景的补充技能
      README.md                     当前只保留范围说明
```

- layers 下按原型 type 命名，例如 text、audio、image；不按实例的“主线”“歌词”等 name 建目录。其他层有实际技能时再创建对应目录。
- 每个技能独立成包，以 SKILL.md 为入口；脚本、参考资料和资源按需要放在包内。
- 场景补充放在 scenarios 下，可同时被多个层引用。同一份技能不因绑定多个层而复制。
- 目录用于组织材料，不决定 tier，也不自动绑定、加载或执行技能。包可以放在这里，也可以引用外部已有位置。

## 绑定示例

下载的技能 ZIP 可以先通过[安装工具](../src/tools/developer/SKILLS.md)放到这里。从项目 src 运行：

```sh
python -m tools.developer.skills SKILL.zip --layer text --json
python -m tools.developer.skills SKILL.zip --scenario --json
```

工具返回实际 route，保留包内文件和已有同名目录；技能内容由 AI 按任务阅读，安装不会自动绑定。

[text-normalize](skills/layers/text/text-normalize/SKILL.md) 是一个实际可运行的纯文本整理示例。AI 阅读后，可以在选定层的 `[layer]` 内将下面的项加入 tools 数组，保留原有引用：

```toml
tools = [
  { route = "tool/skills/layers/text/text-normalize/SKILL.md", tier = "可用", when = "需要规范纯文本换行并清理行尾空格时；代码和 Markdown 不适用" },
]
```

上例 route 相对于项目根目录；tier 和 when 由绑定方按实际用途填写。实际六类层配置仍是空列表，示例未自动绑定。配置只保存并展示这些说明，字段含义见[层配置](../configs/layers/README.md#外置技能-tools)。

## 试运行示例

从项目根目录用 PowerShell 执行：

```powershell
'{"text":"第一句  \r\n第二句\t"}' | python -X utf8 -B tool/skills/layers/text/text-normalize/scripts/normalize_text.py
```

输出：

```json
{"text": "第一句\n第二句", "changed": true}
```

该脚本只接收和返回文本，不读取 LayerWeave 配置或数据库。是否采用返回内容、是否写回对象，由调用它的 AI 根据任务决定。

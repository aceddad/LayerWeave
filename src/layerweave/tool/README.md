# 工具区：内置工具与外置技能

builtin 存放 LayerWeave 自身的内部工具，skills 存放供层原型 `tools` 引用的技能包。技能内容可以独立编写和使用，AI 再按实际需要将其引用填入层 TOML。[返回项目介绍](../../../README.md)。

软件自身的读写、编辑与撤销能力在 [builtin](builtin/README.md)，按完整包增减。本目录中的技能可以使用自己的脚本、外部软件或服务。

本页的项目介绍、开发工具等链接面向源码仓库。普通安装后，技能文件和 KEY 调用说明随包提供；按下面的命令定位即可阅读。完整开发手册与示例脚本在源码仓库中。

## 选择与定位技能

先查询目标层的支持说明，按 tools 中的 when 选择技能，再打开 route 指向的 SKILL.md：

```sh
python -m layerweave.tool.builtin.shared.help.config_help layers text image audio movie active
```

SKILL.md 说明该技能需要的输入、依赖、输出及局限。脚本、参考资料、模板随技能放置；Python/Node/ffmpeg 等依赖由调用环境按需准备，安装 LayerWeave 或解压技能 ZIP 不会自动安装它们。技能中的 Remotion Studio 是外部制作工具，不是 LayerWeave 的视图；LayerWeave 自己的只读视图见 [builtin/view](builtin/view/README.md)。

| 使用方式 | 如何找到文件 |
|---|---|
| 源码仓库 | 自带 route 以 src/layerweave/tool/skills/ 开头，相对于仓库根目录 |
| 普通安装 | 用 SKILLS_ROOT 定位自带材料；将 route 上述前缀之后的 layers/... 或 scenarios/... 接在它下面 |
| ZIP 安装 | 使用安装器返回的 route；相对路径按安装命令的工作目录解释 |

例如，定位安装后的生视频技能入口：

```sh
python -c "from layerweave.support.paths import SKILLS_ROOT; print(SKILLS_ROOT / 'layers/movie/video-generate/SKILL.md')"
```

这是 AI 的文件定位步骤；层配置读取器仍只展示 route，不自动解析或执行它。配置引用 config_ref 继续相对于 configs 根目录，与技能 route 分开。

## 存放方式

```text
src/layerweave/tool/
  builtin/                          软件自身的内部工具
    usage/                          records/query/editing/history/undo/validation/text
    developer/                      database/skills 等开发工具包
    shared/help/                    命令与封装帮助
    view/                           视图网页与视图工具（截图、取帧、排版、批注、正在看哪儿），自带批注层
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

这里保存随软件分发的技能材料。下载的 ZIP 通过[安装工具](builtin/developer/SKILLS.md)默认放入当前工作目录的 tool/skills；需要加入本仓库自带区时，从项目根额外指定 --skills-root src/layerweave/tool/skills。安装后运行：

```sh
python -m layerweave.tool.builtin.developer.skills.cli SKILL.zip --layer text --json
python -m layerweave.tool.builtin.developer.skills.cli SKILL.zip --scenario --json
```

工具返回实际 route，保留包内文件和已有同名目录；技能内容由 AI 按任务阅读，安装不会自动绑定。

[text-normalize](skills/layers/text/text-normalize/SKILL.md) 是一个实际可运行的纯文本整理示例。AI 阅读后，可以在选定层的 `[layer]` 内将下面的项加入 tools 数组，保留原有引用：

```toml
tools = [
  { route = "src/layerweave/tool/skills/layers/text/text-normalize/SKILL.md", tier = "可用", when = "需要规范纯文本换行并清理行尾空格时；代码和 Markdown 不适用" },
]
```

上例 route 用于源码仓库，相对于仓库根目录。普通安装后可通过 layerweave.support.paths.SKILLS_ROOT 找到自带技能的实际位置；ZIP 安装直接返回相对于当前工作目录或绝对的 route。tier 和 when 由绑定方按实际用途填写。文字、图片、音频、视频、动作层已声明相应技能；基础层与模型层仍留空，text-normalize 保留为未默认绑定的示例。实际清单以配置 help 为准。配置只保存并展示这些说明，字段含义见[层配置](../configs/layers/README.md#外置技能-tools)。

## 调用与输出目录

输出目录由调用的 AI 根据项目自行选择和管理。运行技能前安排好输入、输出与临时材料的位置，显式传入输出路径或 --out 等输出参数；建议用绝对路径。没有输出参数的脚本按其说明选择工作目录，并由 AI 收集结果。技能材料目录用于保存代码与参考资料，不作为项目成果的默认存放位置。

需要 KEY 时，先确认它已在环境变量中，还是保存在本地 JSON，再按[KEY 管理的子进程调用](builtin/developer/keys/README.md#把连接交给技能子进程)提供连接信息。技能不依赖 KEY 管理包，也不新增自动绑定或执行器。

技能产出的文件和报告先交给调用 AI 判断；采用后，再通过[使用工具](builtin/usage/README.md)或[读写 API](../support/API.md)保存资源引用、内容和位置。技能本身不自动创建项目对象或改动数据库。

## 试运行示例

从项目根目录用 PowerShell 执行：

```powershell
'{"text":"第一句  \r\n第二句\t"}' | python -X utf8 -B src/layerweave/tool/skills/layers/text/text-normalize/scripts/normalize_text.py
```

输出：

```json
{"text": "第一句\n第二句", "changed": true}
```

该脚本只接收和返回文本，不读取 LayerWeave 配置或数据库。是否采用返回内容、是否写回对象，由调用它的 AI 根据任务决定。

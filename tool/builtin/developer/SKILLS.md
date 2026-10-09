# 从 ZIP 安装外置技能

把已下载的技能包放入项目的 tool/skills，并返回可用于层配置的 route。[返回开发工具](README.md)。

## 快速使用

完成可编辑安装后运行，将 SKILL.zip 替换为实际文件路径：

```sh
python -m tool.builtin.developer.skills.cli SKILL.zip --layer text --json
python -m tool.builtin.developer.skills.cli SKILL.zip --scenario --json
```

- --layer text 安装到 tool/skills/layers/text/技能目录。
- --scenario 安装到 tool/skills/scenarios/技能目录。
- 两者必须选一个；层类型只用于确定目录，不要求先创建层实例或读取层 TOML。

安装后将返回的 route 按需要加入层的 tools，tier 和 when 由 AI 填写。安装器不自动绑定。

## 压缩包与目录选择

支持根目录直接含 SKILL.md，或被一层、多层文件夹包住的技能目录。文件扩展名不影响识别，实际内容为 ZIP 的 .skill 文件也可使用。

默认名称取包含 SKILL.md 的目录名；根目录平铺的包使用 ZIP 文件名去掉扩展名。需要其他安装名称时：

```sh
python -m tool.builtin.developer.skills.cli SKILL.zip --layer audio --name audio-helper --json
```

--name 只改变安装目录名，SKILL.md 的原文和内部名称保持不变。

若有多个独立技能，工具返回 error.candidates 中的包内目录，不自动选择：

```sh
python -m tool.builtin.developer.skills.cli BUNDLE.zip --layer audio --source-dir bundle/audio-skill --json
```

只复制选中技能目录内的内容，外层 README 和其他技能不会一起安装。技能目录内的 scripts、references、assets 及其他文件原样保留。若最外层已有 SKILL.md，其下引用资料里的其他 SKILL.md 默认作为包内内容保留。

标准技能目录结构可参考 [Agent Skills 规范](https://agentskills.io/specification)。本工具仅定位 SKILL.md，不检查其 frontmatter、用途或内容，也不执行脚本或安装依赖。

## 结果与失败处理

默认输出安装位置、文件数量和 route；--json 返回：

```json
{
  "ok": true,
  "name": "audio-helper",
  "path": "目标技能目录的绝对路径",
  "route": "tool/skills/layers/audio/audio-helper/SKILL.md",
  "source_dir": "包内技能目录",
  "files": 3
}
```

上面的目录和数量为示意，以实际返回为准。项目内的 route 相对项目根目录；若用 --skills-root 指定项目外的存放根目录，返回绝对文件路径。

- 同名目标不合并、不覆盖，可用 --name 安装到另一个目录。
- ZIP 中的绝对路径、越界路径、链接及重复文件路径会报错；只允许写入指定存放根目录内。
- 解压或校验 ZIP 数据失败时，清理本次新建的技能目录；已有技能保持原样。
- CLI 成功退出码为 0，失败为 1；--json 失败结果包含 ok=false 和 error，必要时带候选目录。
- 文件安装不写业务数据库，不生成 changes 日志，也不创建数据库操作编号。

## Python 入口

```python
from tool.builtin.developer.skills.cli import install_skill

result = install_skill("download.zip", layer="text")
print(result["route"])
```

可选参数为 scenario、name、source_dir、skills_root；layer 与 scenario 二选一。Python 调用失败时抛出带原因的异常。内部实现与命令声明位于 [skills.py](skills/cli.py)。

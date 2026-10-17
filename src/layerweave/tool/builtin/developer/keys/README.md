# 本地 KEY 管理

管理具名 KEY 条目及其环境变量名、服务地址、默认模型和 used 使用指引。技能、脚本、内部工具或其他程序都可读取同一条目。它是独立工具包，不需要业务数据库，不参与 changes 日志，也不执行使用方或修改环境变量。

先按实际存放方式选择入口：

| KEY 在哪里 | 如何使用 |
|---|---|
| 已在环境变量中 | 技能直接传 --key-env 变量名，无需 init 或 get_key；见[已有环境变量](#key-已在环境变量中) |
| 希望由本地 JSON 管理 | 按[最短使用流程](#最短使用流程)登记，再由程序读取；见[本地 JSON 调用](#key-保存在本地-json) |

登记 env_name 只保存变量名说明，不会读取、设置或同步环境变量。两种方式都由调用 AI 选择服务、模型和输出目录。

## 本地文件与示例

默认真实文件是本机用户目录下的 `.layerweave/keys.json`；`--store` 或 Python 的 store 参数可以指定别的文件。文件是本地明文 JSON，供本人程序读取，不是加密密钥库。若放进源码仓库，使用已忽略的 keys.local.json，真实内容不要提交。

包内 [example.json](example.json) 只有演示名称、空 KEY 和中文填写提示，不预设任何技能专属绑定。你注册真实条目后，可导出保留自己名称及 used 的示例上传。出图、生视频等技能也由调用方自行选择连接。

```json
{
  "example-key": {
    "key": "",
    "env_name": "<请填上环境变量名>",
    "base_url": "<请填上模型服务地址>",
    "model": "<请填上你的所选模型>",
    "used": []
  }
}
```

env_name、base_url 和 model 是供调用方参考的字符串，不验证变量名、网址或模型是否可用。model 是默认模型说明，不是 KEY 的使用限制。used 是任意字符串列表，可以填名称、路径或引用；不限定为 skills，不检查目标存在，也不作为权限名单。

## 最短使用流程

完成安装后，用同一个 Python 环境执行：

```sh
python -X utf8 -m layerweave.tool.builtin.developer.keys.cli init --json
python -X utf8 -m layerweave.tool.builtin.developer.keys.cli update example-key --prompt-key --json
python -X utf8 -m layerweave.tool.builtin.developer.keys.cli connections example-key --json
python -X utf8 -m layerweave.tool.builtin.developer.keys.cli export --output keys.example.json --json
```

init 从示例建立空条目，已有文件不会被覆盖；也可用 --template keys.example.json 初始化别人提供的模板。只需要自行注册时，直接 create 会建立缺失的本地文件，不必先 init。

修改连接说明时，把需要修改的字段保存为本地 JSON，例如 connection.json：

```json
{
  "env_name": "MODEL_API_KEY",
  "base_url": "https://provider.example/v1",
  "model": "example-model",
  "used": ["某个技能的名称或路径", "scripts/render.py", "其他程序"]
}
```

上面是填写示意，替换为实际连接信息再执行：

```sh
python -X utf8 -m layerweave.tool.builtin.developer.keys.cli update example-key --data-file connection.json --json
python -X utf8 -m layerweave.tool.builtin.developer.keys.cli read --json
python -X utf8 -m layerweave.tool.builtin.developer.keys.cli delete example-key --json
```

--prompt-key 使用隐藏输入。自动化可用 --key-stdin 从标准输入提供密钥，或从本地 --data-file 读取 key 字段；CLI 不接受把 KEY 直接放在命令行参数里的写法。create/update 省略 key 会保留未配置状态或已有密钥，明确传空字符串则清空密钥。

## 操作与返回

统一 Python 入口是 `layerweave.tool.builtin.developer.keys.service.manage_keys`，现有命令 help 可通过 `keys` 或 `manage_keys` 找到它。

| action | 行为 |
|---|---|
| init | 从内置或指定模板建立本地空条目，不覆盖已有文件 |
| create | 新增名称；同名时提示使用 update |
| read | 指定 name 返回一条，否则返回列表；不存在的文件视为空列表 |
| update | 修改明确提供的字段，used 整个列表替换；不隐式删除其他值 |
| delete | 删除指定条目 |
| connections | 返回全部或指定条目的连接信息列表及 used |
| export | 保留名称和 used，清空 key，三个连接字段替换为固定中文提示；可写入 output |

manage_keys 返回 ok/action/store/data；Python 输入错误抛出异常，CLI 返回非零退出码。--json 的失败结果为 ok=false/error，错误不回显输入内容。普通结果不会返回 key 字段，只显示 key_configured。这个标记仅表示密钥是否已填写，connections 不发送网络请求，也不声称鉴权、余额或模型调用成功。

export 的返回 data 就是模板字典；--output 写出的文件直接是模板，不带返回结果外壳。输出不能指向真实 KEY 文件。记录使用一个本地 JSON 文件，修改以同目录临时文件写好后替换；不保存密钥历史或备份，调用方应顺序编辑这个文件。

## 由调用方使用密钥

以下 get_key 示例要求真实 KEY 已写入本地 JSON；它不会回退读取环境变量。

```python
from layerweave.tool.builtin.developer.keys.service import get_key, manage_keys

# 名称由你注册；store 省略时读取本机默认文件。
connection = manage_keys("read", "example-key")["data"]
key = get_key("example-key")
# 将 key、connection["base_url"]、connection["model"] 交给自己的客户端。
# 环境变量名称也可由调用方自行选择；不要打印 key。
```

get_key 是程序读取接口，不作为 CLI 查询输出。空密钥会明确报告尚未填写。不同调用方可以复用同一条记录，也可以选择与 env_name 不同的变量名；used 只帮助 AI 了解已登记的用途。

## 把连接交给技能子进程

### KEY 已在环境变量中

KEY 已在环境变量里时，直接使用技能的 `--key-env 变量名`，不必存入 keys.json，也不调用 get_key。例如在生视频技能目录运行 `python -X utf8 scripts/video.py --key-env MY_VIDEO_KEY --base-url 服务地址/v2 ping`；出图技能同样支持 --key-env。通过 Python 启动子进程时，使用继承的环境或 child_env = dict(os.environ)，省略下例中调用 get_key 的那一行。仅登记 env_name 不会让 get_key 去读该环境变量。

### KEY 保存在本地 JSON

AI 先用 connections 查看已登记的连接，按所需服务选择条目；used 提供使用指引，不限制选择。条目的 env_name、base_url、model 需要已经填写实际值。地址按技能要求填写，例如出图接口到 /v1，视频接口到 /v2；同一个 KEY 可用于多个调用方。

下面演示 KEY 已写入 keys.json 时如何调用出图技能。先由 AI 设置 entry_name（条目名）、project_dir（已存在的项目工作目录）、output_dir（本次选定的输出目录）、prompt_file（已写好的提示词文件）；三个路径使用 pathlib.Path 的绝对路径。输出目录由 AI 管理，没有固定的项目布局要求。

```python
import os
import subprocess
import sys

from layerweave.support.paths import SKILLS_ROOT
from layerweave.tool.builtin.developer.keys.service import get_key, manage_keys

connection = manage_keys("read", entry_name)["data"]
child_env = dict(os.environ)
child_env[connection["env_name"]] = get_key(entry_name)
output_dir.mkdir(parents=True, exist_ok=True)

subprocess.run([
    sys.executable, "-X", "utf8", "-B",
    str(SKILLS_ROOT / "layers/image/image-generate/scripts/generate.py"),
    str(output_dir / "画面.png"), str(prompt_file),
    "--key-env", connection["env_name"],
    "--base-url", connection["base_url"],
    "--model", connection["model"],
], cwd=project_dir, env=child_env, check=True)
```

视频生成使用同样的步骤，但要先选好视频服务的条目，并将上面的 subprocess.run 替换为：

```python
subprocess.run([
    sys.executable, "-X", "utf8", "-B",
    str(SKILLS_ROOT / "layers/movie/video-generate/scripts/video.py"),
    "--base-url", connection["base_url"],
    "--key-env", connection["env_name"],
    "submit", str(output_dir / "片段.mp4"), str(prompt_file),
    "--model", connection["model"],
], cwd=project_dir, env=child_env, check=True)
```

KEY 只进入这次子进程的环境，不修改全局环境或写进命令参数；不要打印 child_env。模型可在调用参数里换成该任务需要的模型。使用自定义 KEY 文件时，给 manage_keys 和 get_key 传入同一个 store。脚本仍可直接用已有环境变量调用，不要求安装或使用本管理工具。

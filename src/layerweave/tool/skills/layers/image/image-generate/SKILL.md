---
name: image-generate
description: 通过 OpenAI 兼容的图片接口（官方或任意转发站）文生图、带参考图出图：保持角色一致、按 SVG／代码草图锁定构图和姿势、在原图上修改。需要新图、同一角色的新姿势、或要求构图精确服从设计时使用。
---

# 出图

脚本只用 Python 标准库。从本技能目录运行。

输出目录由调用的 AI 按项目管理，output 显式填写包含目录和文件名的路径，建议使用绝对路径；本技能没有固定输出目录。提示词和参考图路径也由 AI 指定。

## 连接
- 地址：`--base-url`；省略时读环境变量 `OPENAI_BASE_URL`；再省略用官方 `https://api.openai.com/v1`。
- KEY：从环境变量读取，默认 `OPENAI_API_KEY`；KEY 放在别的变量里时用 `--key-env 变量名`。脚本不打印 KEY，也不接受把 KEY 写在命令行里。
- 如使用 LayerWeave 的 KEY 管理，参考[子进程调用示例](../../../../builtin/developer/keys/README.md#把连接交给技能子进程)：由 AI 选择条目，把 KEY 注入该次子进程；地址、模型通过参数传入。
- 先确认连接并查看模型名（GET /models，不出图）：

```sh
python scripts/models.py --filter image
```

## 出图

```sh
python scripts/generate.py 输出.png 提示词.txt --model 模型名 [--size 1536x1024] [--style 风格.txt] [--ref 参考1.png 参考2.png]
```

- 提示词写在 UTF-8 文本文件里，便于留档；英文描述通常更稳。
- `--style`：每张都要附加的风格段（例如项目的 style.txt），接在提示词后面。
- `--ref`：给了参考图就走 `/images/edits`。用途：带角色设定图保持一致；带草图锁定构图；在原图上改。可以给多张。
- `--quality`、`--background`（如 `transparent`）只在给出时发送；不同接口支持的取值不同。
- 成功时打印一行 JSON（输出路径、模型、尺寸、参考图、耗时、用量），可直接记进项目的出图记录。
- 网络错误和服务端 5xx 自动重试 3 次；KEY、参数、额度这类 4xx 错误直接报出。
- 一张通常要几十秒到两分钟。互不依赖的几张可以同时跑。

## 用法经验
1. 角色类：先出设定图并选定一张，之后每张都用 `--ref` 带上它。
2. 出完先看图，再决定是否采用；候选和弃用的版本保留，方便回头比较。
3. 姿势、遮挡、空间关系用文字说不清时，先画草图再出图，见 [references/sketch-guide.md](references/sketch-guide.md)。
4. 要补两帧之间的过渡画面时，把前后两帧都作为参考图，并明确要求画"两者正中间的那一刻"；只说"过渡"时，模型常常直接画成后一帧。

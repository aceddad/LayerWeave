---
name: text-normalize
description: 规范纯文本换行并清理行尾空格和制表符，用于已有文字的格式整理。保留措辞、段落与有文字行的缩进；代码、Markdown 或依赖行尾空白的内容不适用。
---

# 纯文本格式整理

使用包内的 [scripts/normalize_text.py](scripts/normalize_text.py) 处理原文。此技能独立于 LayerWeave，也可直接用于其他纯文本。

## 输入与输出

向脚本标准输入提供 JSON，text 为完整原文：

```json
{"text":"第一句  \r\n第二句\t"}
```

从本技能目录运行：

```sh
python -X utf8 -B scripts/normalize_text.py
```

将上面的 JSON 交给命令的标准输入，读取标准输出：

```json
{"text": "第一句\n第二句", "changed": true}
```

## 处理范围

- 将 CRLF 和单独的 CR 换行统一为 LF。
- 删除每行末尾的 ASCII 空格与制表符。
- 保留措辞、标点、行的顺序、空行数量和末尾换行；有文字行的行首缩进保持。
- changed 表示返回文本是否与输入不同。将结果交回调用方，不额外改写内容。

脚本只读标准输入、写标准输出。需要保存结果时，由调用的 AI 选择输出目录与文件名，再使用已有的写入方式保存。

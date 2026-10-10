"""检查源码里有没有写死原文片段（例如歌词）。只打印 文件:行号 和匹配到的字符数，不打印原文内容。

python scripts/find_hardcoded_text.py 原文.srt|原文.json 源码文件 [源码文件 ...] [--min-letters 4]
原文可以是 SRT 字幕，或 JSON：字符串列表，或带 "text" 字段的对象列表。
"""
import argparse
import json
import re


def load_texts(path):
    with open(path, encoding="utf-8-sig") as handle:
        raw = handle.read()
    if path.lower().endswith(".srt"):
        blocks = re.split(r"\n\s*\n", raw.strip())
        texts = []
        for block in blocks:
            lines = [line for line in block.splitlines() if line.strip()]
            body = [line for line in lines if not line.strip().isdigit() and "-->" not in line]
            texts.append(" ".join(body))
        return [t.lower() for t in texts if t]
    data = json.loads(raw)
    return [str(item.get("text", "") if isinstance(item, dict) else item).lower() for item in data]


def main():
    p = argparse.ArgumentParser(description="查源码里写死的原文片段")
    p.add_argument("source"); p.add_argument("files", nargs="+")
    p.add_argument("--min-letters", type=int, default=4, help="引号里至少有这么多个字母或汉字才比较")
    a = p.parse_args()
    texts = load_texts(a.source)
    quoted = re.compile(r"""['"`]([^'"`\n]{2,})['"`]""")
    total = 0
    for path in a.files:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for number, line in enumerate(handle, 1):
                for match in quoted.finditer(line):
                    fragment = match.group(1).strip().lower()
                    if sum(ch.isalpha() for ch in fragment) < a.min_letters:
                        continue
                    if any(fragment in text for text in texts):
                        total += 1
                        print(f"{path}:{number}  与原文重合（{len(fragment)} 个字符）")
    print("total matches:", total)


if __name__ == "__main__":
    main()

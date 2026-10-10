"""纯文本格式整理示例；与 LayerWeave 的配置、数据库和内部工具无依赖。"""

import json
import sys


def normalize_text(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip(" \t") for line in lines)


def main():
    source = json.load(sys.stdin)["text"]
    normalized = normalize_text(source)
    json.dump({"text": normalized, "changed": normalized != source}, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

"""出一张图。给了 --ref 就走 /images/edits（保持角色一致、照草图构图、在原图上改），否则走 /images/generations。

python scripts/generate.py 输出.png 提示词.txt --model 模型名 [--style 风格.txt] [--size 1024x1024]
                           [--quality high] [--background transparent] [--ref 参考1.png 参考2.png]
                           [--base-url 地址] [--key-env 变量名]
成功时在标准输出打印一行 JSON：output、model、size、refs、seconds、usage。
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import Connection, RequestFailed, add_connection_args, with_retry  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="用 OpenAI 兼容的图片接口出一张图")
    parser.add_argument("output", help="输出图片路径（.png）")
    parser.add_argument("prompt_file", help="提示词文本文件（UTF-8）")
    parser.add_argument("--model", required=True, help="模型名；不确定时先运行 scripts/models.py")
    parser.add_argument("--style", help="每张图都要附加的风格段文件，接在提示词后面")
    parser.add_argument("--size", default="1024x1024", help="例如 1024x1024、1536x1024、1024x1536")
    parser.add_argument("--quality", help="例如 low / medium / high；省略时不发送，用接口默认值")
    parser.add_argument("--background", help="例如 transparent；省略时不发送")
    parser.add_argument("--ref", nargs="*", default=[], help="参考图，可多张；给了就走 /images/edits")
    add_connection_args(parser)
    args = parser.parse_args()

    with open(args.prompt_file, encoding="utf-8-sig") as handle:
        prompt = handle.read().strip()
    if args.style:
        with open(args.style, encoding="utf-8-sig") as handle:
            prompt += "\n\n" + handle.read().strip()
    for path in args.ref:
        if not os.path.isfile(path):
            sys.exit(f"参考图不存在：{path}")

    connection = Connection(args.base_url, args.key_env)
    options = {"model": args.model, "prompt": prompt, "size": args.size}
    if args.quality:
        options["quality"] = args.quality
    if args.background:
        options["background"] = args.background

    def call():
        if args.ref:
            fields = {**options, "n": "1"}
            return connection.multipart("/images/edits", fields, [("image[]", path) for path in args.ref])
        return connection.json("/images/generations", {**options, "n": 1})

    started = time.time()
    try:
        result = with_retry(call)
    except RequestFailed as error:
        sys.exit(f"请求失败：{error}")
    item = result["data"][0]
    if item.get("b64_json"):
        image = base64.b64decode(item["b64_json"])
    else:
        with urllib.request.urlopen(item["url"], timeout=300) as response:
            image = response.read()
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "wb") as handle:
        handle.write(image)
    print(json.dumps({"output": args.output, "model": args.model, "size": args.size, "refs": args.ref,
                      "seconds": round(time.time() - started), "usage": result.get("usage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

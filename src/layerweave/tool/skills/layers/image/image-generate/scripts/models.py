"""列出接口上可用的模型名（GET /models，不出图、通常不计费），也可用来确认地址和 KEY 能用。

python scripts/models.py [--filter image] [--base-url 地址] [--key-env 变量名]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import Connection, RequestFailed, add_connection_args  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="列出接口上的模型名")
    parser.add_argument("--filter", default="", help="只列出名字里含这个字符串的模型，例如 image")
    add_connection_args(parser)
    args = parser.parse_args()
    try:
        result = Connection(args.base_url, args.key_env).json("/models", timeout=60)
    except RequestFailed as error:
        sys.exit(f"请求失败：{error}")
    names = sorted(item["id"] for item in result.get("data", []) if args.filter in item["id"])
    print(f"{len(names)} 个模型")
    for name in names:
        print(" ", name)


if __name__ == "__main__":
    main()

"""OpenAI 兼容图片接口的最小客户端：只用标准库。

地址：--base-url，其次环境变量 OPENAI_BASE_URL，默认 https://api.openai.com/v1。
KEY：从 --key-env 指定的环境变量读取（默认 OPENAI_API_KEY）；不打印、不写文件、不接受命令行明文。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_KEY_ENV = "OPENAI_API_KEY"


def add_connection_args(parser):
    parser.add_argument("--base-url", default=None,
                        help=f"接口地址；省略时读 OPENAI_BASE_URL，再省略用 {DEFAULT_BASE_URL}")
    parser.add_argument("--key-env", default=DEFAULT_KEY_ENV,
                        help=f"存放 KEY 的环境变量名，默认 {DEFAULT_KEY_ENV}")


class Connection:
    def __init__(self, base_url=None, key_env=DEFAULT_KEY_ENV):
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.key_env = key_env

    def key(self):
        value = os.environ.get(self.key_env)
        if not value:
            sys.exit(f"未找到环境变量 {self.key_env}：请把 KEY 放进这个变量，或用 --key-env 指定别的变量名")
        return value

    def _open(self, request, timeout):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            raise RequestFailed(error.code, detail) from None

    def json(self, path, body=None, *, timeout=900, method=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.base_url + path, data=data, method=method or ("POST" if data else "GET"),
            headers={"Authorization": "Bearer " + self.key(), "Content-Type": "application/json"})
        return self._open(request, timeout)

    def multipart(self, path, fields, files, *, timeout=900):
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in fields.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        for name, file_path in files:
            filename = os.path.basename(file_path).encode("ascii", "replace").decode()
            with open(file_path, "rb") as handle:
                content = handle.read()
            parts += [f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                      f'Content-Type: {_mime(file_path)}\r\n\r\n'.encode(), content, b"\r\n"]
        parts.append(f"--{boundary}--\r\n".encode())
        request = urllib.request.Request(
            self.base_url + path, data=b"".join(parts),
            headers={"Authorization": "Bearer " + self.key(),
                     "Content-Type": f"multipart/form-data; boundary={boundary}"})
        return self._open(request, timeout)


class RequestFailed(Exception):
    def __init__(self, status, detail):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status


def _mime(path):
    ext = os.path.splitext(path)[1].lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "image/png")


def with_retry(call, attempts=4, wait=5):
    """网络错误和 5xx 重试；4xx（KEY、参数、额度）直接报出，不浪费重试。"""
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except RequestFailed as error:
            if error.status < 500 or attempt == attempts:
                raise
            print(f"第 {attempt} 次失败：{error}；{wait} 秒后重试", file=sys.stderr)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            if attempt == attempts:
                raise
            print(f"第 {attempt} 次失败：{type(error).__name__}: {str(error)[:120]}；{wait} 秒后重试", file=sys.stderr)
        time.sleep(wait)

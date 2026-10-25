"""传输 JSON 的二进制表示；业务 JSON 字段仍使用严格的标准 JSON 编码。"""
from base64 import b64encode


def binary_json_default(value):
    """供 json.dumps(default=...) 使用；仅处理字节，不猜测字符串或字典。"""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return b64encode(bytes(value)).decode("ascii")
    raise TypeError(f"{type(value).__name__} 不能编码为 JSON")

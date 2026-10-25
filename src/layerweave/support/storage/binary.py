"""按列声明转换 BLOB；快照解码不补字段，不改变普通 TEXT/JSON。"""
from base64 import b64decode
from binascii import Error as Base64Error

from layerweave.support.feedback import InputError
from layerweave.support.serialization import binary_json_default


def blob_fields(spec):
    return {name for name, column in spec.get("columns", {}).items() if column["type"] == "BLOB"}


def normalize_binary(spec, record):
    """写入原语只接收字节或 NULL，避免 SQLite 将字符串存为 TEXT。"""
    if record is None:
        return None
    result = dict(record)
    for name in blob_fields(spec) & result.keys():
        value = result[name]
        if value is None:
            continue  # 非空约束仍交给 SQLite。
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise InputError(f"BLOB 字段 {name} 需要 bytes、bytearray、memoryview 或 None",
                             code="blob_type", field=name)
        result[name] = bytes(value)
    return result


def encode_binary(spec, record):
    """日志、交换快照的 JSON 表示；原字段集合保持不变。"""
    result = normalize_binary(spec, record)
    if result is not None:
        for name in blob_fields(spec) & result.keys():
            if result[name] is not None:
                result[name] = binary_json_default(result[name])
    return result


def decode_binary(spec, record):
    """JSON 请求/快照按声明解码；Python 调用已经是字节时保持其含义。"""
    if record is None:
        return None
    result = dict(record)
    for name in blob_fields(spec) & result.keys():
        value = result[name]
        if isinstance(value, str):
            try:
                result[name] = b64decode(value, validate=True)
            except (ValueError, Base64Error) as error:
                raise InputError(f"BLOB 字段 {name} 需要标准 Base64 字符串",
                                 code="blob_base64", field=name) from error
    return normalize_binary(spec, result)

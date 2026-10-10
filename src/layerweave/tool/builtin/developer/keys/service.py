"""本地 KEY 条目的 JSON 管理；公开结果只含元信息，密钥由 get_key 显式读取。"""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile

from layerweave.support.feedback import InputError


FIELDS = ("key", "env_name", "base_url", "model", "used")
PROMPTS = {"env_name": "<请填上环境变量名>", "base_url": "<请填上模型服务地址>",
           "model": "<请填上你的所选模型>"}
EXAMPLE_PATH = Path(__file__).with_name("example.json")
ACTIONS = ("init", "create", "read", "update", "delete", "connections", "export")


def store_path(store=None):
    return (Path(store).expanduser() if store is not None else Path.home() / ".layerweave/keys.json").resolve()


def _name(name):
    if not isinstance(name, str) or not name.strip():
        raise InputError("需要非空的 KEY 条目名称", field="name")


def _fields(data):
    if not isinstance(data, dict):
        raise InputError("条目内容需要是 JSON 对象", field="data", allowed=list(FIELDS))
    if set(data) - set(FIELDS):
        # 不回显未知字段及输入值，避免把误填位置的密钥放进异常。
        raise InputError("包含未支持的字段", field="data", allowed=list(FIELDS))
    for field, value in data.items():
        valid = isinstance(value, list) and all(isinstance(item, str) for item in value) if field == "used" else isinstance(value, str)
        if not valid:
            raise InputError("used 需要字符串列表" if field == "used" else "字段需要字符串", field=field)
    return deepcopy(data)


def _load(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError) as error:
        raise InputError("KEY 文件不是有效的 UTF-8 JSON，未改写原文件", code="invalid_key_store") from error
    if not isinstance(data, dict):
        raise InputError("KEY 文件最外层需要是名称到条目的对象", code="invalid_key_store")
    for name, record in data.items():
        _name(name)
        _fields(record)
    return data


def _record(record):
    return {"key": "", "env_name": "", "base_url": "", "model": "", "used": [], **record}


def _public(name, record):
    record = _record(record)
    return {"name": name, "key_configured": bool(record["key"].strip()),
            **{field: deepcopy(record[field]) for field in FIELDS if field != "key"}}


def _get(records, name):
    _name(name)
    if name not in records:
        raise InputError("KEY 条目不存在", code="key_not_found", field="name", allowed=list(records))
    return records[name]


def _text(records):
    return json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _write(path, records):
    """在同目录写好临时文件再替换；失败保留原文件，不另存包含密钥的备份。"""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(_text(records))
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _example(records):
    return {name: {"key": "", **PROMPTS, "used": deepcopy(_record(record)["used"])}
            for name, record in records.items()}


def get_key(name, *, store=None):
    """供程序读取实际 KEY；不打印、不记录日志、不改环境变量。"""
    key = _record(_get(_load(store_path(store)), name))["key"]
    if not key.strip():
        raise InputError("此条目的 KEY 尚未填写", code="key_not_configured", field="key")
    return key


def manage_keys(action="read", name=None, *, data=None, store=None, template=None, output=None):
    """增删查改、连接信息查看及空模板初始化/导出。返回值不会包含实际 KEY。"""
    if action not in ACTIONS:
        raise InputError("未知 KEY 操作", field="action", allowed=list(ACTIONS))
    if data is not None and action not in {"create", "update"}:
        raise InputError("data 只用于 create/update", field="data")
    if template is not None and action != "init":
        raise InputError("template 只用于 init", field="template")
    if output is not None and action != "export":
        raise InputError("output 只用于 export", field="output")
    if name is not None and action in {"init", "export"}:
        raise InputError("此操作针对整个文件，不接受条目名称", field="name")
    path = store_path(store)
    if action == "init":
        source = Path(template).expanduser().resolve() if template is not None else EXAMPLE_PATH
        if not source.is_file():
            raise InputError("示例文件不存在", field="template")
        records = _example(_load(source))
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            # 新建空模板时使用独占创建，已有的真实记录不被初始化覆盖。
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as error:
            raise InputError("本地 KEY 文件已存在，未覆盖", code="key_store_exists", field="store") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(_text(records))
        result = [_public(key_name, record) for key_name, record in records.items()]
    else:
        records = _load(path)
        if action == "create":
            _name(name)
            if name in records:
                raise InputError("KEY 名称已存在，请使用 update", code="key_exists", field="name")
            records[name] = _record(_fields({} if data is None else data))
            _write(path, records)
            result = _public(name, records[name])
        elif action == "update":
            current = _get(records, name)
            updated = {**current, **_fields({} if data is None else data)}
            if updated != current:
                records[name] = updated
                _write(path, records)
            result = _public(name, updated)
        elif action == "delete":
            result = _public(name, _get(records, name))
            del records[name]
            _write(path, records)
        elif action in {"read", "connections"}:
            if name is not None:
                result = _public(name, _get(records, name))
                if action == "connections":
                    result = [result]
            else:
                result = [_public(key_name, record) for key_name, record in records.items()]
        else:
            result = _example(records)
            if output is not None:
                destination = Path(output).expanduser().resolve()
                if destination == path or (destination.exists() and path.exists() and os.path.samefile(destination, path)):
                    raise InputError("示例输出不能覆盖真实 KEY 文件", field="output")
                _write(destination, result)
    return {"ok": True, "action": action, "store": str(path), "data": result}

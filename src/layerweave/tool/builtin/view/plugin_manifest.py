"""视图插件 v1 声明与兼容判断；只读元数据，不导入插件。"""
from .i18n import ViewError

import json
from pathlib import Path, PurePosixPath
import re
import tomllib

PART = re.compile(r"[a-z][a-z0-9_-]{0,39}")
PARAM = re.compile(r"[a-z][a-z0-9_]{0,31}")
VERSION = r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
HOST_API = 3
KINDS = {"string", "integer", "number", "boolean", "array", "object"}
# URL 属于宿主的字段共用这一份；插件参数不能改变项目和截图控制。
LINK_KEYS = ("lang", "view", "board", "begin", "end", "playhead", "select", "focus", "note", "changes", "layers", "side", "links", "walk", "walkdir", "walkdepth")
OWN_KEYS = {*LINK_KEYS, "project", "record", "capture", "full", "tree", "as", "media"}


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(VERSION, value):
        raise ValueError(f"版本要写成三段非负整数（如 1.0.0）：{value!r}")
    return tuple(map(int, value.split(".")))


def valid_id(value):
    return isinstance(value, str) and len(parts := value.split(".")) == 2 and all(PART.fullmatch(p) for p in parts)


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ViewError("pluginError.relativePath", {"value1": repr(value)})
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ViewError("pluginError.pathEscape", {"value1": repr(value)})
    return path.as_posix()


def inside(folder, relative):
    folder = Path(folder).resolve()
    path = (folder / relative_path(relative)).resolve()
    if not path.is_relative_to(folder):
        raise ViewError("pluginError.fileEscape", {"value1": relative})
    return path


def requirements(value):
    if not isinstance(value, dict):
        raise ValueError("requires 必须声明 view 和 host_api")
    spec = value.get("view")
    match = re.fullmatch(r">=(\d+\.\d+\.\d+)(?:\s*,\s*<(\d+\.\d+\.\d+))?", spec or "") if isinstance(spec, str) else None
    if not match:
        raise ValueError("requires.view 只支持 >=0.27.0 或 >=0.27.0,<1.0.0")
    lower, upper = version_tuple(match[1]), version_tuple(match[2]) if match[2] else None
    if upper and upper <= lower:
        raise ValueError("requires.view 的上界必须大于下界")
    apis = value.get("host_api")
    if not isinstance(apis, list) or not apis or any(type(v) is not int or v < 1 for v in apis):
        raise ValueError("requires.host_api 要写成明确支持的代数列表，例如 [3]")
    return lower, upper, apis


def current_version():
    return tomllib.loads(Path(__file__).with_name("component.toml").read_text(encoding="utf-8"))["version"]


def compatibility(requires, *, view_version=None, host_api=HOST_API):
    lower, upper, apis = requirements(requires)
    current = view_version or current_version()
    number = version_tuple(current)
    reasons = []
    if number < lower or (upper is not None and number >= upper):
        reasons.append(f"需要视图 {requires['view']}，当前 {current}")
    if host_api not in apis:
        reasons.append(f"支持 host.api={apis}，当前 {host_api}")
    return "；".join(reasons) or None


def manifest(data, *, files_root=None):
    if not isinstance(data, dict) or data.get("format") != 1:
        raise ViewError("pluginError.format")
    if data.get("kind") != "view-plugin":
        raise ViewError("pluginError.kind", {"value1": repr(data.get('kind'))})
    for key in ("publisher", "name"):
        if not isinstance(data.get(key), str) or not PART.fullmatch(data[key]):
            raise ValueError(f"{key} 要用小写字母开头的字母、数字、- 或 _，最多 40 字符")
    version_tuple(data.get("version"))
    for key in ("label", "description"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ViewError("pluginError.manifestMissing", {"value1": key})
    requirements(data.get("requires"))
    result = {"entry": "plugin.js", "usage": "README.md", "params": {}, **data}
    result["id"] = data["publisher"] + "." + data["name"]
    for key in ("entry", "usage", "license_file"):
        if key not in result:
            continue
        result[key] = relative_path(result[key])
        if files_root is not None and not inside(files_root, result[key]).is_file():
            raise ValueError(f"{key} 指向的文件不存在：{result[key]}")
    if Path(result["entry"]).suffix not in (".js", ".mjs"):
        raise ViewError("pluginError.entry")
    locales = result.get("locales", {})
    if not isinstance(locales, dict) or not all(isinstance(k, str) for k in locales):
        raise ViewError("pluginError.locales")
    for lang, path in locales.items():
        relative_path(path)
    params = result["params"]
    if not isinstance(params, dict):
        raise ViewError("pluginError.params")
    for key, spec in params.items():
        if not PARAM.fullmatch(key) or key in OWN_KEYS:
            raise ViewError("pluginError.reservedParam", {"value1": key})
        if not isinstance(spec, dict) or spec.get("type") not in KINDS or not isinstance(spec.get("description"), str):
            raise ValueError(f"params.{key} 需要 type 和 description")
        if "required" in spec and type(spec["required"]) is not bool:
            raise ValueError(f"params.{key}.required 必须是布尔值")
        if spec.get("required") and "default" in spec:
            raise ValueError(f"params.{key} 不能同时声明 required=true 和 default")
        if spec["type"] == "array" and (not isinstance(spec.get("items"), dict) or spec["items"].get("type") not in KINDS):
            raise ValueError(f"params.{key} 需要 items.type")
    for key in ("handles", "slots", "languages"):
        if key in result and (not isinstance(result[key], list) or not all(isinstance(v, str) for v in result[key])):
            raise ValueError(f"{key} 必须是字符串数组")
    return result


def read_manifest(folder):
    try:
        data = json.loads((Path(folder) / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ViewError("pluginError.manifestRead", {"value1": error}) from error
    return manifest(data, files_root=folder)


def check_params(specs, values):
    """检查传输值，不注入默认值，不更改原字符串；未知参数仅提醒。"""
    warnings = []
    def matches(value, kind):
        return {"string": lambda: isinstance(value, str), "integer": lambda: type(value) is int,
                "number": lambda: type(value) in (int, float), "boolean": lambda: type(value) is bool,
                "array": lambda: isinstance(value, list), "object": lambda: isinstance(value, dict)}[kind]()
    for name, spec in specs.items():
        if name not in values:
            if spec.get("required"):
                raise ValueError(f"插件参数 {name} 必须提供（{spec['type']}）：{spec['description']}")
            continue
        raw = values[name]
        try:
            value = raw if spec["type"] == "string" else json.loads(raw, parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
            if not matches(value, spec["type"]):
                raise ValueError()
            if spec["type"] == "array" and not all(matches(item, spec["items"]["type"]) for item in value):
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError(f"插件参数 {name} 需要 {spec['type']}，收到 {raw!r}") from None
    for key in values:
        if key not in specs:
            warnings.append({"severity": "warn", "field": key, "message": f"未声明的插件参数 {key}，仍按原值传递"})
    return warnings

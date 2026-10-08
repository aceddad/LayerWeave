"""每次检测复用一个 Loader；只读取 TOML，不导入配置中的 class。"""

from copy import deepcopy
from pathlib import Path
import tomllib


DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "configs"


class ConfigError(ValueError):
    """某份配置无法解释，调用方将其作为单条诊断报告。"""


def _fixed(parent, child, location):
    """固定约定只能增加或重复，不能覆盖已有值。"""
    result = deepcopy(parent)
    for key, value in child.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _fixed(result[key], value, f"{location}.{key}")
        elif key in result and result[key] != value:
            raise ConfigError(f"{location}.{key} 改写父约定：{result[key]!r} → {value!r}")
        else:
            result[key] = deepcopy(value)
    return result


class Loader:
    def __init__(self, root=DEFAULT_ROOT):
        self.root = Path(root).resolve()
        self.cache = {}
        self.index = None

    def ref(self, path):
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def load(self, ref, kind, _chain=()):
        path = (self.root / ref).resolve()
        key = (kind, path)
        if key in _chain:
            chain = " → ".join(self.ref(item[1]) for item in (*_chain, key))
            raise ConfigError(f"配置继承成环：{chain}")
        if key in self.cache:
            cached = self.cache[key]
            if isinstance(cached, ConfigError):
                raise cached
            return cached
        try:
            with path.open("rb") as file:
                raw = tomllib.load(file)[kind]
            if not isinstance(raw.get("type"), str):
                raise ConfigError(f"{self.ref(path)} 缺少 {kind}.type 字符串")
            parent = None
            if "extends" in raw:
                parent_path = (path.parent / raw["extends"]).resolve()
                parent = self.load(str(parent_path), kind, (*_chain, key))
            result = self._merge(parent, raw)
            result["_ref"] = self.ref(path)
            result["_lineage"] = [*(parent["_lineage"] if parent else []), self.ref(path)]
            if kind == "layer" and parent and "objects" in raw and raw["objects"] != parent.get("objects"):
                expected = self.object_config(parent["objects"])
                declared = self.object_config(raw["objects"])
                if expected["_ref"] not in declared["_lineage"]:
                    raise ConfigError("layer.objects 必须保留父配置接受的对象类型，或收窄为它的派生类型")
            self.cache[key] = result
            return result
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            failure = error if isinstance(error, ConfigError) else ConfigError(f"{self.ref(path)}：{error}")
            self.cache[key] = failure
            raise failure

    def _merge(self, parent, raw):
        result = deepcopy(parent) if parent else {}
        # 只有 default/note 是字段说明；字段类型等声明属于固定约定。
        for section in ("fields", "information"):
            declarations = result.setdefault(section, {})
            for field, spec in raw.get(section, {}).items():
                old = declarations.get(field, {})
                fixed_old = {k: v for k, v in old.items() if k not in {"note", "default"}}
                fixed_new = {k: v for k, v in spec.items() if k not in {"note", "default"}}
                declarations[field] = {**old, **spec, **_fixed(fixed_old, fixed_new, f"{section}.{field}")}
        contracts = deepcopy(parent.get("_contracts", {})) if parent else {}
        defaults = deepcopy(result.get("defaults", {}))
        for section, values in raw.get("defaults", {}).items():
            defaults.setdefault(section, {}).update(values)
        result["defaults"] = defaults
        for section in ("rules", "constraint", "display"):
            contracts[section] = _fixed(contracts.get(section, {}), raw.get(section, {}), section)
            result[section] = {**defaults.get(section, {}), **contracts[section]}
        if parent and "open" in parent and "open" in raw and raw["open"] != parent["open"]:
            raise ConfigError("object.open 改写父约定")
        result["_contracts"] = contracts
        # options 是明确允许派生调整的选项，当前只有 axis_only_on_root。
        result["options"] = {**result.get("options", {}), **raw.get("options", {})}
        for key, value in raw.items():
            if key not in {"fields", "information", "defaults", "rules", "constraint", "display", "options"}:
                result[key] = deepcopy(value)
        return result

    def object_config(self, type_name):
        if self.index is None:
            self.index = {}
            for path in sorted((self.root / "objects").rglob("*.toml")):
                try:
                    with path.open("rb") as file:
                        name = tomllib.load(file)["object"]["type"]
                    self.index.setdefault(name, []).append(self.ref(path))
                except (OSError, ValueError, KeyError, TypeError):
                    # 无关的损坏文件不阻断当前目标；直接引用时仍会报告原始错误。
                    continue
        refs = self.index.get(type_name, [])
        if len(refs) != 1:
            raise ConfigError(f"对象配置 {type_name!r} 无法唯一定位：找到 {len(refs)} 份")
        return self.load(refs[0], "object")

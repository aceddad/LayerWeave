"""每次检测复用一个 Loader；只读取 TOML，不导入配置中的 class。"""

from copy import deepcopy
from difflib import get_close_matches
from pathlib import Path
import tomllib

from ..values import same_value
from ..feedback import InputError


DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "configs"


class ConfigError(InputError):
    """某份配置无法解释，调用方将其作为单条诊断报告。"""


def _fixed(parent, child, location):
    """固定约定只能增加或重复，不能覆盖已有值。"""
    result = deepcopy(parent)
    for key, value in child.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _fixed(result[key], value, f"{location}.{key}")
        elif key in result and not same_value(result[key], value):
            raise ConfigError(f"{location}.{key} 改写父约定：{result[key]!r} → {value!r}")
        else:
            result[key] = deepcopy(value)
    return result


class Loader:
    def __init__(self, root=DEFAULT_ROOT):
        self.root = Path(root).resolve()
        self.cache = {}
        self.indexes = {}
        self.raw_cache = {}

    def _raw(self, path, kind):
        key = (kind, path)
        if key not in self.raw_cache:
            with path.open("rb") as file:
                self.raw_cache[key] = tomllib.load(file)[kind]
        return self.raw_cache[key]

    def ref(self, path):
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def _missing(self, path, kind):
        ref = self.ref(path)
        refs = sorted(self.ref(item) for item in (self.root / f"{kind}s").rglob("*.toml"))
        close = get_close_matches(ref, refs, n=3, cutoff=0.5)
        candidates = (close + [item for item in refs if item not in close])[:8]
        return ConfigError(f"配置不存在：{ref}", code="config_not_found", field="config_ref",
                           value=ref, candidates=candidates, candidate_count=len(refs))

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
            raw = self._raw(path, kind)
            if not isinstance(raw.get("type"), str):
                raise ConfigError(f"{self.ref(path)} 缺少 {kind}.type 字符串")
            if not isinstance(raw.get("class"), str) or ":" not in raw["class"]:
                raise ConfigError(f"{self.ref(path)} 必须明确声明自己的 {kind}.class（模块:类），不能继承父类绑定")
            refs = self._index(kind)["class"].get(raw["class"], [])
            # 直接引用根目录外的配置时，也将当前文件计入唯一性判断。
            refs = sorted(set([*refs, self.ref(path)]))
            if len(refs) != 1:
                raise ConfigError(f"{raw['class']} 必须只绑定一份配置，实际为：{', '.join(refs)}")
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
            if isinstance(error, FileNotFoundError):
                failure = self._missing(path, kind)
            elif isinstance(error, OSError):
                failure = ConfigError(f"无法读取配置 {self.ref(path)}：{error.strerror}",
                                      code="config_unreadable", field="config_ref", value=self.ref(path))
            else:
                failure = error if isinstance(error, ConfigError) else ConfigError(f"{self.ref(path)}：{error}")
            if not failure.details:
                failure.details.update(code="config_invalid", field="config_ref", value=self.ref(path))
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
        if parent and "open" in parent and "open" in raw and not same_value(raw["open"], parent["open"]):
            raise ConfigError("object.open 改写父约定")
        result["_contracts"] = contracts
        # options 是明确允许派生调整的选项，当前只有 axis_only_on_root。
        result["options"] = {**result.get("options", {}), **raw.get("options", {})}
        for key, value in raw.items():
            if key not in {"fields", "information", "defaults", "rules", "constraint", "display", "options"}:
                result[key] = deepcopy(value)
        return result

    def _index(self, kind):
        """同一个 Loader 内每种配置只扫描一次，同时索引名称与直接声明的类。"""
        if kind not in self.indexes:
            index = {"type": {}, "class": {}}
            for path in sorted((self.root / f"{kind}s").rglob("*.toml")):
                try:
                    section = self._raw(path.resolve(), kind)
                    for key in index:
                        value = section.get(key)
                        if isinstance(value, str):
                            index[key].setdefault(value, []).append(self.ref(path))
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    # 无关的损坏文件不阻断当前目标；直接引用时仍会报告原始错误。
                    continue
            self.indexes[kind] = index
        return self.indexes[kind]

    def class_config(self, class_path, kind):
        refs = self._index(kind)["class"].get(class_path, [])
        if len(refs) != 1:
            raise ConfigError(f"{class_path} 必须只绑定一份配置，实际找到 {len(refs)} 份：{', '.join(refs)}")
        return refs[0]

    def object_config(self, type_name):
        refs = self._index("object")["type"].get(type_name, [])
        if len(refs) != 1:
            raise ConfigError(f"对象配置 {type_name!r} 无法唯一定位：找到 {len(refs)} 份")
        return self.load(refs[0], "object")

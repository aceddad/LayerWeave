"""动态配置 help：发现、合并、兼容关系与说明数据，无数据库或模型导入。"""

from datetime import date, datetime, time
from math import isfinite

from .loader import DEFAULT_ROOT, ConfigError, Loader
from .help_data import field_origins, io_help, reporting_exceptions, save_example, usage
from ..feedback import InputError, error_detail
from ..validation.channel import report
from ..validation.diagnostics import DiagnosticPolicy, prepare_diagnostics


VIEWS = ("overview", "layers", "objects", "combined")
AUDIENCES = ("usage", "developer")
INTERNAL_KEYS = {"_ref", "_lineage", "_contracts"}
SUMMARY_KEYS = ("type", "name", "class", "when", "note", "not_for", "tools")


def _json_value(value):
    """TOML 的额外日期时间/非有限数值也能展示，原文可通过 source 查看。"""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, float) and not isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _summary(config):
    return {"config_ref": config["_ref"], **{key: config[key] for key in SUMMARY_KEYS if key in config}}


class _Catalog:
    def __init__(self, config_root, include_source, audience):
        self.loader = Loader(config_root)
        if not self.loader.root.is_dir():
            raise InputError(f"配置目录不存在：{self.loader.root}", field="config_root", code="config_not_found")
        self.policy = DiagnosticPolicy(config_root)
        self.include_source = include_source
        self.audience = audience
        self.loaded, self.issues = {}, []
        self.objects = None

    def issue(self, ref, kind, error, *, resolved=True):
        self.issues.append({"rule": "config_help", "code": "config_invalid", "field": "config_ref",
                            **error_detail(error), **({"config_ref": ref} if resolved else {}),
                            "target": {"kind": "configuration", "id": ref, "category": kind}})

    def load(self, ref, kind):
        ref = self.loader.ref((self.loader.root / ref).resolve())
        key = (kind, ref)
        if key not in self.loaded:
            try:
                self.loaded[key] = self.loader.load(ref, kind)
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.loaded[key] = None
                self.issue(ref, kind, error)
        return self.loaded[key]

    def resolve(self, target, kind):
        if not isinstance(target, str):
            raise InputError("查询目标应为配置路径、type 或 Python 类名", code="target", field="targets")
        target = target.replace("\\", "/")
        if target.lower().endswith(".toml"):
            return self.loader.ref((self.loader.root / target).resolve())
        refs = self.loader.find_configs(target, kind)
        if len(refs) == 1:
            return refs[0]
        candidates = refs or self.loader.refs(kind)
        reason = "存在多个匹配，请使用配置路径" if refs else "没有找到对应封装"
        raise InputError(f"{target!r}：{reason}", code="target", field="targets",
                         candidates=candidates[:8], candidate_count=len(candidates))

    def compatible(self, config):
        if self.objects is None:
            self.objects = [(ref, self.load(ref, "object")) for ref in self.loader.refs("object")]
        complete = all(obj is not None for ref, obj in self.objects)
        try:
            # 即使对象目录为空，也必须说明期望类型是否存在。
            self.loader.object_config(config["objects"])
            accepted = [obj for ref, obj in self.objects if obj is not None and self.loader.accepts_object(config, obj)]
        except (ConfigError, KeyError, TypeError) as error:
            self.issue(config["_ref"], "layer", error)
            return [], False
        return accepted, complete

    def reporting(self, config):
        ref = config["_ref"]
        fields = {name: {"field_type": self.policy.level("field_type", config_ref=ref, field=name)}
                  for name in config.get("fields", {})}
        information = {name: {code: self.policy.level(code, config_ref=ref, field=f"information.{name}")
                              for code in ("missing_field", "field_type")}
                       for name in config.get("information", {})}
        declarations = {section: {name: self.policy.describe(name, config_ref=ref) for name in config.get(section, {})}
                        for section in ("rules", "constraint", "options")}
        return {"fallback": "warn", "fields": fields, "information": information,
                "field_typo": self.policy.describe("field_typo", config_ref=ref), **declarations}

    def entry(self, ref, kind, *, detail, target=None):
        ref = self.loader.ref((self.loader.root / ref).resolve())
        config = self.load(ref, kind)
        entry = {"target": ref if target is None else target, "kind": kind, "config_ref": ref,
                 "status": "loaded" if config is not None else "unavailable"}
        if self.include_source:
            try:
                entry["source"] = self.loader.source(ref)
            except (OSError, UnicodeError):
                pass  # 读取失败已由 load 逐项报告；语法损坏但可读的原文仍保留。
        if config is not None:
            if detail:
                entry["save_example"] = save_example(config, kind, self.loader.root)
                if self.audience == "developer":
                    entry.update(definition={key: value for key, value in config.items() if key not in INTERNAL_KEYS},
                                 lineage=config["_lineage"], fixed_contracts=config["_contracts"],
                                 reporting=self.reporting(config), field_origins=field_origins(self.loader, config, kind))
                else:
                    entry.update(summary=_summary(config), usage=usage(config))
                    exceptions = reporting_exceptions(config, self.policy)
                    if exceptions:
                        entry["reporting_exceptions"] = exceptions
            else:
                entry["summary"] = _summary(config)
            if kind == "layer":
                accepted, complete = self.compatible(config)
                entry["accepted_objects"] = [_summary(obj) for obj in accepted]
                entry["accepted_objects_complete"] = complete
                if not complete:
                    entry["status"] = "partial"
        return entry


def read_support(view="overview", targets=None, *, config_root=DEFAULT_ROOT, audience="usage", include_source=None):
    """四种 help 都查看封装定义；后三项接受单个或多个配置路径/type/类名。"""
    if view not in VIEWS:
        raise InputError(f"未知 help 视图：{view}", field="view", code="target", allowed=list(VIEWS))
    if audience not in AUDIENCES:
        raise InputError(f"未知 help 用途：{audience}", field="audience", allowed=list(AUDIENCES))
    if include_source is None:
        include_source = audience == "developer" and view != "overview"
    if view == "overview":
        if targets is not None:
            raise InputError("总览不指定目标；详细查询请使用 layers、objects 或 combined", field="targets")
        if include_source:
            raise InputError("TOML 原文请通过详细查询读取", field="include_source")
    elif targets is None:
        raise InputError("详细查询需要一个目标或目标列表；使用 overview 查看总览", field="targets")
    catalog = _Catalog(config_root, include_source, audience)
    kind = "object" if view == "objects" else "layer"
    requests = catalog.loader.refs("layer") if view == "overview" else [targets] if isinstance(targets, str) else list(targets)
    items, seen = [], set()
    for target in requests:
        try:
            ref = catalog.resolve(target, kind)
        except (OSError, ValueError, TypeError) as error:
            catalog.issue(str(target), kind, error, resolved=False)
            items.append({"target": str(target), "kind": kind, "status": "unavailable"})
            continue
        if ref not in seen:
            seen.add(ref)
            items.append(catalog.entry(ref, kind, detail=view != "overview", target=target))
    result = {"view": view, "audience": audience, "items": items}
    if view == "combined":
        refs = dict.fromkeys(obj["config_ref"] for item in items for obj in item.get("accepted_objects", []))
        result["object_details"] = [catalog.entry(ref, "object", detail=True) for ref in refs]
    if view != "overview":
        kinds = {item["kind"] for item in [*items, *result.get("object_details", [])]}
        result["io"] = io_help(kinds)
    issues = prepare_diagnostics(catalog.issues, config_root=config_root, policy=catalog.policy)
    result.update(status="partial" if issues or any(item["status"] != "loaded" for item in items) else "completed",
                  issues=report(issues)["issues"])
    return _json_value(result)

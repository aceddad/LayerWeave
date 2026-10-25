"""独立的汇报等级与同因合并；不控制规则执行，不保存历史状态。"""

from copy import deepcopy
import json
from pathlib import Path
import tomllib

from layerweave.support.configuration.loader import DEFAULT_ROOT
from .serialization import binary_json_default


LEVELS = {"none": 0, "warn": 1, "error": 2}
CONFIG_FAILURES = {"config_not_found", "config_unreadable", "config_invalid"}


class DiagnosticPolicy:
    """检查汇报与配置 help 共用等级解析；不伪造问题来查询等级。"""

    def __init__(self, config_root=DEFAULT_ROOT):
        self.root = Path(config_root).resolve()
        self.settings, self.issue = {}, None
        try:
            with (self.root / "logging" / "diagnostics.toml").open("rb") as file:
                self.settings = tomllib.load(file)
            if not isinstance(self.settings.get("levels", {}), dict) or not isinstance(self.settings.get("overrides", {}), dict):
                raise ValueError("levels 和 overrides 应为表")
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            self.settings = {}
            self.issue = str(error.strerror) if isinstance(error, OSError) else str(error)

    def ref(self, ref):
        path = (self.root / ref).resolve()
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def level(self, code, *, config_ref=None, field=None):
        level = self.settings.get("levels", {}).get(code, "warn")
        ref = self.ref(config_ref) if config_ref else None
        if ref:
            overrides = self.settings.get("overrides", {}).get(ref, {})
            if isinstance(overrides, dict) and code in overrides:
                override = overrides[code]
                level = override.get(field, level) if isinstance(override, dict) else override
        if not isinstance(level, str) or level not in LEVELS:
            self.issue = f"{code} 的汇报等级应为 error、warn 或 none，实际为 {level!r}；使用 warn"
            level = "warn"
        return level

    def issues(self):
        return [{"severity": "warn", "code": "diagnostics_config", "rule": "diagnostics",
                 "field": "logging/diagnostics.toml", "message": f"汇报配置不可用：{self.issue}"}] if self.issue else []

    def describe(self, code, *, config_ref):
        """展示某个问题代码的默认等级及字段覆盖，不假定检查只会报告某一个字段。"""
        ref = self.ref(config_ref)
        overrides = self.settings.get("overrides", {}).get(ref, {})
        fields = overrides.get(code, {}) if isinstance(overrides, dict) else {}
        return {"default": self.level(code, config_ref=ref),
                "fields": {field: self.level(code, config_ref=ref, field=field) for field in fields} if isinstance(fields, dict) else {}}


def prepare_diagnostics(issues, *, config_root=DEFAULT_ROOT, policy=None):
    policy = policy or DiagnosticPolicy(config_root)
    result = []
    for original in issues:
        item = deepcopy(original)
        if item.get("config_ref"):
            item["config_ref"] = policy.ref(item["config_ref"])
        item["severity"] = policy.level(item.get("code", item.get("rule", "")),
                                        config_ref=item.get("config_ref"), field=item.get("field"))
        result.append(item)
    result.extend(policy.issues())

    merged = {}
    for item in result:
        if item.get("code") not in CONFIG_FAILURES:
            key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=binary_json_default)
        else:
            key = json.dumps([item.get("target"), item["code"], item.get("value")], sort_keys=True, default=binary_json_default)
        if key not in merged:
            merged[key] = item
            continue
        old = merged[key]
        if item.get("code") in CONFIG_FAILURES:
            checks = old.setdefault("affected_checks", [
                {"rule": old["rule"], "target": old.get("checked_target", old["target"])}])
            check = {"rule": item["rule"], "target": item.get("checked_target", item["target"])}
            if check not in checks:
                checks.append(check)
            old["severity"] = max((old["severity"], item["severity"]), key=LEVELS.get)
            old["skipped"] = old.get("skipped", False) or item.get("skipped", False)
    return list(merged.values())

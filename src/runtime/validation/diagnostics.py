"""独立的汇报等级与同因合并；不控制规则执行，不保存历史状态。"""

from copy import deepcopy
import json
from pathlib import Path
import tomllib

from ..configuration.loader import DEFAULT_ROOT


LEVELS = {"none": 0, "warn": 1, "error": 2}
CONFIG_FAILURES = {"config_not_found", "config_unreadable", "config_invalid"}


def prepare_diagnostics(issues, *, config_root=DEFAULT_ROOT):
    root = Path(config_root).resolve()
    policy, policy_issue = {}, None
    try:
        with (root / "logging" / "diagnostics.toml").open("rb") as file:
            policy = tomllib.load(file)
        if not isinstance(policy.get("levels", {}), dict) or not isinstance(policy.get("overrides", {}), dict):
            raise ValueError("levels 和 overrides 应为表")
    except FileNotFoundError:
        pass  # 忘记提供汇报配置时，各项默认 warn；不制造额外缺文件提示。
    except (OSError, ValueError) as error:
        policy = {}
        policy_issue = str(error.strerror) if isinstance(error, OSError) else str(error)

    result = []
    for original in issues:
        item = deepcopy(original)
        code = item.get("code", item.get("rule", ""))
        level = policy.get("levels", {}).get(code, "warn")
        ref = item.get("config_ref")
        if ref:
            path = (root / ref).resolve()
            try:
                ref = path.relative_to(root).as_posix()
            except ValueError:
                ref = str(path)
            item["config_ref"] = ref
            overrides = policy.get("overrides", {}).get(ref, {})
            if isinstance(overrides, dict) and code in overrides:
                override = overrides[code]
                level = override.get(item.get("field"), level) if isinstance(override, dict) else override
        if not isinstance(level, str) or level not in LEVELS:
            policy_issue = f"{code} 的汇报等级应为 error、warn 或 none，实际为 {level!r}；使用 warn"
            level = "warn"
        item["severity"] = level
        result.append(item)
    if policy_issue:
        result.append({"severity": "warn", "code": "diagnostics_config", "rule": "diagnostics",
                       "field": "logging/diagnostics.toml", "message": f"汇报配置不可用：{policy_issue}"})

    merged = {}
    for item in result:
        if item.get("code") not in CONFIG_FAILURES:
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        else:
            key = json.dumps([item.get("target"), item["code"], item.get("value")], sort_keys=True)
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

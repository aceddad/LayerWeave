"""从变更选择规则；按最终记录检查，规则失败只影响当前一项。"""

from importlib import import_module
import json
from layerweave.core.identity import identity_key

from layerweave.support.configuration.loader import ConfigError, DEFAULT_ROOT, Loader
from layerweave.support.values import same_value
from layerweave.support.feedback import target as make_target
from layerweave.support.positions import PositionMath
from layerweave.support.channel import report
from layerweave.tool.builtin.usage.validation.registry import RULES
from layerweave.tool.builtin.usage.validation.declarations import spelling_hints
from layerweave.support.diagnostics import prepare_diagnostics


def _identity(kind, record):
    return identity_key(kind, record.get("project_id"), record["id"])


def _read(read_record, key):
    kind, project_id, entity_id = key
    return read_record(kind, project_id=project_id, id=entity_id)


def _related(change, scope, read_record):
    kind, before, after = change["kind"], change["before"], change["after"]
    if scope == "self":
        return [(kind, after)] if after else []
    if scope == "layer":
        if kind == "layer":
            return [(kind, after)] if after else []
        layers = {item["layer"] for item in (before, after) if item is not None and item["layer"] is not None}
        project_id = (after or before)["project_id"]
        return [("layer", row) for layer_id in sorted(layers)
                if (row := read_record("layer", project_id=project_id, id=layer_id)) is not None]
    if scope == "binds":
        if kind == "bind":
            return [(kind, after)] if after else []
        if after is not None and not change.get("force"):
            return []
        record = after or before
        rows = {}
        for side in ("source", "target"):
            filters = {f"{side}_kind": kind, f"{side}_project_id": record["project_id"], f"{side}_id": record["id"]}
            rows.update((row["id"], row) for row in read_record("bind", filters=filters))
        return [("bind", row) for row in rows.values()]
    raise ValueError(f"未实现的检查范围：{scope}")


def _collect(changes, read_record):
    changes = list(changes)
    affected_layers, position_checks = set(), []
    for change in changes:
        before, after = change["before"], change["after"]
        if change["kind"] != "layer" or not before or not after or change.get("force"):
            continue
        if all(same_value(before[name], after[name]) for name in ("axis", "father")):
            continue
        pending = [after]
        while pending:
            layer = pending.pop()
            key = (layer["project_id"], layer["id"])
            if key in affected_layers:
                continue
            affected_layers.add(key)
            for obj in read_record("object", project_id=key[0], filters={"layer": key[1]}):
                position_checks.append({"kind": "object", "before": obj, "after": obj,
                                        "force": True, "position_only": True})
            pending.extend(read_record("layer", project_id=key[0], filters={"father": key[1]}))
    jobs = {}
    for change in [*changes, *position_checks]:
        before, after, kind = change["before"], change["after"], change["kind"]
        changed = {key for key in (before or {}).keys() | (after or {}).keys()
                   if not same_value((before or {}).get(key), (after or {}).get(key))}
        for rule, spec in RULES.items():
            if change.get("position_only") and rule not in {"begin_le_end", "duration", "overlap"}:
                continue
            if kind not in spec["triggers"]:
                continue
            fields = spec["triggers"][kind]
            if not (change.get("force") or before is None or after is None or "config_ref" in changed
                    or fields is None or changed.intersection(fields)):
                continue
            for target_kind, record in _related(change, spec["scope"], read_record):
                selected = None if change.get("force") or before is None or "config_ref" in changed else changed
                jobs[(_identity(target_kind, record), rule)] = (record, selected)
    return jobs


def _execute(jobs, read_record, loader, modified=None):
    issues, configs, invalid_configs, prepared = [], {}, set(), set()
    references = {key: row.get("config_ref") for (key, rule), (row, changed) in jobs.items()}
    positions = {}

    def add(key, rule, message, **extra):
        kind, project_id, entity_id = key
        checked = make_target(kind, project_id, entity_id)
        issue = {"rule": rule, "target": checked, "message": message, **extra}
        actual = issue["target"]
        identity = identity_key(actual["kind"], actual.get("project_id"), actual["id"])
        if identity not in references and actual["kind"] in {"layer", "object"}:
            references[identity] = (_read(read_record, identity) or {}).get("config_ref")
        if references.get(identity):
            issue["config_ref"] = references[identity]
        issue["scope"] = "manual" if modified is None else "direct" if identity in modified else "related"
        if actual != checked:
            issue["checked_target"] = checked
        issues.append(issue)

    for (key, rule), (record, changed_fields) in jobs.items():
        spec = RULES[rule]
        kind = key[0]
        config = {}
        if spec.get("config", True):
            if key not in prepared:
                prepared.add(key)
                try:
                    configs[key] = loader.load(record["config_ref"], kind)
                except Exception as error:
                    invalid_configs.add(key)
                    add(key, "configuration", f"配置不可用，依赖它的检查未完成：{error}", skipped=True,
                        **{"field": "config_ref", **getattr(error, "details", {})})
                    # 基础约定独立可读时仍可检查，不冒充已检查缺失的派生约定。
                    try:
                        configs[key] = loader.load(f"{kind}s/base.toml", kind)
                    except ConfigError:
                        configs[key] = {}
                if key not in invalid_configs:
                    for hint in spelling_hints(loader, configs[key], kind):
                        detail = dict(hint)
                        add(key, "configuration", detail.pop("message"), **detail)
                    known = {entry["setting"] for entry in RULES.values() if "setting" in entry
                             and (kind in entry["triggers"] if entry["scope"] == "self"
                                  else kind == ("layer" if entry["scope"] == "layer" else "bind"))}
                    for section in ("rules", "constraint", "options"):
                        for name in configs[key].get(section, {}):
                            if section == "rules" and configs[key][section][name] is False:
                                continue
                            if (section, name) not in known:
                                add(key, "configuration", f"尚未实现的检测声明：{section}.{name}", skipped=True)
            if key in invalid_configs and rule not in {"fields", "no_cycle", "begin_le_end"}:
                continue
            config = configs[key]
            if not config:
                continue
            if "setting" in spec:
                section, name = spec["setting"]
                value = config.get(section, {}).get(name)
                if value is None:
                    continue
                if "values" in spec:
                    if value not in spec["values"]:
                        add(key, rule, f"未实现的参数：{section}.{name}={value!r}", skipped=True)
                        continue
                    if value == spec.get("disabled"):
                        continue
                elif type(value) is not bool:
                    add(key, rule, f"{section}.{name} 应为布尔值", skipped=True)
                    continue
                elif value != spec.get("enabled", True):
                    continue
        try:
            module, name = spec["function"].split(":", 1)
            function = getattr(import_module(module), name)
            project_id = record.get("project_id")
            if project_id not in positions:
                positions[project_id] = PositionMath(read_record, project_id)
            found = function(record, {**config, "_loader": loader, "_changed_fields": changed_fields,
                                      "_positions": positions[project_id]}, read_record)
            if not isinstance(found, list) or any(not isinstance(item, dict) for item in found):
                raise TypeError("规则应返回问题字典列表")
            json.dumps(found, ensure_ascii=False, allow_nan=False)
            for item in found:
                detail = dict(item)
                message = detail.pop("message")
                add(key, rule, message, **detail)
        except Exception as error:
            add(key, rule, f"本项检查未完成：{type(error).__name__}: {error}", code="check_failed", skipped=True)
    # 同一关联或问题可能从多个受影响目标到达，保留一次。
    unique = {}
    for item in issues:
        unique[json.dumps(item, ensure_ascii=False, sort_keys=True)] = item
    return list(unique.values())


def check_changes(changes, read_record, *, config_root=DEFAULT_ROOT):
    """兼容 checker(changes, read_record)；每次调用重新读取配置。"""
    merged = {}
    for change in changes:
        key = identity_key(change["kind"], change["project_id"], change["id"])
        if key not in merged:
            merged[key] = dict(change)
    final = []
    for key, change in merged.items():
        change["after"] = _read(read_record, key)
        if not same_value(change["before"], change["after"]):
            final.append(change)
    return prepare_diagnostics(_execute(_collect(final, read_record), read_record, Loader(config_root), modified=set(merged)),
                               config_root=config_root)


def validate(targets, read_record, *, config_root=DEFAULT_ROOT):
    """主动复查，不写日志。层含直接装载对象；项目含层、对象及两端关联。"""
    changes, missing = {}, []

    def include(kind, row):
        key = _identity(kind, row)
        changes[key] = {"kind": kind, "before": row, "after": row, "force": True}

    for target in targets:
        kind = target["kind"]
        key = identity_key(kind, target.get("project_id"), target["id"])
        row = _read(read_record, key)
        if row is None:
            missing.append({"rule": "target", "target": target,
                            "message": "指定目标不存在，未进行复查", "skipped": True, "scope": "manual"})
            continue
        include(kind, row)
        if kind == "layer":
            for obj in read_record("object", project_id=row["project_id"], filters={"layer": row["id"]}):
                include("object", obj)
        elif kind == "project":
            for entity_kind in ("layer", "object"):
                for entity in read_record(entity_kind, project_id=row["id"]):
                    include(entity_kind, entity)
            for side in ("source", "target"):
                for bind in read_record("bind", filters={f"{side}_project_id": row["id"]}):
                    include("bind", bind)
    return report(prepare_diagnostics([*missing, *_execute(_collect(changes.values(), read_record), read_record, Loader(config_root))],
                                      config_root=config_root))

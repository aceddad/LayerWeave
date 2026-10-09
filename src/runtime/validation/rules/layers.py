"""层关系、对象兼容与占用规则，读取关联数据但不修改记录。"""

from ...configuration.loader import ConfigError
from .fields import problem
from ...positions import interval_ticks


def layer_type(record, config, read_record):
    if record["type"] != config["type"]:
        return [problem(f"存储 type={record['type']!r} 与配置 type={config['type']!r} 不一致",
                        field="type")]
    return []


def no_cycle(record, config, read_record):
    seen = set()
    current = record
    while current is not None:
        if current["id"] in seen:
            return [problem("father 链成环", field="father")]
        seen.add(current["id"])
        father = current["father"]
        if father is None:
            return []
        current = read_record("layer", project_id=record["project_id"], id=father)
        if current is None:
            return [problem(f"父层 {father} 不存在，无法继续检查父链", field="father", skipped=True)]
    return []


def axis_only_on_root(record, config, read_record):
    if record["father"] is not None and record["axis"] is not None:
        return [problem("当前配置仅允许根层声明 axis", field="axis")]
    return []


def accepts_objects(record, config, read_record):
    loader = config["_loader"]
    try:
        expected = loader.object_config(config["objects"])
    except (ConfigError, KeyError) as error:
        return [problem(f"无法确定层接受的对象配置：{error}", skipped=True,
                        **{"field": "config_ref", **getattr(error, "details", {})})]
    issues = []
    for obj in read_record("object", project_id=record["project_id"], filters={"layer": record["id"]}):
        target = {"kind": "object", "project_id": obj["project_id"], "id": obj["id"]}
        try:
            actual = loader.load(obj["config_ref"], "object")
        except ConfigError as error:
            issues.append(problem(f"无法判断对象兼容性：{error}", target=target, skipped=True,
                                  **{"field": "config_ref", **getattr(error, "details", {})}))
            continue
        if expected["_ref"] not in actual["_lineage"]:
            issues.append(problem(f"层接受 {expected['type']} 及其派生配置，当前对象为 {actual['type']}",
                                  target=target, field="config_ref"))
    return issues


def _overlaps(left, right):
    a, b, c, d = left["begin"], left["end"], right["begin"], right["end"]
    if a == b:
        return a == c if c == d else c <= a < d
    if c == d:
        return a <= c < b
    return a < d and c < b


def overlap(record, config, read_record):
    issues, active = [], []
    objects = read_record("object", project_id=record["project_id"], filters={"layer": record["id"]})
    valid = []
    for obj in objects:
        span = interval_ticks(obj, read_record, config.get("_positions"))
        if span is not None and span[0] <= span[1]:
            valid.append({**obj, "begin": span[0], "end": span[1]})
        else:
            issues.append(problem("对象起止位置无效，未参与重叠比较", code="position_invalid", skipped=True,
                                  target={"kind": "object", "project_id": obj["project_id"], "id": obj["id"]}))
    for obj in sorted(valid, key=lambda item: (item["begin"], item["end"], item["id"])):
        # 持续对象不占结束点；瞬间对象在同一坐标仍须参与比较。
        active = [other for other in active if other["end"] > obj["begin"]
                  or other["begin"] == other["end"] == obj["begin"]]
        for other in active:
            if _overlaps(other, obj):
                issues.append(problem(f"对象 {other['id']} 与 {obj['id']} 占用重叠", related=[
                    {"kind": "object", "project_id": record["project_id"], "id": value}
                    for value in sorted((other["id"], obj["id"]))]))
        active.append(obj)
    return issues

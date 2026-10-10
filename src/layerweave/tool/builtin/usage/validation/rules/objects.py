"""对象区间约定；负位置和瞬间都可使用。"""

from layerweave.tool.builtin.usage.validation.rules.fields import problem
from layerweave.support.positions import interval_ticks


def begin_le_end(record, config, read_record):
    span = interval_ticks(record, read_record, config.get("_positions"))
    if span is None:
        return [problem("起止位置类型无效，未检查先后顺序", code="position_invalid", skipped=True)]
    return [] if span[0] <= span[1] else [problem("begin 不能晚于 end", field="end")]


def duration(record, config, read_record):
    span = interval_ticks(record, read_record, config.get("_positions"))
    if span is None or span[0] > span[1]:
        return [problem("起止位置无效，未检查时长约定", code="position_invalid", skipped=True)]
    value = span[1] - span[0]
    expected = config["constraint"]["duration"]
    valid = value > 0 if expected == "positive" else value == 0
    return [] if valid else [problem(f"时长应满足 {expected}，实际占用 {value} 个刻度", field="end")]

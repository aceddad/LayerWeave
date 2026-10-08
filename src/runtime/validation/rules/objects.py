"""对象区间约定；负位置和瞬间都可使用。"""

from .fields import interval, matches, problem


def begin_le_end(record, config, read_record):
    if not all(matches(record[name], "float") for name in ("begin", "end")):
        return [problem("起止位置类型无效，未检查先后顺序", severity="warn", skipped=True)]
    return [] if record["begin"] <= record["end"] else [problem("begin 不能晚于 end", field="end")]


def duration(record, config, read_record):
    if not interval(record):
        return [problem("起止位置无效，未检查时长约定", severity="warn", skipped=True)]
    value = record["end"] - record["begin"]
    expected = config["constraint"]["duration"]
    valid = value > 0 if expected == "positive" else value == 0
    return [] if valid else [problem(f"时长应满足 {expected}，实际为 {value}", field="end")]

"""空档查询：合并已有占用区间，只做数值计算，不修改或解释内容。"""

from math import isfinite

from support.api import decimal_value, read_layer_positions


def _number(value, label):
    if type(value) not in {int, float} or not isfinite(value):
        raise ValueError(f"{label} 必须是有限数值")
    return value


def find_gaps(connection, project_id, layer_id, *, begin, end, min_length=0):
    """查询直属层在 [begin,end) 内的空档；瞬间对象占点，以开起点明确排除。"""
    _number(begin, "begin")
    _number(end, "end")
    minimum = decimal_value(_number(min_length, "min_length"))
    if begin > end or minimum < 0:
        raise ValueError("需要 begin <= end 且 min_length >= 0")
    data = read_layer_positions(connection, project_id, layer_id)
    if data is None:
        raise ValueError(f"层 ({project_id}, {layer_id}) 不存在")
    occupied = []
    for obj in data["objects"]:
        label = f"对象 ({data['project_id']}, {obj['id']})"
        b, e = _number(obj["begin"], f"{label} 的 begin"), _number(obj["end"], f"{label} 的 end")
        if b > e:
            raise ValueError(f"{label} 的 begin 晚于 end，无法确定空档；可使用 recheck 复查")
        if (b == e and begin <= b < end) or (b < e and e > begin and b < end):
            occupied.append((max(begin, b), min(end, e)))
    gaps = []

    def append(b, e, inclusive):
        length = decimal_value(e) - decimal_value(b)
        # 开起点不允许直接放入恰好占满区间的对象；不虚构一个 epsilon 起点。
        if b < e and (length > minimum or (length == minimum and inclusive)):
            gaps.append({"begin": b, "end": e, "length": float(length), "begin_inclusive": inclusive})

    cursor, inclusive = begin, True
    for b, e in sorted(occupied):
        if b > cursor:
            append(cursor, b, inclusive)
        if b == e:
            if b >= cursor:
                cursor, inclusive = b, False
        elif e > cursor:
            cursor, inclusive = e, True
    append(cursor, end, inclusive)
    return {"project_id": data["project_id"], "layer_id": data["layer_id"],
            "scope": {"begin": begin, "end": end, "min_length": min_length},
            "gaps": gaps, "count": len(gaps)}


def format_gaps(result):
    lines = [f"项目 {result['project_id']} · 层 {result['layer_id']} · {result['count']} 个空档"]
    for gap in result["gaps"]:
        bracket = "[" if gap["begin_inclusive"] else "("
        lines.append(f"  {bracket}{gap['begin']}, {gap['end']}) · 长度 {gap['length']}")
    return "\n".join(lines)


def main():
    from support.cli import parser_for, run_cli
    parser = parser_for("LayerWeave 空档查询：指定直属层与有限区间，只读", commands=COMMANDS)
    parser.add_argument("layer_id", type=int, help="只查询此层直属对象，不包括子层")
    parser.add_argument("begin", type=float, help="查询起点，包含")
    parser.add_argument("end", type=float, help="查询终点，不包含")
    parser.add_argument("--min-length", type=float, default=0, help="至少容纳的长度，默认返回全部正长度空档")
    return run_cli(parser, lambda connection, args: find_gaps(connection, args.project_id, args.layer_id,
                   begin=args.begin, end=args.end, min_length=args.min_length), formatter=format_gaps)


COMMANDS = [{'name': 'find_gaps',
  'summary': '查询直属层在指定区间内的空档，可按最小可容纳长度筛选',
  'entrypoint': 'tool.builtin.usage.query.free_ranges:find_gaps',
  'cli': 'python -m tool.builtin.usage.query.free_ranges',
  'read_only': True,
  'context': ['database', 'project_id'],
  'parameters': {'layer_id': {'type': 'integer', 'required': True, 'description': '只查询此层直属对象，不包含子层'},
                 'begin': {'type': 'number', 'required': True, 'description': '查询区间起点，包含'},
                 'end': {'type': 'number', 'required': True, 'description': '查询区间终点，不包含；不得早于 begin'},
                 'min_length': {'type': 'number', 'default': 0, 'description': '最小可容纳长度，非负；0 返回全部正长度空档'}},
  'returns': 'project_id、layer_id、scope、count、gaps；每段含 begin/end/length/begin_inclusive，终点始终不包含。',
  'examples': [{'cli': 'python -m tool.builtin.usage.query.free_ranges DATABASE 1 4 0 20 --min-length 3 --json'}],
  'notes': ['合并相交或首尾相接的占用，空层返回整个查询区间。数值不换算、不落点、不加载配置或正文。',
            '瞬间对象占用一个点，其后的空档 begin_inclusive=false；不猜测 epsilon。开起点的空档不能容纳等于其长度的对象。',
            '位置不是有限数值或 begin>end 时明确指出对象，查询失败，不将无法判断的区域报告为空闲。']}]


if __name__ == "__main__":
    raise SystemExit(main())

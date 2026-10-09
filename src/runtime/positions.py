"""写入、工具和检查共用的十进制计算与轴精度落点，不做单位或帧率换算。"""

from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from math import isfinite


DEFAULT_PRECISION = 1e-6


def numeric_position(value):
    return type(value) in {int, float} and isfinite(value)


def decimal_value(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


class PositionMath:
    """一次操作内复用轴查找；最近的显式 axis 定义当前轴，默认沿父链到根。"""

    def __init__(self, read_record, project_id):
        self.read = read_record
        self.project_id = project_id
        self.cache = {}

    def precision(self, layer_id):
        current, path, seen = layer_id, [], set()
        precision = DEFAULT_PRECISION
        while current is not None:
            if current in self.cache:
                precision = self.cache[current]
                break
            layer = self.read("layer", project_id=self.project_id, id=current)
            if layer is None:
                raise KeyError(f"无法取得轴：层 ({self.project_id}, {current}) 不存在")
            current = layer["id"]
            if current in seen:
                break  # 已遍历完整环且未找到显式轴，使用默认刻度；环由 no_cycle 诊断。
            seen.add(current)
            path.append(current)
            axis = layer["axis"]
            if axis is not None:
                if not isinstance(axis, dict):
                    raise ValueError(f"层 ({self.project_id}, {current}) 的 axis 不是字典")
                precision = axis.get("precision")
                if precision is None:
                    precision = DEFAULT_PRECISION
                if precision is not None and (type(precision) not in {int, float} or not isfinite(precision) or precision <= 0):
                    raise ValueError(f"层 ({self.project_id}, {current}) 的 precision 应为正的有限数值")
                break  # 自有轴没有 precision 时使用默认步长，不借用另一轴。
            current = layer["father"]
        for id in path:
            self.cache[id] = precision
        self.cache[layer_id] = precision
        return precision

    def ticks(self, layer_id, value):
        value = decimal_value(value)
        quantum = decimal_value(self.precision(layer_id))
        return int((value / quantum).to_integral_value(rounding=ROUND_HALF_UP))

    def snap(self, layer_id, value):
        step = self.precision(layer_id)
        ticks = self.ticks(layer_id, value)
        snapped = float(Fraction(step) * ticks)
        places = max(0, -decimal_value(step).as_tuple().exponent)
        return round(snapped, places)


def interval_ticks(record, read_record, math=None):
    if not all(numeric_position(record[name]) for name in ("begin", "end")):
        return None
    math = math or PositionMath(read_record, record["project_id"])
    return math.ticks(record["layer"], record["begin"]), math.ticks(record["layer"], record["end"])

"""位置工具共用的十进制计算与轴精度落点，不做单位或帧率换算。"""

from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from math import isfinite


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
        precision = None
        while current is not None:
            if current in self.cache:
                precision = self.cache[current]
                break
            layer = self.read("layer", project_id=self.project_id, id=current)
            if layer is None:
                raise KeyError(f"无法取得轴：层 ({self.project_id}, {current}) 不存在")
            current = layer["id"]
            if current in seen:
                raise ValueError(f"无法取得轴：层 ({self.project_id}, {layer_id}) 的父链成环")
            seen.add(current)
            path.append(current)
            axis = layer["axis"]
            if axis is not None:
                if not isinstance(axis, dict):
                    raise ValueError(f"层 ({self.project_id}, {current}) 的 axis 不是字典")
                precision = axis.get("precision")
                if precision is not None and (type(precision) not in {int, float} or not isfinite(precision) or precision <= 0):
                    raise ValueError(f"层 ({self.project_id}, {current}) 的 precision 应为正的有限数值")
                break  # 自有轴没有 precision 时，也不借用另一轴的精度。
            current = layer["father"]
        for id in path:
            self.cache[id] = precision
        self.cache[layer_id] = precision
        return precision

    def snap(self, layer_id, value):
        value = decimal_value(value)
        step = self.precision(layer_id)
        if step is None:
            return float(value)
        quantum = decimal_value(step)
        ticks = (value / quantum).to_integral_value(rounding=ROUND_HALF_UP)
        # 使用实际数值步长的整数倍，支持 1/30 这类浮点步长；最后清除十进制步长的二进制尾差。
        snapped = float(Fraction(step) * int(ticks))
        places = max(0, -quantum.as_tuple().exponent)
        return round(snapped, places)

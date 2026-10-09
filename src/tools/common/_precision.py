"""兼容旧工具导入位置；数值实现统一位于 runtime.positions。"""

from runtime.api import PositionMath, decimal_value

__all__ = ["PositionMath", "decimal_value"]

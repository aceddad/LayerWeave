from dataclasses import dataclass, field

from ..objects.base import Object


@dataclass
class Layer:
    """层的基础类：组织上下文并装载对象。"""

    id: int | None = None
    name: str = ""  # 创建时传入的实例名字。
    father: int | None = None
    axis: dict | None = None
    tips: str = ""
    bind: list = field(default_factory=list)
    objects: list[Object] = field(default_factory=list)

    def return_self(self):
        """返回当前实例。"""
        return self

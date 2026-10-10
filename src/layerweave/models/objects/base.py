from dataclasses import dataclass, field


@dataclass
class Object:
    """对象的基础类：承载内容及其在轴上的位置。"""

    id: int | None = None
    name: str = ""
    layer: int = field(kw_only=True)  # 必传；实际归属关系由保存数据的外键保证。
    begin: float = 0.0
    end: float = 0.0
    information: dict = field(default_factory=dict)
    tips: str = ""
    bind: list = field(default_factory=list)

    def return_self(self):
        """返回当前实例。"""
        return self

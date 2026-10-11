"""开发者发号接口。词条随数据库保存，函数规则由当前运行环境提供。"""
from .registry import register_numbering, numbering_entries
from .service import allocate, increment, register_numbering_rule

__all__ = ["allocate", "increment", "register_numbering", "numbering_entries", "register_numbering_rule"]

"""配置与解码后记录共用的值比较，保留 Python/JSON 中的值类型。"""


def same_value(left, right):
    """忽略字典键顺序，保留列表顺序；True、1、1.0 是不同的值表示。"""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same_value(value, right[key]) for key, value in left.items())
    if isinstance(left, list):
        return len(left) == len(right) and all(same_value(a, b) for a, b in zip(left, right))
    return left == right

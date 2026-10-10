"""概览与详细展开共用的迭代排列；原始 father 保留，不重新定义数据层级。"""

from collections import defaultdict


def order_layers(layers, root_id=None, *, root_ids=None):
    children = defaultdict(list)
    for layer in layers:
        children[layer["father"]].append(layer)
    if root_ids is not None:
        by_id = {layer["id"]: layer for layer in layers}
        roots = [by_id[id] for id in root_ids if id in by_id]
    else:
        roots = children[None] if root_id is None else [layer for layer in layers if layer["id"] == root_id]
    pending = [(layer, 0) for layer in reversed(roots)]
    ordered, placed = [], set()
    while pending:
        layer, depth = pending.pop()
        if layer["id"] in placed:
            continue
        placed.add(layer["id"])
        ordered.append({**layer, "depth": depth})
        pending.extend((child, depth + 1) for child in reversed(children[layer["id"]]))
    return ordered + [{**layer, "depth": None} for layer in layers if layer["id"] not in placed]

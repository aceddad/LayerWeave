"""按步数广度展开标准 bind；返回节点与边，展示含义由调用方解释。"""
from collections import deque

from layerweave.support.api import read_bindings, read_record, read_snapshot


def walk_relations(connection, project_id, kind, id, *, direction="outgoing", max_depth=3,
                   max_nodes=100, max_edges=300):
    """包含起点；完整身份去重，重复节点不再扩展；深度外不查询，数量截断明确返回。"""
    if kind not in {"layer", "object"}:
        raise ValueError("起点 kind 应为 layer 或 object")
    if direction not in {"outgoing", "incoming", "both"}:
        raise ValueError("direction 应为 outgoing、incoming 或 both")
    for name, value, minimum in (("max_depth", max_depth, 0), ("max_nodes", max_nodes, 1), ("max_edges", max_edges, 1)):
        if type(value) is not int or value < minimum:
            raise ValueError(f"{name} 应为不小于 {minimum} 的整数")
    if project_id is None or id is None:
        raise ValueError("起点需要明确的 project_id 和 id")
    start = (kind, project_id, id)
    nodes, edges, reasons = {}, {}, set()
    pending = deque()

    def add_node(identity, depth):
        node_kind, owner, number = identity
        row = read_record(connection, node_kind, project_id=owner, id=number) if node_kind in {"layer", "object"} else None
        status = "found" if row is not None else "missing" if node_kind in {"layer", "object"} else "unsupported_kind"
        nodes[identity] = {"kind": node_kind, "project_id": owner, "id": number,
                           "depth": depth, "status": status, "record": row}
        pending.append(identity)

    with read_snapshot(connection):
        add_node(start, 0)
        while pending:
            current = pending.popleft()
            node = nodes[current]
            if node["depth"] >= max_depth or node["status"] == "unsupported_kind":
                continue
            for edge in read_bindings(connection, current[0], current[1], current[2], direction=direction):
                if edge["id"] in edges:
                    continue
                if len(edges) >= max_edges:
                    reasons.add("max_edges")
                    pending.clear()
                    break
                source = tuple(edge[f"source_{field}"] for field in ("kind", "project_id", "id"))
                destination = tuple(edge[f"target_{field}"] for field in ("kind", "project_id", "id"))
                other = destination if source == current else source
                if other not in nodes:
                    if len(nodes) >= max_nodes:
                        reasons.add("max_nodes")
                        continue
                    add_node(other, node["depth"] + 1)
                edges[edge["id"]] = edge
    return {"scope": {"kind": kind, "project_id": project_id, "id": id, "direction": direction,
                       "max_depth": max_depth, "max_nodes": max_nodes, "max_edges": max_edges},
            "nodes": list(nodes.values()), "edges": list(edges.values()),
            "truncated": bool(reasons), "truncation_reasons": sorted(reasons)}


def main():
    from layerweave.support.cli import parser_for, run_cli

    parser = parser_for("LayerWeave 沿标准关联展开节点与内容", commands=COMMANDS)
    parser.add_argument("kind", choices=("layer", "object"))
    parser.add_argument("id", type=int)
    parser.add_argument("--direction", choices=("outgoing", "incoming", "both"), default="outgoing")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=100)
    parser.add_argument("--max-edges", type=int, default=300)
    return run_cli(parser, lambda connection, args: walk_relations(
        connection, args.project_id, args.kind, args.id, direction=args.direction, max_depth=args.max_depth,
        max_nodes=args.max_nodes, max_edges=args.max_edges))


COMMANDS = [{
    "name": "walk_relations", "summary": "从实体出发按步数展开关联，读取相关节点内容",
    "entrypoint": "layerweave.tool.builtin.usage.query.walk:walk_relations",
    "cli": "python -m layerweave.tool.builtin.usage.query.walk", "read_only": True,
    "context": ["database", "project_id"],
    "parameters": {
        "kind": {"type": "string", "required": True, "choices": ["layer", "object"], "description": "起点种类"},
        "id": {"type": "integer", "required": True, "description": "起点的项目内编号"},
        "direction": {"type": "string", "default": "outgoing", "choices": ["outgoing", "incoming", "both"]},
        "max_depth": {"type": "integer", "default": 3, "description": "最大步数，0 只读取起点"},
        "max_nodes": {"type": "integer", "default": 100, "description": "最大节点数，包含起点"},
        "max_edges": {"type": "integer", "default": 300, "description": "最大关联数"},
    },
    "returns": "scope、nodes、edges、truncated、truncation_reasons；节点含完整身份、最短步数、状态和原始 record。",
    "examples": [{"cli": "python -m layerweave.tool.builtin.usage.query.walk DATABASE 1 object 8 --max-depth 3 --direction both"}],
    "notes": ["按完整身份去重，保留环边；失效引用保留节点，record=null。",
              "只走标准 bind，不解释其他工具表中的关联；摘要与排版由调用方决定。",
              "max_depth 是查询范围；truncated 表示数量上限令范围内结果不完整。"],
    "aliases": ["walk"],
}]


if __name__ == "__main__":
    raise SystemExit(main())

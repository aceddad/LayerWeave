"""查询实体引用谁、被谁引用；保持完整引用，不自动递归或装载目标。"""

from runtime.api import read_bindings


def query_relations(connection, project_id, kind, id, *, direction="both"):
    """返回 entity/direction/outgoing/incoming；自关联在两个方向各出现一次。"""
    rows = read_bindings(connection, kind, project_id, id, direction=direction)
    entity = {"kind": kind, "project_id": project_id, "id": id}
    result = {"entity": entity, "direction": direction, "outgoing": [], "incoming": []}
    for row in rows:
        for side, group in (("source", "outgoing"), ("target", "incoming")):
            if direction in {"both", group} and all(row[f"{side}_{field}"] == value for field, value in entity.items()):
                result[group].append(row)
    return result


def main():
    from tools._cli import parser_for, run_cli

    parser = parser_for("LayerWeave 关联查询（只读，输出 JSON）")
    parser.add_argument("kind", choices=("layer", "object"), help="实体种类")
    parser.add_argument("id", type=int, help="实体在项目内的编号")
    parser.add_argument("--direction", choices=("both", "outgoing", "incoming"), default="both")
    return run_cli(parser, lambda connection, args: query_relations(
        connection, args.project_id, args.kind, args.id, direction=args.direction,
    ))


if __name__ == "__main__":
    raise SystemExit(main())

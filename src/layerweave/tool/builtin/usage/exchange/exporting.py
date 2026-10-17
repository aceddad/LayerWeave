"""项目数据导出；层次节点与托管表声明共用同一读取快照。"""
from copy import deepcopy

from layerweave.support.api import read_record, read_project_details, read_snapshot, table_specs, numbering_entries
from .format import CORE, OPS, address, fail, fingerprint, identity, references, table_definition


def export_project(connection, project_id, *, layer_ids=None, object_ids=None, begin=None, end=None,
                   op="update", include_tools=True, include_global=False, include_baseline=False, compact=False):
    """返回交换文档；默认项目范围，global 明确选择无项目归属的全部工具记录。"""
    if op not in OPS:
        fail("导出 op 应为 add、update 或 delete", "/op", allowed=list(OPS))
    if object_ids is not None and (layer_ids is not None or begin is not None or end is not None):
        fail("object_ids 与层/时间范围互斥", "/scope")
    with read_snapshot(connection):
        specs = table_specs(connection)
        project = read_record(connection, "project", id=project_id)
        if project is None:
            fail(f"项目 {project_id} 不存在", code="target_not_found")
        whole = layer_ids is None and object_ids is None and begin is None and end is None
        selected = {}
        if object_ids is not None:
            for id in dict.fromkeys(object_ids):
                row = read_record(connection, "object", project_id=project_id, id=id)
                if row is None:
                    fail(f"对象 ({project_id}, {id}) 不存在", code="target_not_found")
                selected[("object", project_id, row["id"])] = row
        else:
            details = read_project_details(connection, project_id, layer_ids=layer_ids, begin=begin, end=end)
            if details["missing_layer_ids"]:
                fail("导出范围包含不存在的层", missing_layer_ids=details["missing_layer_ids"])
            for layer in details["layers"]:
                selected[("layer", project_id, layer["id"])] = layer
                for obj in layer["objects"]:
                    selected[("object", project_id, obj["id"])] = obj
        selected_core = set(selected)
        contexts = {key for key in selected if key[0] == "layer"} if (begin is not None or end is not None) and op != "add" else set()
        # bind 归其来源所有；复制不会擅自改动范围外指向本范围的入向关联。
        for bind in read_record(connection, "bind", filters={"source_project_id": project_id}):
            if whole or (bind["source_kind"], project_id, bind["source_id"]) in selected_core - contexts:
                selected[("bind", None, bind["id"])] = bind

        tool_kinds = sorted(set(specs) - CORE) if include_tools else []
        candidates = {}
        for kind in tool_kinds:
            spec = specs[kind]
            rows = read_record(connection, kind, **({"project_id": project_id} if spec["scoped"] else {}))
            for row in rows:
                key = identity(kind, row.get("project_id"), row["id"], specs)
                if (spec["scoped"] and whole) or (not spec["scoped"] and include_global):
                    selected[key] = row
                else:
                    candidates[key] = row
        # 工具记录若通过声明的引用接到选中记录，则随之导出；只凭 project 引用不扩大局部范围。
        while candidates:
            found = [key for key, row in candidates.items()
                     if any((target in selected and target not in contexts) or (whole and target == ("project", None, project_id))
                            for _, target, _ in references(key[0], row, specs))]
            if not found:
                break
            for key in found:
                selected[key] = candidates.pop(key)
        # 再补足选中工具记录明确引用的工具数据，例如项目批注引用的全局字典项。
        # 不从补入的共享字典反向扩散到别的项目记录。
        while candidates:
            needed = {target for key, row in selected.items()
                      for _, target, _ in references(key[0], row, specs) if target in candidates}
            if not needed:
                break
            for key in sorted(needed, key=repr):
                selected[key] = candidates.pop(key)
                if op == "delete":
                    contexts.add(key)  # 被引用的共享资料不是随项目/条目删除的从属记录。

        def node(kind, row):
            value = {"kind": kind, "op": op, "id": row["id"],
                     "data": {field: deepcopy(row[field]) for field in specs[kind]["fields"]}}
            if kind in {"layer", "object"}:
                value["parent_id"] = row["father" if kind == "layer" else "layer"]
            if include_baseline and op != "add":
                value["base"] = fingerprint(connection, kind, row, specs[kind])
            if identity(kind, row.get("project_id"), row["id"], specs) in contexts:
                value.pop("op", None)
                value.pop("base", None)
            return value

        layers = {key[2]: node("layer", row) for key, row in selected.items() if key[0] == "layer"}
        roots = []
        for key, row in selected.items():
            kind, _, id = key
            if kind == "layer":
                value = layers[id]
                if row["father"] in layers:
                    layers[row["father"]].setdefault("children", []).append(value)
                else:
                    roots.append(value)
            elif kind == "object":
                value = node(kind, row)
                if row["layer"] in layers:
                    layers[row["layer"]].setdefault("children", []).append(value)
                else:
                    roots.append(value)
        # 保留来源身份，用于 add 重新发号后的关系转换；project.op 只在完整项目范围导出。
        project_node = {"data": {field: project[field] for field in specs["project"]["fields"]}}
        if whole:
            project_node["op"] = op
            if include_baseline and op != "add":
                project_node["base"] = fingerprint(connection, "project", project, specs["project"])
        externals = set()
        for key, row in selected.items():
            for _, target, _ in references(key[0], row, specs):
                if target not in selected and target != ("project", None, project_id):
                    externals.add(target)
        # 局部文档只携带用到的表及声明依赖；补结构不扩展业务记录范围。
        definitions = set(tool_kinds) if whole else {key[0] for key in selected if key[0] in tool_kinds}
        pending = list(definitions)
        while pending:
            spec = specs[pending.pop()]
            for ref in [*spec["references"], *spec.get("logical_references", [])]:
                target = ref["kind"]
                if target not in CORE and target not in definitions:
                    definitions.add(target)
                    pending.append(target)
        document = {"format_version": 1, "project_id": project_id, "project": project_node,
                "preserve_positions": True,
                "scope": {"layer_ids": layer_ids, "object_ids": object_ids, "begin": begin, "end": end,
                          "include_tools": include_tools, "include_global": include_global},
                **({} if compact else {
                    "tables": {kind: table_definition(specs[kind]) for kind in sorted(definitions)},
                    "source_numbering": numbering_entries(connection)}),
                "items": roots,
                "records": [node(key[0], row) for key, row in selected.items() if key[0] not in {"layer", "object"}],
                "external_references": [address(key) for key in sorted(externals, key=repr)],
                "counts": {kind: sum(key[0] == kind for key in selected) for kind in ("layer", "object", "bind", *tool_kinds)},
                "omitted_tool_records": {kind: sum(key[0] == kind for key in candidates) for kind in tool_kinds
                                         if any(key[0] == kind for key in candidates)}}
        if compact:
            document["scope"]["compact"] = True
        return document

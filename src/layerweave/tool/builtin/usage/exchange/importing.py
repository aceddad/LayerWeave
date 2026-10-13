"""解析上下文与文档内引用；筛掉警告项后，业务写入仍归一个外层事务。"""
from copy import deepcopy

from layerweave.support.api import Loader, register_tables, run_operation, table_specs
from layerweave.support.configuration.loader import DEFAULT_ROOT
from layerweave.support.providers import DEFAULT_CHECKER, optional_checker
from layerweave.support.transaction import require_write_session, reject_nested_operation
from .format import CORE, OPS, address, document_value, fail, fingerprint, identity, table_definition


class Pending(Exception):
    pass


class Skip(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


def prepare_exchange(connection, document):
    """独立准备表声明，不进入业务撤销；已有新增列保留，不改身份、引用或已有列。"""
    reject_nested_operation(connection)
    document = document_value(document)
    specs, proposed = table_specs(connection), {}
    for kind, definition in document.get("tables", {}).items():
        if kind in CORE:
            fail("工具表声明不能覆盖内置表", "/tables/" + kind)
        raw = deepcopy(definition)
        if kind in specs:
            old = table_definition(specs[kind])
            # 归属引用、默认类型等交给 register_tables 规范化后比较，避免把等价声明当作变更。
            raw = {**old, **raw, "fields": {**old["fields"], **raw.get("fields", {})}}
        proposed[kind] = raw
    if proposed:
        register_tables(connection, proposed)
    return {"prepared_kinds": sorted(proposed), "separate_transaction": True}


class Importer:
    def __init__(self, write, document, *, project_id, new_project, parent_layer_id, external_refs,
                 reference_map, check_baseline, config_root):
        self.write = require_write_session(write)
        self.connection = write.connection
        self.doc = document_value(document)
        self.specs = table_specs(self.connection)
        self.source = self.doc.get("project_id")
        self.target, self.new = project_id, new_project
        self.attach = parent_layer_id
        self.external = external_refs
        self.check_base = check_baseline
        self.loader = Loader(config_root)
        self.nodes, self.ids, self.keys, self.explicit = [], {}, {}, {}
        self.issues, self.maps = [], []
        if external_refs not in {"skip", "preserve"}:
            fail("external_refs 应为 skip 或 preserve", allowed=["skip", "preserve"])
        for item in reference_map or []:
            source, target = item["source"], item["target"]
            self.explicit[self._address(source)] = self._address(target)
        for name in ("items", "records"):
            self._flatten(self.doc.get(name, []), "/" + name, None)

    def _address(self, value):
        kind = value["kind"]
        if kind not in self.specs or kind == "change":
            fail(f"引用的 kind 未登记：{kind}")
        return identity(kind, value.get("project_id", self.source), value["id"], self.specs)

    def _flatten(self, values, path, parent):
        if not isinstance(values, list):
            fail("children 需要列表", path)
        for index, raw in enumerate(values):
            pointer = f"{path}/{index}"
            if not isinstance(raw, dict):
                fail("节点需要字典", pointer)
            kind, op = raw.get("kind"), raw.get("op")
            if kind not in self.specs or kind in {"project", "change"}:
                fail("节点需要已登记的业务 kind；项目操作写在 project 区域", pointer + "/kind",
                     allowed=sorted(set(self.specs) - {"project", "change"}))
            if op is not None and op not in OPS:
                fail("op 应为 add、update 或 delete；省略表示上下文", pointer + "/op", allowed=list(OPS))
            if not isinstance(raw.get("data", {}), dict) or not isinstance(raw.get("refs", {}), dict):
                fail("data 和 refs 需要字典", pointer)
            if op != "add" and (type(raw.get("id")) is not int or raw["id"] < 1):
                fail("已有节点需要正整数 id", pointer + "/id")
            if "project_id" in raw and self.specs[kind]["scoped"] and raw["project_id"] != self.source:
                fail("一份文档只声明一个来源项目；跨项目目标使用引用", pointer + "/project_id")
            node = {"raw": raw, "kind": kind, "op": op, "path": pointer, "parent": parent, "state": "pending"}
            self.nodes.append(node)
            if type(raw.get("id")) is int and raw["id"] > 0:
                key = identity(kind, self.source, raw["id"], self.specs)
                if key in self.ids:
                    fail("同一来源身份重复声明，请合并到一个节点", pointer, code="duplicate_identity")
                self.ids[key] = node
            if "key" in raw:
                key = raw["key"]
                if not isinstance(key, str) or not key or key in self.keys:
                    fail("key 需要文档内唯一的非空字符串", pointer + "/key")
                self.keys[key] = node
            if raw.get("children") and kind != "layer":
                fail("只有层节点可以装载 children", pointer + "/children")
            self._flatten(raw.get("children", []), pointer + "/children", node)

    def _warn(self, node, error):
        node["state"] = "skipped"
        self.issues.append({"severity": "warn", "code": error.code, "message": str(error), "effect": "skipped",
                            "pointer": node["path"], "kind": node["kind"], "source_id": node["raw"].get("id"), **error.details})

    def _resolved_node(self, node, *, allow_deleted=False):
        if node["state"] == "pending":
            raise Pending()
        if node["state"] == "skipped" or (node["state"] == "deleted" and not allow_deleted):
            raise Skip("dependency_skipped", "引用目标被跳过或删除，本项未执行", dependency=node["path"])
        return node["identity"]

    def _resolve(self, key, *, copying, expression=None, allow_deleted=False):
        if expression is not None:
            if "key" in expression:
                node = self.keys.get(expression["key"])
                if node is None:
                    raise Skip("unresolved_reference", "文档内 key 不存在", reference=expression)
                return self._resolved_node(node, allow_deleted=allow_deleted)
            key = self._address(expression)
            if expression.get("external"):
                return key
        if key in self.explicit:
            return self.explicit[key]
        if key == ("project", None, self.source):
            return "project", None, self.target
        if key in self.ids:
            return self._resolved_node(self.ids[key], allow_deleted=allow_deleted)
        if copying and self.external != "preserve":
            raise Skip("external_reference", "引用目标不在文档内；请提供映射或明确保留外部引用", reference=address(key))
        if not copying and key[1] == self.source and key[0] in self.specs and self.specs[key[0]]["scoped"]:
            return key[0], self.target, key[2]
        return key

    def _parent(self, node):
        parent = node["parent"]
        if parent is not None:
            return self._resolved_node(parent, allow_deleted=node["op"] in {None, "delete"})[2], True
        if node["kind"] not in {"layer", "object"}:
            return None, False
        if self.attach is not None:
            return self.attach, True
        if "parent_id" not in node["raw"]:
            return None, False
        value = node["raw"]["parent_id"]
        if value is None:
            return None, True
        return self._resolve(("layer", self.source, value), copying=node["op"] == "add", allow_deleted=node["op"] == "delete")[2], True

    def _payload(self, node, parent_id, has_parent):
        kind, raw, spec = node["kind"], node["raw"], self.specs[node["kind"]]
        data = deepcopy(raw.get("data", {}))
        allowed = set(spec["fields"]) | ({"id"} if node["op"] == "add" and spec["id_source"] == "provided" else set())
        if set(data) - allowed:
            fail("data 包含不可写字段", node["path"] + "/data", fields=sorted(set(data)-allowed), allowed=sorted(allowed))
        row = {"id": raw.get("id"), "project_id": self.source, **data}
        if kind == "bind":
            descriptors = [(side, (row.get(side+"_kind"), row.get(side+"_project_id"), row.get(side+"_id")),
                            (side+"_project_id",side+"_id")) for side in ("source","target")]
        else:
            descriptors = []
            for ref in spec["references"]:
                fields = tuple(ref["fields"])
                values = [row.get(field) for field in fields]
                key = identity(ref["kind"], values[0] if self.specs[ref["kind"]]["scoped"] else None, values[-1], self.specs)
                descriptors.append((fields[-1], key, fields))
        supplied = raw.get("refs", {})
        unknown = set(supplied) - {name for name, _, _ in descriptors}
        if unknown:
            fail("refs 只能指定标准关系或表声明中的引用", node["path"] + "/refs", fields=sorted(unknown))
        parent_field = "father" if kind == "layer" else "layer" if kind == "object" else None
        for name, key, fields in descriptors:
            if name == parent_field and has_parent and node["op"] == "add":
                data[name] = parent_id
                continue
            if fields == ("project_id",):
                continue
            if name == "id" and node["op"] != "add":
                continue
            if name not in supplied and (key[2] is None or (not any(field in data for field in fields if field != "project_id") and name != "id")):
                continue
            resolved = self._resolve(key, copying=node["op"] == "add", expression=supplied.get(name))
            if kind != "bind" and resolved[0] != key[0]:
                fail("引用目标种类与表声明不同", node["path"] + "/refs/" + name)
            values = resolved[1:] if len(fields) == 2 else resolved[2:]
            for field, value in zip(fields, values):
                if field == "project_id":
                    if value != self.target:
                        raise Skip("reference_scope", "引用要求不同的记录归属，请明确提供目标映射", reference=address(resolved))
                else:
                    data[field] = value
            if kind == "bind":
                data[name+"_kind"] = resolved[0]
        if node["op"] == "add" and kind in {"layer", "object"} and has_parent:
            data[parent_field] = parent_id
        if kind == "layer" and "config_ref" in data and "type" not in data:
            data["type"] = self.loader.load(data["config_ref"], "layer")["type"]
        if node["op"] == "add" and spec["id_source"] == "provided" and "id" not in data:
            data["id"] = raw.get("id")
        return data

    def _execute(self, node):
        kind, op, raw = node["kind"], node["op"], node["raw"]
        spec = self.specs[kind]
        scope = {"project_id": self.target} if spec["scoped"] else {}
        parent_id, has_parent = self._parent(node)
        current = None
        if op != "add":
            current = self.write.read(kind, id=raw["id"], **scope)
            if current is None:
                fail(f"{kind} {raw['id']} 不存在", node["path"], code="target_not_found")
            if has_parent and kind in {"layer", "object"}:
                actual = current["father" if kind == "layer" else "layer"]
                if actual != parent_id:
                    raise Skip("parent_mismatch", "ID 存在但直属归属不一致，本项未执行", expected_parent=parent_id, actual_parent=actual)
            if op is not None and self.check_base and "base" in raw and raw["base"] != fingerprint(self.connection, kind, current, spec):
                raise Skip("source_changed", "数据库内容与导出时的状态不同，本项未执行")
        if op is None:
            row, state = current, "selected"
        elif op == "delete":
            row, state = self.write.delete(kind, raw["id"], **scope), "deleted"
        else:
            data = self._payload(node, parent_id, has_parent)
            if op == "add":
                create = self.write.create_exact if self.doc.get("preserve_positions", False) else self.write.create
                row, state = create(kind, data, **scope), "created"
            else:
                if self.doc.get("preserve_positions", False) and kind == "object":
                    row = self.write.restore(kind, raw["id"], {**current, **data}, fields=list(data), **scope)
                else:
                    row = self.write.update(kind, raw["id"], data, **scope)
                state = "unchanged" if row == current else "updated"
        node["state"] = state
        node["identity"] = identity(kind, self.target, row["id"], self.specs)
        if op == "add":
            source = {"kind": kind, "project_id": self.source if spec["scoped"] else None, "id": raw.get("id")}
            if "key" in raw:
                source["key"] = raw["key"]
            self.maps.append({"source": source, "target": address(node["identity"])})

    def run(self):
        project = self.doc.get("project", {})
        op = project.get("op")
        if op is not None and op not in OPS:
            fail("project.op 应为 add、update 或 delete", "/project/op")
        if self.new and self.target is not None:
            fail("new_project 与 project_id 不能同时提供")
        create_project = self.new or (self.target is None and (self.source is None or op == "add"))
        self.write.defer_references()
        if create_project:
            if op == "delete":
                fail("不能新建一个用于删除的项目", "/project/op")
            row = self.write.create("project", project.get("data", {"name": self.doc.get("name", "导入项目")}))
            self.target, project_state = row["id"], "created"
            self.maps.append({"source": {"kind": "project", "project_id": None, "id": self.source},
                              "target": {"kind": "project", "project_id": None, "id": self.target}})
        else:
            self.target = self.source if self.target is None else self.target
            row = self.write.read("project", id=self.target)
            if row is None:
                fail(f"目标项目 {self.target} 不存在", code="target_not_found")
            project_state = "selected"
            if op in {"update", "delete"}:
                if self.check_base and "base" in project and project["base"] != fingerprint(self.connection, "project", row, self.specs["project"]):
                    project_state = "skipped"
                    self.issues.append({"severity":"warn", "code":"source_changed", "pointer":"/project", "effect":"skipped",
                                        "message":"项目内容已变化，依赖该项目上下文的本批节点均未执行"})
                    for node in self.nodes:
                        self._warn(node, Skip("dependency_skipped", "项目上下文已跳过", dependency="/project"))
                elif op == "update":
                    after = self.write.update("project", self.target, project.get("data", {}))
                    project_state = "unchanged" if after == row else "updated"
                else:
                    self.write.delete("project", self.target)
                    project_state = "deleted"
        if self.attach is not None and self.write.read("layer", project_id=self.target, id=self.attach) is None:
            fail("附着层不存在", field="parent_layer_id")
        while any(node["state"] == "pending" for node in self.nodes):
            progress = False
            for node in self.nodes:
                if node["state"] != "pending":
                    continue
                try:
                    self._execute(node)
                except Pending:
                    continue
                except Skip as issue:
                    self._warn(node, issue)
                except Exception as error:
                    error.details = {**getattr(error, "details", {}), "pointer": node["path"]}
                    raise
                progress = True
            if not progress:
                for node in self.nodes:
                    if node["state"] == "pending":
                        self._warn(node, Skip("unresolved_dependency", "新增引用形成循环或尚无可用身份；请分为创建和更新两步"))
        counts = {state: sum(node["state"] == state for node in self.nodes)
                  for state in ("created","updated","deleted","unchanged","selected","skipped")}
        return {"status": "partial" if self.issues else "completed", "project_id": self.target,
                "project_action": project_state, "counts": counts, "issues": self.issues, "id_map": self.maps,
                "items": [{"pointer": node["path"], "kind": node["kind"], "op": node["op"], "status": node["state"],
                           **({"target": address(node["identity"])} if "identity" in node else {})} for node in self.nodes]}


def import_project_in_session(write, document, *, project_id=None, new_project=False, parent_layer_id=None,
                              external_refs="skip", reference_map=None, check_baseline=True, config_root=DEFAULT_ROOT):
    """已准备表结构后的事务内导入；返回业务报告，写入错误抛出交给外层回滚。"""
    return Importer(write, document, project_id=project_id, new_project=new_project, parent_layer_id=parent_layer_id,
                    external_refs=external_refs, reference_map=reference_map, check_baseline=check_baseline,
                    config_root=config_root).run()


def import_project(connection, document, *, project_id=None, new_project=False, parent_layer_id=None,
                   external_refs="skip", reference_map=None, check_baseline=True, prepare_tables=True,
                   config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    """先独立准备工具表，再执行一次可撤销业务操作；归属和基线冲突跳过并汇总。"""
    reject_nested_operation(connection)
    schema = {"prepared_kinds": [], "separate_transaction": True}
    try:
        value = document_value(document)
        if prepare_tables:
            schema = prepare_exchange(connection, value)
    except Exception as error:
        def failed(write, error=error):
            raise error
        return {**run_operation(connection, failed), "schema": schema}
    observed = {}
    def work(write):
        engine = Importer(write, value, project_id=project_id, new_project=new_project, parent_layer_id=parent_layer_id,
                          external_refs=external_refs, reference_map=reference_map, check_baseline=check_baseline,
                          config_root=config_root)
        try:
            return engine.run()
        finally:
            observed["issues"] = deepcopy(engine.issues)
    result = run_operation(connection, work, checker=optional_checker(checker, config_root=config_root))
    if not result["ok"] and observed.get("issues"):
        result["import_issues"] = observed["issues"]
    return {**result, "schema": schema}

"""依据托管表声明读取真实引用；供恢复规划和 SQL 失败说明复用。"""
from .tables import table_specs, quote


def reference_key(ref, row, specs):
    values = [row.get(field) for field in ref["fields"]]
    if any(value is None for value in values):
        return None
    return (ref["kind"], values[0], values[1]) if specs[ref["kind"]]["scoped"] else (ref["kind"], None, values[0])


def missing_references(connection, kind, row, specs=None):
    specs = table_specs(connection) if specs is None else specs
    missing = []
    for ref in specs[kind]["references"]:
        key = reference_key(ref, row, specs)
        if key is None:
            continue
        target = specs[key[0]]
        fields, values = (["project_id", "id"], key[1:]) if target["scoped"] else (["id"], key[2:])
        where = " AND ".join(f"{quote(name)}=?" for name in fields)
        if connection.execute(f'SELECT 1 FROM {quote(target["table"])} WHERE {where}', values).fetchone() is None:
            missing.append((ref, key))
    return missing


def dependent_records(connection, key, specs=None):
    """返回引用指定身份的 (kind, 解码记录, 引用声明)，覆盖跨项目和全局表。"""
    from .crud import _decode

    specs = table_specs(connection) if specs is None else specs
    values = key[1:] if specs[key[0]]["scoped"] else key[2:]
    result = []
    for kind, spec in specs.items():
        for ref in spec["references"]:
            if ref["kind"] != key[0]:
                continue
            where = " AND ".join(f"{quote(name)}=?" for name in ref["fields"])
            for row in connection.execute(f'SELECT * FROM {quote(spec["table"])} WHERE {where}', values):
                result.append((kind, _decode(spec, row), ref))
    return result

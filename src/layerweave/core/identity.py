"""身份与引用的纯数据表达；层/对象按项目定位，project/bind 使用独立编号。"""


def identity_key(kind, project_id, id):
    return kind, project_id if kind in {"layer", "object"} else None, id


def reference(kind, project_id, id):
    kind, project_id, id = identity_key(kind, project_id, id)
    return {"kind": kind, "project_id": project_id, "id": id}

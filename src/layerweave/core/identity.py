"""身份与引用的纯数据表达；层/对象按项目定位，project/bind 使用独立编号。"""


def identity_key(kind, project_id, id):
    # 扩展记录保留调用方提供的项目范围；独立编号的记录传入 None。
    return kind, None if kind in {"project", "bind", "change"} else project_id, id


def reference(kind, project_id, id):
    kind, project_id, id = identity_key(kind, project_id, id)
    return {"kind": kind, "project_id": project_id, "id": id}

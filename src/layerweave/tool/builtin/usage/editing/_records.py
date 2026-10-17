"""编辑包内部的记录选择、时长读取和可写字段复制。"""
from copy import deepcopy
from math import isfinite
from layerweave.support import records as crud
from layerweave.support.api import decimal_value


def _number(value, label):
    if type(value) not in {int, float} or not isfinite(value):
        raise ValueError(f"{label} 必须是可计算的有限数值")
    return value

def _position(record, field):
    return _number(record[field], f"对象 ({record['project_id']}, {record['id']}) 的 {field}")

def _duration(record):
    return decimal_value(_position(record, "end")) - decimal_value(_position(record, "begin"))

def _layer(read, project_id, layer_id):
    if layer_id is None:
        raise ValueError("需要明确的 layer_id")
    record = read("layer", project_id=project_id, id=layer_id)
    if record is None:
        raise KeyError(f"层 ({project_id}, {layer_id}) 不存在")
    return record

def _objects(read, project_id, object_ids=None, layer_id=None):
    """显式选择编号，或指定整层；顺序保留，重复编号只处理一次。"""
    if layer_id is not None:
        layer_id = _layer(read, project_id, layer_id)["id"]
    if object_ids is None:
        if layer_id is None:
            raise ValueError("请指定 object_ids 或 layer_id")
        return read("object", project_id=project_id, filters={"layer": layer_id})
    if isinstance(object_ids, (str, bytes)):
        raise TypeError("object_ids 需要编号序列，不能传入单个字符串")
    records = {}
    for id in dict.fromkeys(object_ids):
        if id is None:
            raise ValueError("对象选择需要明确的编号")
        record = read("object", project_id=project_id, id=id)
        if record is None:
            raise KeyError(f"对象 ({project_id}, {id}) 不存在")
        if layer_id is not None and record["layer"] != layer_id:
            raise ValueError(f"对象 {id} 不属于指定层 {layer_id}")
        records.setdefault(record["id"], record)
    return list(records.values())

def _tail(read, project_id, layer_id, *, after_id=None, empty_start=0):
    if after_id is not None:
        record = _objects(read, project_id, [after_id], layer_id)[0]
        return _position(record, "end")
    _layer(read, project_id, layer_id)
    records = read("object", project_id=project_id, filters={"layer": layer_id})
    if not records:
        return _number(empty_start, "空层起点")
    return max(_position(record, "end") for record in records)


def _payload(kind, row):
    return {key: deepcopy(row[key]) for key in crud.writable_fields(kind)}

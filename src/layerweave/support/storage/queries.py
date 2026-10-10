"""内部工具复用的只读查询；SQL 与存储字段约定集中在存储层。"""

from math import isfinite

from layerweave.support.storage import crud
from layerweave.support.storage.assembly import _snapshot


def _object_conditions(project_id, *, layer_id=None, name=None, begin=None, end=None):
    spec = crud.SPECS["object"]
    crud._scope(spec, project_id)
    for value in (begin, end):
        if value is not None and (type(value) not in {int, float} or not isfinite(value)):
            raise ValueError("查询位置应为有限数值，未限定的一端使用 None")
    if begin is not None and end is not None and begin > end:
        raise ValueError("查询 begin 不能晚于 end")

    terms, values = ['project_id = ?'], [project_id]
    if layer_id is not None:
        terms.append('layer = ?')
        values.append(layer_id)
    if name is not None:
        terms.append('instr(name, ?) > 0')
        values.append(name)
    if begin is not None or end is not None:
        terms.extend(['typeof("begin") IN (\'integer\', \'real\')',
                      'typeof("end") IN (\'integer\', \'real\')', '"begin" <= "end"'])
        if begin is not None and begin == end:
            terms.append('"begin" <= ? AND ("end" > ? OR "begin" = ?)')
            values.extend((begin, begin, begin))
        else:
            if begin is not None:
                terms.append('("end" > ? OR ("begin" = "end" AND "begin" >= ?))')
                values.extend((begin, begin))
            if end is not None:
                terms.append('"begin" < ?')
                values.append(end)
    return ' AND '.join(terms), values


def query_objects(connection, project_id, *, layer_id=None, name=None, begin=None, end=None):
    """对象记录，不装载关联。name 为字面子串；位置为相交范围，相等边界表示点查询。"""
    where, values = _object_conditions(project_id, layer_id=layer_id, name=name, begin=begin, end=end)
    with _snapshot(connection):
        rows = connection.execute(
            'SELECT * FROM objects WHERE ' + where + ' ORDER BY layer, "begin", "end", id', values,
        )
        return [crud._decode(crud.SPECS["object"], row) for row in rows]


def read_bindings(connection, kind, project_id, id, *, direction="both"):
    """按实体完整身份读取直接关联；软引用失效时仍可查询，both 下自关联只取一行。"""
    if kind not in {"layer", "object"}:
        raise ValueError("关联查询的实体 kind 应为 layer 或 object")
    crud._scope(crud.SPECS[kind], project_id)
    if direction not in {"outgoing", "incoming", "both"}:
        raise ValueError("direction 应为 outgoing、incoming 或 both")
    sides = ("source", "target") if direction == "both" else (("source",) if direction == "outgoing" else ("target",))
    terms, values = [], []
    for side in sides:
        terms.append(f'({side}_kind = ? AND {side}_project_id = ? AND {side}_id = ?)')
        values.extend((kind, project_id, id))
    with _snapshot(connection):
        rows = connection.execute('SELECT * FROM binds WHERE ' + ' OR '.join(terms) + ' ORDER BY id', values)
        return [dict(row) for row in rows]


def read_layer_positions(connection, project_id, layer_id):
    """同一读取快照内取层身份和直属对象位置；不加载正文，也不隐藏异常位置。"""
    if layer_id is None:
        raise ValueError("需要明确的 layer_id")
    with _snapshot(connection):
        layer = crud.read(connection, "layer", project_id=project_id, id=layer_id)
        if layer is None:
            return None
        rows = connection.execute(
            'SELECT id, "begin", "end" FROM objects WHERE project_id = ? AND layer = ? ORDER BY "begin", "end", id',
            (layer["project_id"], layer["id"]),
        )
        return {"project_id": layer["project_id"], "layer_id": layer["id"], "objects": [dict(row) for row in rows]}

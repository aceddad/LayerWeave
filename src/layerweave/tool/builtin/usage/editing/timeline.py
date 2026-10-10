"""分割与插空档的共同计算/写入；通用平移继续使用 dispatch 请求工厂。"""

from copy import deepcopy
from functools import partial

from layerweave.support import records as crud
from layerweave.support.storage.details import read_project_details
from layerweave.tool.builtin.usage.editing.tree_service import _checker, _payload
from layerweave.support.configuration.loader import DEFAULT_ROOT
from ._plan import dispatch
from layerweave.support.feedback import InputError, target
from layerweave.support.operation import run_operation
from layerweave.support.providers import DEFAULT_CHECKER
from layerweave.support.positions import PositionMath, decimal_value, numeric_position, shifted_positions


CROSSING_ACTIONS = ("split", "keep", "stretch", "move")


def _number(value, field):
    if not numeric_position(value):
        raise InputError(f"{field} 应为有限数值", field=field)
    return value


def _record(connection, kind, project_id, id):
    if id is None:
        raise InputError("需要明确的目标编号", field="id")
    row = crud.read(connection, kind, project_id=project_id if kind != "project" else None, id=id)
    if row is None:
        raise InputError("指定目标不存在", code="target_not_found", target=target(kind, project_id, id))
    return row


def _select(connection, project_id, *, object_ids=None, layer_id=None, layer_ids=None, whole=False):
    if layer_ids is not None and (layer_id is not None or object_ids is not None):
        raise InputError("子树范围不能同时指定 layer_id 或 object_ids", field="layer_ids")
    owner = _record(connection, "project", None, project_id)["id"]
    if layer_ids is not None:
        data = read_project_details(connection, owner, layer_ids=layer_ids)
        if data["missing_layer_ids"]:
            raise InputError("部分起始层不存在，本批未写入", field="layer_ids", missing_ids=data["missing_layer_ids"])
        return owner, [row["id"] for row in data["layers"]], [obj for row in data["layers"] for obj in row["objects"]]
    layer = _record(connection, "layer", owner, layer_id) if layer_id is not None else None
    if object_ids is not None:
        if isinstance(object_ids, (str, bytes)):
            raise InputError("object_ids 应为编号列表", field="object_ids")
        rows = {}
        for id in object_ids:
            row = _record(connection, "object", owner, id)
            if layer is not None and row["layer"] != layer["id"]:
                raise InputError(f"对象 {id} 不属于指定层", field="object_ids")
            rows[row["id"]] = row
        return owner, list(dict.fromkeys(row["layer"] for row in rows.values())), list(rows.values())
    if layer is not None:
        return owner, [layer["id"]], crud.read(connection, "object", project_id=owner, filters={"layer": layer["id"]})
    if whole:
        return owner, [row["id"] for row in crud.read(connection, "layer", project_id=owner)], crud.read(connection, "object", project_id=owner)
    raise InputError("请指定 object_ids、layer_id 或 layer_ids", field="scope")


def shift_objects(connection, project_id, object_ids=None, *, offset, layer_id=None, layer_ids=None,
                  from_position=None, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    def plan(read):
        _number(offset, "offset")
        if from_position is not None:
            _number(from_position, "from_position")
        owner, _, rows = _select(connection, project_id, object_ids=object_ids, layer_id=layer_id, layer_ids=layer_ids)
        math = PositionMath(read, owner)
        return [{"action": "update", "kind": "object", "project_id": owner, "id": row["id"],
                 "data": shifted_positions(row, offset, math)} for row in rows
                if from_position is None or _number(row["begin"], "begin") >= from_position]
    return dispatch(connection, plan, config_root=config_root, checker=checker)


def _information(value, field, row):
    if not isinstance(value, dict):
        raise InputError(f"{field} 需要明确提供完整的 information 字典", field=field,
                         target=target("object", row["project_id"], row["id"]))
    return deepcopy(value)


def _prepare_split(row, math, first_information, cuts):
    cuts = list(cuts)
    if not cuts:
        return [], []
    layer = row["layer"]
    begin = math.snap(layer, _number(row["begin"], "begin"))
    end = math.snap(layer, _number(row["end"], "end"))
    previous = math.ticks(layer, begin)
    end_tick = math.ticks(layer, end)
    bounds, contents, positions = [begin], [_information(first_information, "first_information", row)], []
    for index, cut in enumerate(cuts):
        if not isinstance(cut, dict) or "at" not in cut or "information" not in cut:
            raise InputError("每个切点需要 at 和 information", field=f"cuts[{index}]")
        requested = _number(cut["at"], f"cuts[{index}].at")
        actual = math.snap(layer, requested)
        tick = math.ticks(layer, actual)
        if not previous < tick < end_tick:
            raise InputError("切点落点后必须严格递增且位于原区间内部", code="invalid_cut",
                             field=f"cuts[{index}].at", requested=requested, actual=actual,
                             target=target("object", row["project_id"], row["id"]))
        bounds.append(actual)
        positions.append({"requested": requested, "actual": actual})
        contents.append(_information(cut["information"], f"cuts[{index}].information", row))
        previous = tick
    bounds.append(end)
    return [{"begin": a, "end": b, "information": info} for a, b, info in zip(bounds, bounds[1:], contents)], positions


def _apply_split(connection, row, parts, math, operation_id):
    if not parts:
        return [row]
    first, _ = crud.update(connection, "object", row["id"], parts[0], project_id=row["project_id"],
                                operation_id=operation_id, position_math=math)
    result = [first]
    for part in parts[1:]:
        created, _ = crud.create(connection, "object", {**_payload("object", row), **part},
                                      project_id=row["project_id"], operation_id=operation_id, position_math=math)
        result.append(created)
    return result


def split_object(connection, project_id, object_id, *, cuts, first_information=None,
                 config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    def work(write):
        operation_id = write.operation_id
        row = _record(connection, "object", project_id, object_id)
        math = PositionMath(partial(crud.read, connection), row["project_id"])
        parts, positions = _prepare_split(row, math, first_information, cuts)
        segments = _apply_split(connection, row, parts, math, operation_id)
        return {"project_id": row["project_id"], "object_id": row["id"], "cuts": positions, "segments": segments}
    return {**run_operation(connection, work, checker=_checker(checker, config_root)), "tool": "split_object"}


def insert_gap(connection, project_id, *, at, length, layer_id=None, layer_ids=None, whole_project=False,
               crossing_actions=None, split_contents=None,
               config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    def work(write):
        operation_id = write.operation_id
        if type(whole_project) is not bool or sum((layer_id is not None, layer_ids is not None, whole_project is True)) != 1:
            raise InputError("请明确选择一个范围：直属层、子树或整个项目", field="scope", code="explicit_scope_required",
                             allowed=["layer_id", "layer_ids", "whole_project=True"])
        if crossing_actions is not None and split_contents is not None:
            raise InputError("crossing_actions 与旧参数 split_contents 不能同时提供", field="crossing_actions")
        _number(at, "at")
        if _number(length, "length") <= 0:
            raise InputError("空档长度应大于零", field="length")
        owner, layers, rows = _select(connection, project_id, layer_id=layer_id, layer_ids=layer_ids, whole=whole_project)
        math = PositionMath(partial(crud.read, connection), owner)
        gaps = {}
        for id in layers:
            begin = math.snap(id, at)
            end = math.snap(id, decimal_value(begin) + decimal_value(length))
            if math.ticks(id, end) <= math.ticks(id, begin):
                raise InputError("长度落点后无法形成空档", field="length", target=target("layer", owner, id), actual_begin=begin, actual_end=end)
            gaps[id] = {"layer_id": id, "begin": begin, "end": end, "length": float(decimal_value(end) - decimal_value(begin))}
        supplied = {}
        entries = crossing_actions if crossing_actions is not None else split_contents
        for item in entries or []:
            if not isinstance(item, dict) or type(item.get("object_id")) is not int:
                raise InputError("每项跨界处理需要整数 object_id", field="crossing_actions")
            if item["object_id"] in supplied:
                raise InputError("同一对象的跨界处理只能提供一次", field="crossing_actions")
            # 旧文件明确给出两段内容时仍表示 split；不根据对象类型推断处理方式。
            action = item.get("action", "split" if "first_information" in item and "second_information" in item else None)
            if action not in CROSSING_ACTIONS:
                raise InputError("跨界对象需要明确选择 split、keep、stretch 或 move", field="action", allowed=list(CROSSING_ACTIONS),
                                 target=target("object", owner, item["object_id"]))
            supplied[item["object_id"]] = {**item, "action": action}
        shifts, crossings = [], []
        for row in rows:
            gap = gaps[row["layer"]]
            begin = _number(row["begin"], "begin")
            end = _number(row["end"], "end")
            point = gap["begin"]
            if begin >= point:  # 瞬间对象正好在切点时也后移。
                shifts.append((row, shifted_positions(row, gap["length"], math)))
            elif point < end:
                crossings.append(row)
        crossing_ids = {row["id"] for row in crossings}
        missing = [{"object_id": row["id"], "layer_id": row["layer"], "begin": row["begin"], "end": row["end"],
                    "at": gaps[row["layer"]]["begin"]} for row in crossings if row["id"] not in supplied]
        if missing or supplied.keys() - crossing_ids:
            raise InputError("跨界处理与当前对象不对应；本批未写入", code="crossing_actions_required", field="crossing_actions",
                             target=target("project", None, owner), allowed=list(CROSSING_ACTIONS),
                             required_crossings=missing, required_splits=missing,
                             unused_object_ids=sorted(supplied.keys() - crossing_ids))
        planned, kept, adjustments = [], [], []
        for row in crossings:
            gap, info = gaps[row["layer"]], supplied[row["id"]]
            if info["action"] == "keep":
                kept.append({"id": row["id"], "layer_id": row["layer"], "begin": row["begin"], "end": row["end"]})
                continue
            if info["action"] == "stretch":
                values = {"end": math.snap(row["layer"], decimal_value(row["end"]) + decimal_value(gap["length"]))}
                adjustments.append((row, values, "stretched"))
                continue
            if info["action"] == "move":
                adjustments.append((row, shifted_positions(row, gap["length"], math), "moved"))
                continue
            parts, _ = _prepare_split(row, math, info.get("first_information"),
                                     [{"at": gap["begin"], "information": info.get("second_information")}])
            parts[1].update(shifted_positions({**row, **parts[1]}, gap["length"], math))
            planned.append((row, parts))
        splits = []
        updates = {"shifted": [], "stretched": [], "moved": []}
        for row, parts in planned:
            segments = _apply_split(connection, row, parts, math, operation_id)
            splits.append({"object_id": row["id"], "segments": segments})
        for row, values, action in [*adjustments, *((row, values, "shifted") for row, values in shifts)]:
            updated, _ = crud.update(connection, "object", row["id"], values, project_id=owner,
                                           operation_id=operation_id, position_math=math)
            summary = {"id": updated["id"], "begin": updated["begin"], "end": updated["end"]}
            if action != "shifted":
                summary.update(layer_id=row["layer"], previous_begin=row["begin"], previous_end=row["end"])
            updates[action].append(summary)
        scope = {"mode": "project" if whole_project else "layer" if layer_id is not None else "subtrees", "layer_ids": layers}
        return {"project_id": owner, "scope": scope, "requested_at": at, "requested_length": length,
                "gaps": list(gaps.values()), "splits": splits, "kept": kept, **updates}
    return {**run_operation(connection, work, checker=_checker(checker, config_root)), "tool": "insert_gap"}

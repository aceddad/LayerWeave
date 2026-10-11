"""视图读取：只读打开数据库，整理成网页需要的结构；素材文件只提供数据库里引用过的。"""
import json
from pathlib import Path
import sqlite3

from layerweave.support.api import read_project_details, read_record

from .fold import KIND as FOLD_KIND, read_folds
from .notes import LAYER_REF as NOTE_LAYER_REF

IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
VIDEO = {".mp4", ".webm", ".mov", ".m4v", ".mkv"}
AUDIO = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}


def open_readonly(database, *, threads=False):
    """只读连接：视图不可能写入业务库。threads=True 时允许跨线程使用，调用方自行加锁。"""
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, check_same_thread=not threads)
    connection.row_factory = sqlite3.Row
    return connection


def media_kind(source):
    if not isinstance(source, str) or not source:
        return None
    suffix = Path(source.split("?")[0]).suffix.lower()
    if suffix in IMAGE:
        return "image"
    if suffix in VIDEO:
        return "video"
    if suffix in AUDIO:
        return "audio"
    return "file"


def resolve_source(database, source):
    """绝对路径直接用；相对路径相对于数据库文件所在目录。网址不在本地提供。"""
    if not isinstance(source, str) or not source or "://" in source:
        return None
    path = Path(source)
    if not path.is_absolute():
        path = Path(database).resolve().parent / path
    return path.resolve()


UNIT_ALIASES = {"秒": {"秒", "s", "sec", "secs", "second", "seconds"}, "帧": {"帧", "f", "frame", "frames"}}


def axis_key(axis):
    """根层的轴按单位归类：单位相同（含常见同义写法，如 秒 / s）的根默认拼在同一块画板里。没有单位的根不参与拼接，返回 None。"""
    unit = (axis or {}).get("unit") if isinstance(axis, dict) else None
    if not isinstance(unit, str) or not unit.strip():
        return None
    unit = unit.strip().lower()
    return next((name for name, aliases in UNIT_ALIASES.items() if unit in aliases), unit)


def order_layers(layers):
    """按父子关系排成树的顺序并记录深度；成环或找不到根的层放在最后，depth 为 None。"""
    children = {}
    for layer in layers:
        children.setdefault(layer["father"], []).append(layer)
    pending = [(layer, 0) for layer in reversed(children.get(None, []))]
    ordered, placed = [], set()
    while pending:
        layer, depth = pending.pop()
        if layer["id"] in placed:
            continue
        placed.add(layer["id"])
        ordered.append({**layer, "depth": depth})
        pending.extend((child, depth + 1) for child in reversed(children.get(layer["id"], [])))
    return ordered + [{**layer, "depth": None} for layer in layers if layer["id"] not in placed]


def project_roots(connection, project_id):
    """项目里的根层，按树的顺序：id、name、unit、key（拼接用的轴类别）。"""
    layers = order_layers(read_record(connection, "layer", project_id=project_id))
    return [{"id": l["id"], "name": l["name"], "unit": (l["axis"] or {}).get("unit", "") if isinstance(l["axis"], dict) else "",
             "key": axis_key(l["axis"])} for l in layers if l["depth"] == 0]


def list_projects(connection):
    return [{"id": row["id"], "name": row["name"], "tips": row["tips"]} for row in read_record(connection, "project")]


def project_view(connection, database, project_id):
    """网页要的整理结果：层按树的顺序，每层记下所属的根；roots 列出每个根的轴和自己子树的时间范围。"""
    details = read_project_details(connection, project_id)
    if details is None:
        return None
    layers, roots, root_of = [], {}, {}
    hidden = _hidden_by_default({layer["config_ref"] for layer in details["layers"]})
    for layer in order_layers(details["layers"]):
        if layer["depth"] is not None:
            root_of[layer["id"]] = layer["id"] if layer["depth"] == 0 else root_of[layer["father"]]
        root = root_of.get(layer["id"])
        if layer["depth"] == 0:
            axis = layer["axis"] if isinstance(layer["axis"], dict) else {}
            roots[layer["id"]] = {"id": layer["id"], "name": layer["name"], "axis": axis, "unit": axis.get("unit", ""),
                                  "key": axis_key(axis), "begin": None, "end": None}
        objects = []
        for obj in layer["objects"]:
            info = obj["information"] if isinstance(obj["information"], dict) else {}
            source = info.get("source")
            kind = media_kind(source)
            path = resolve_source(database, source) if kind else None
            item = {
                "id": obj["id"], "name": obj["name"], "type": obj["config_ref"].rsplit("/", 1)[-1].removesuffix(".toml"),
                "begin": obj["begin"], "end": obj["end"], "tips": obj["tips"],
                "text": info.get("text") if isinstance(info.get("text"), str) else None,
                "media": None if kind is None else {
                    "kind": kind, "source": source,
                    "available": bool(path and path.is_file()),
                    "url": f"/media/{project_id}/{obj['id']}" if path and path.is_file() else None,
                },
                "information": info,
            }
            objects.append(item)
            span = roots.get(root)
            if span is not None and isinstance(obj["begin"], (int, float)) and isinstance(obj["end"], (int, float)):
                span["begin"] = obj["begin"] if span["begin"] is None else min(span["begin"], obj["begin"])
                span["end"] = obj["end"] if span["end"] is None else max(span["end"], obj["end"])
        layers.append({
            "id": layer["id"], "name": layer["name"], "type": layer["type"], "father": layer["father"],
            "depth": layer["depth"], "root": root, "axis": layer["axis"], "tips": layer["tips"], "objects": objects,
            "role": "note" if layer["config_ref"] == NOTE_LAYER_REF else None, "hidden": hidden.get(layer["config_ref"], False),
        })
    for span in roots.values():
        begin = span.pop("begin") or 0
        end = span.pop("end")
        span["extent"] = [begin, end if end is not None and end > begin else begin + 10]
    return {
        "project": {"id": details["project"]["id"], "name": details["project"]["name"], "tips": details["project"]["tips"]},
        "roots": list(roots.values()),
        "layers": layers,
        "binds": project_binds(connection, project_id),
        "folds": [{"layer": layer, "by": by} for layer, by in sorted(read_folds(connection, project_id).items())],
    }


SLIM = ("name", "layer", "begin", "end", "father", "type", "config_ref")


def _short(value, size=80):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= size else text[:size - 1] + "…"


def _slim(record):
    """改动前后只留认得出、定得了位的部分：名字、所在层、位置，以及文字或素材路径（截短）。"""
    if record is None:
        return None
    out = {k: record.get(k) for k in SLIM if k in record}
    info = record.get("information")
    if isinstance(info, dict):
        for key in ("text", "source"):
            if isinstance(info.get(key), str):
                out[key] = _short(info[key], 60)
    return out


def recent_changes(connection, project_id, limit=10):
    """最近 limit 次涉及这个项目的操作，新的在前。每项改动给出种类、编号、动作、改之前和之后的名字与位置、
    改了哪些字段；information 里改了的键给出前后值（截短）。只读日志，不碰业务表。"""
    from layerweave.support.storage.log_reader import operation_page, operation_rows
    _, page = operation_page(connection, project_id, limit=limit * 3)   # 多取一些：只有折叠的操作不列
    operations = []
    for entry in page:
        if len(operations) >= limit:
            break
        rows = operation_rows(connection, entry["operation_id"])
        items = []
        for row in rows:
            before, after, kind = row["before_data"], row["after_data"], row["kind"]
            if kind == FOLD_KIND:
                continue   # 折叠是视图状态，不是内容的改动；画布上直接看得到

            if kind in ("object", "layer") and row["project_id"] != project_id:
                continue   # 跨项目搬移时，另一头的改动不画在这个项目上
            item = {"kind": kind, "id": row["target_id"], "action": row["action"], "before": _slim(before), "after": _slim(after)}
            if row["action"] == "update" and before and after:
                item["fields"] = sorted(k for k in before.keys() | after.keys()
                                        if k != "max_id" and before.get(k) != after.get(k))
                old, new = before.get("information"), after.get("information")
                if isinstance(old, dict) and isinstance(new, dict):
                    item["information"] = [{"key": k, "before": _short(old.get(k)), "after": _short(new.get(k))}
                                           for k in sorted(old.keys() | new.keys()) if old.get(k) != new.get(k)]
            items.append(item)
        if not items and all(row["kind"] == FOLD_KIND for row in rows):
            continue
        operations.append({"operation_id": entry["operation_id"], "at": rows[0]["created_at"],
                           "undo_of": rows[0]["undo_of"], "items": items})
    return operations


def _hidden_by_default(refs):
    """层配置里 display.default_visible = false 的，视图默认收起（比如批注层）。读不到的配置按显示处理。"""
    from layerweave.support.configuration.loader import Loader
    loader, out = Loader(), {}
    for ref in refs:
        try:
            out[ref] = loader.load(ref, "layer").get("display", {}).get("default_visible") is False
        except Exception:   # 配置缺失或损坏：照常显示，问题由检测工具报告
            out[ref] = False
    return out


def project_binds(connection, project_id):
    """这个项目里所有关联：从这里发出的，以及别的项目指向这里的。两端写成 {kind, project, id}。"""
    found = {}
    for field in ("source_project_id", "target_project_id"):
        for row in read_record(connection, "bind", filters={field: project_id}):
            found[row["id"]] = {
                "id": row["id"], "tips": row["tips"],
                "source": {"kind": row["source_kind"], "project": row["source_project_id"], "id": row["source_id"]},
                "target": {"kind": row["target_kind"], "project": row["target_project_id"], "id": row["target_id"]},
            }
    return [found[key] for key in sorted(found)]


def media_path(connection, database, project_id, object_id):
    """只返回该对象 information.source 指向、且确实存在的本地文件。"""
    row = read_record(connection, "object", project_id=project_id, id=object_id)
    if row is None:
        return None
    info = row["information"] if isinstance(row["information"], dict) else {}
    path = resolve_source(database, info.get("source"))
    return path if path is not None and path.is_file() else None


def find_ffmpeg():
    """抽视频帧要用 ffmpeg：环境变量 FFMPEG 优先，其次 PATH。没有时返回 None，视图改用浏览器自己解码。"""
    import os
    import shutil
    value = os.environ.get("FFMPEG")
    if value and Path(value).is_file():
        return value
    return shutil.which("ffmpeg")


def extract_frame(path, seconds, *, width=640, ffmpeg=None):
    """返回视频在 seconds 秒处那一帧的 JPEG 字节。seconds 为 "end" 时取最后一帧；超出时长时也取最后一帧。"""
    import subprocess
    ffmpeg = ffmpeg or find_ffmpeg()
    if ffmpeg is None:
        raise FileNotFoundError("找不到 ffmpeg：请安装并加入 PATH，或用环境变量 FFMPEG 指定")
    output = ["-vf", f"scale={width}:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "4", "-"]
    attempts = [] if seconds == "end" else [["-ss", f"{max(0.0, float(seconds)):.3f}", "-i", str(path), "-frames:v", "1"]]
    # 从结尾往前 0.5 秒开始解到底，留最后一张：比按时长倒推更准（时长和最后一帧的时间常常差一点）
    attempts += [["-sseof", "-0.5", "-i", str(path)], ["-ss", "0", "-i", str(path), "-frames:v", "1"]]
    for seek in attempts:
        result = subprocess.run([ffmpeg, "-v", "error", *seek, *output], capture_output=True, timeout=60)
        if result.returncode == 0 and result.stdout:
            data = result.stdout
            return data[data.rfind(bytes([0xFF, 0xD8])):]   # 解出好几张时只要最后一张（JPEG 以 FFD8 开头）
    raise RuntimeError(f"ffmpeg 没能取出画面：{result.stderr.decode('utf-8', 'replace')[-200:]}")

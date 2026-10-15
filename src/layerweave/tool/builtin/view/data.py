"""视图读取：只读打开数据库，整理成网页需要的结构；文件只提供数据库里引用过的。"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import threading

from layerweave.support.api import read_project_details, read_record, read_snapshot

from .fold import read_folds
from .notes import LAYER_REF as NOTE_LAYER_REF
from .notes.reads import read_reads

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


def _local(base, source):
    """和 resolve_source 同样的规则，但不解析真实路径：整理项目数据时只要知道文件在不在（送文件时再用 resolve_source）。"""
    if not isinstance(source, str) or not source or "://" in source:
        return None
    path = Path(source)
    return str(path if path.is_absolute() else base / path)


def _existing(paths):
    """一批本地文件在不在：去重后并行地查。Windows 上解析路径、查一次文件都要零点几毫秒，
    几千个对象逐个查要好几秒（2026-10-14 量的：5000 个对象的库里整理一次项目要 3.8 秒，九成花在这里）。"""
    unique = list(dict.fromkeys(p for p in paths if p))
    if len(unique) < 32:
        return {p: os.path.isfile(p) for p in unique}
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(unique, pool.map(os.path.isfile, unique)))


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
    # 关联和工具表也属于同一份画面，不能在详情的快照结束后另取一份。
    with read_snapshot(connection):
        return _project_view(connection, database, project_id)


def object_view(obj, project_id, available=False):
    """完整记录转换成画面对象；全量和增量共用，不重读较晚的业务记录。"""
    info = obj["information"] if isinstance(obj["information"], dict) else {}
    source, kind = info.get("source"), media_kind(info.get("source"))
    return {
        "id": obj["id"], "name": obj["name"], "type": obj["config_ref"].rsplit("/", 1)[-1].removesuffix(".toml"),
        "begin": obj["begin"], "end": obj["end"], "tips": obj["tips"],
        "text": info.get("text") if isinstance(info.get("text"), str) else None,
        "media": None if kind is None else {"kind": kind, "source": source, "available": available,
                                             "url": f"/media/{project_id}/{obj['id']}" if available else None},
        "information": info,
    }


def object_views(database, project_id, objects):
    """只检查本批对象的素材；同一对象在一页内的多个版本仍各自保留。"""
    base = Path(database).resolve().parent
    paths = [_local(base, row["information"].get("source")) if isinstance(row["information"], dict) else None
             for row in objects]
    exists = _existing(paths)
    return [object_view(row, project_id, bool(exists.get(path))) for row, path in zip(objects, paths)]


def bind_view(row):
    return {"id": row["id"], "tips": row["tips"],
            "source": {"kind": row["source_kind"], "project": row["source_project_id"], "id": row["source_id"]},
            "target": {"kind": row["target_kind"], "project": row["target_project_id"], "id": row["target_id"]}}


def _project_view(connection, database, project_id):
    """网页要的整理结果：层按树的顺序，每层记下所属的根；roots 列出每个根的轴和自己子树的时间范围。"""
    details = read_project_details(connection, project_id)
    if details is None:
        return None
    layers, roots, root_of = [], {}, {}
    hidden = _hidden_by_default({layer["config_ref"] for layer in details["layers"]})
    base = Path(database).resolve().parent
    local = {}
    for layer in details["layers"]:
        for obj in layer["objects"]:
            info = obj["information"] if isinstance(obj["information"], dict) else {}
            if media_kind(info.get("source")):
                local[obj["id"]] = _local(base, info.get("source"))
    exists = _existing(local.values())
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
            available = bool(kind and exists.get(local.get(obj["id"])))
            item = object_view(obj, project_id, available)
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
        "folds": read_folds(connection, project_id),   # 人和 AI 两边的折叠（fold.py）
        "noteReads": {str(k): v for k, v in read_reads(connection, project_id).items()},   # 批注的已读：{楼主: {名字: 读到的最后一条}}
    }


SLIM = ("name", "layer", "begin", "end", "father", "type", "config_ref")


def _short(value, size=80):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= size else text[:size - 1] + "…"


def _slim(record):
    """改动前后只留认得出、定得了位的部分：名字、所在层、位置，以及文字或文件路径（截短）。"""
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
    _, page = operation_page(connection, project_id, limit=limit * 3)   # 多取一些：只改视图状态（折叠）的操作不列
    operations = []
    for entry in page:
        if len(operations) >= limit:
            break
        rows = operation_rows(connection, entry["operation_id"])
        items = []
        for row in rows:
            before, after, kind = row["before_data"], row["after_data"], row["kind"]
            if kind.startswith("view_"):
                continue   # 视图自己的表（折叠等）：视图状态，不是内容的改动；画布上直接看得到

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
        if not items and all(row["kind"].startswith("view_") for row in rows):
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
            found[row["id"]] = bind_view(row)
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


THUMB_WIDTHS = (160, 320, 640, 1280, 2048)   # 只出这几种宽，免得缓存按任意宽度长
THUMB_KEEP = {".svg", ".gif"}            # 不缩：矢量图本来就轻；动图缩了只剩第一帧
_thumb_slots = threading.BoundedSemaphore(4)   # 同时最多几个 ffmpeg：页面一打开会同时要几百张


def thumbnail(path, width, cache_root=None, *, ffmpeg=None):
    """图片的缩略图：(字节, 类型)。用 ffmpeg 缩到 width 宽（原图更窄时不放大），存在本机视图目录 thumbs/ 里，
    原文件的修改时间或大小变了就重做。带透明的格式（png、webp）缩成 PNG，其余缩成 JPEG。
    没有 ffmpeg、文件解不开（或是 svg、gif）时返回 None，调用方改送原图。
    为什么要缩：画布上一个格子一两百像素宽，原图却常是几 MB 的 3072×2048；手书那个库打开就下载了 390 MB，拖动画布每秒只有 8 帧（2026-10-14 量的）。"""
    import hashlib
    import subprocess
    path = Path(path)
    if path.suffix.lower() in THUMB_KEEP:
        return None
    ffmpeg = ffmpeg or find_ffmpeg()
    if ffmpeg is None:
        return None
    width = min(THUMB_WIDTHS, key=lambda w: (w < width, abs(w - width)))   # 取不小于要求的最近一档
    stat = path.stat()
    alpha = path.suffix.lower() in {".png", ".webp"}
    key = hashlib.sha1(f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|{width}".encode()).hexdigest()[:24]
    folder = Path(cache_root or Path.home() / ".layerweave" / "view") / "thumbs"
    cached = folder / f"{key}.{'png' if alpha else 'jpg'}"
    kind = "image/png" if alpha else "image/jpeg"
    if cached.is_file():
        return cached.read_bytes(), kind
    codec = ["-vcodec", "png"] if alpha else ["-vcodec", "mjpeg", "-q:v", "4"]
    with _thumb_slots:
        if cached.is_file():   # 排队的时候别的请求已经做好了
            return cached.read_bytes(), kind
        result = subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-vf", f"scale='min({width},iw)':-2", "-frames:v", "1",
                                 "-f", "image2pipe", *codec, "-"], capture_output=True, timeout=60)
    if result.returncode != 0 or not result.stdout:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    temp = folder / f"{key}.{os.getpid()}.{threading.get_ident()}.tmp"
    temp.write_bytes(result.stdout)
    os.replace(temp, cached)
    return result.stdout, kind


WAVE_BINS = 800


def waveform(path, cache_root=None, *, ffmpeg=None):
    """音频的波形：整首分成 800 段，每段的平均能量（RMS，0–1）。用 ffmpeg 解成单声道 4000 Hz 再算，存在本机视图目录 waves/ 里。
    页面拿这 800 个数按分贝画（和以前浏览器自己解码时一样）。没有 ffmpeg 或解不开时返回 None，页面退回自己解码。
    为什么放到服务端：分轨常是几十 MB 的 WAV，浏览器要整个下载再解码；手书那个库光 4 条分轨就下载了 147 MB（2026-10-14 量的）。"""
    from array import array
    import hashlib
    import subprocess
    path = Path(path)
    ffmpeg = ffmpeg or find_ffmpeg()
    if ffmpeg is None:
        return None
    stat = path.stat()
    key = hashlib.sha1(f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|{WAVE_BINS}".encode()).hexdigest()[:24]
    folder = Path(cache_root or Path.home() / ".layerweave" / "view") / "waves"
    cached = folder / f"{key}.json"
    if cached.is_file():
        return json.loads(cached.read_text(encoding="utf-8"))
    with _thumb_slots:
        result = subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "4000", "-f", "s16le", "-"],
                                capture_output=True, timeout=120)
    if result.returncode != 0 or len(result.stdout) < 2:
        return None
    samples = array("h")
    samples.frombytes(result.stdout[: len(result.stdout) // 2 * 2])
    size = max(1, len(samples) // WAVE_BINS)
    rms = []
    for i in range(WAVE_BINS):
        part = samples[i * size:(i + 1) * size]
        rms.append(round((sum(v * v for v in part) / max(1, len(part))) ** 0.5 / 32768, 5))
    folder.mkdir(parents=True, exist_ok=True)
    temp = folder / f"{key}.{os.getpid()}.{threading.get_ident()}.tmp"
    temp.write_text(json.dumps(rms), encoding="utf-8")
    os.replace(temp, cached)
    return rms


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

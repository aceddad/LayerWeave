"""视图读取：只读打开数据库，整理成网页需要的结构；素材文件只提供数据库里引用过的。"""
from pathlib import Path
import sqlite3

from layerweave.support.api import read_project_details, read_record

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


def list_projects(connection):
    return [{"id": row["id"], "name": row["name"], "tips": row["tips"]} for row in read_record(connection, "project")]


def project_view(connection, database, project_id):
    details = read_project_details(connection, project_id)
    if details is None:
        return None
    layers, begin, end = [], None, None
    for layer in order_layers(details["layers"]):
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
            if isinstance(obj["begin"], (int, float)) and isinstance(obj["end"], (int, float)):
                begin = obj["begin"] if begin is None else min(begin, obj["begin"])
                end = obj["end"] if end is None else max(end, obj["end"])
        layers.append({
            "id": layer["id"], "name": layer["name"], "type": layer["type"], "father": layer["father"],
            "depth": layer["depth"], "axis": layer["axis"], "tips": layer["tips"], "objects": objects,
        })
    root_axis = next((layer["axis"] for layer in layers if layer["father"] is None and layer["axis"]), None)
    return {
        "project": {"id": details["project"]["id"], "name": details["project"]["name"], "tips": details["project"]["tips"]},
        "unit": (root_axis or {}).get("unit", ""),
        "extent": [begin or 0, end if end is not None and end > (begin or 0) else (begin or 0) + 10],
        "layers": layers,
    }


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
    """返回视频在 seconds 秒处那一帧的 JPEG 字节；超出时长时取最后一帧附近。"""
    import subprocess
    ffmpeg = ffmpeg or find_ffmpeg()
    if ffmpeg is None:
        raise FileNotFoundError("找不到 ffmpeg：请安装并加入 PATH，或用环境变量 FFMPEG 指定")
    seconds = max(0.0, float(seconds))
    for at in (seconds, max(0.0, seconds - 0.5), 0.0):
        result = subprocess.run([ffmpeg, "-v", "error", "-ss", f"{at:.3f}", "-i", str(path), "-frames:v", "1",
                                 "-vf", f"scale={width}:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "4", "-"],
                                capture_output=True, timeout=60)
        if result.returncode == 0 and result.stdout:
            return result.stdout
    raise RuntimeError(f"ffmpeg 没能取出画面：{result.stderr.decode('utf-8', 'replace')[-200:]}")

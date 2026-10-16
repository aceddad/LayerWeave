"""本机插件清单和显式迁移；不写业务数据库。"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time

from .plugin_manifest import read_manifest

DEFAULT_CATALOG = "https://gitee.com/emotion1354414/layerweave-plugins/raw/main/catalog/index.json"
RECOMMENDED = [
    {"id": "layerweave.assets", "label": "一览", "description": "按种类分页查看图片、视频、音频和文字。"},
    {"id": "layerweave.preview", "label": "预览", "description": "按时间取帧，分页检查视频和动态图像。"},
    {"id": "layerweave.cuts", "label": "接缝", "description": "并排检查前后相接的画面，沿接缝跳转。"},
]
LEGACY = {"cuts": False, "assets": True, "preview": False}
_thread_lock = threading.RLock()


def home(root=None):
    return Path(root if root is not None else Path.home() / ".layerweave" / "view").expanduser().resolve()


def list_path(root=None):
    return home(root) / "plugins.json"


def empty():
    return {"format": 1, "plugins": []}


def read(root=None):
    path = list_path(root)
    if not path.exists():
        return empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"插件清单读不了（{path}）：{error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("plugins"), list) or not all(isinstance(r, dict) for r in data["plugins"]):
        raise ValueError(f"插件清单格式不对：{path}")
    if "format" not in data:
        return legacy_preview(data, root)
    if data["format"] != 1:
        raise ValueError(f"插件清单 format={data['format']} 不受支持；仅支持 1")
    return data


def legacy_preview(data, root):
    result = {**empty(), "migration_pending": True, "preferences": {"layerweave." + k: v for k, v in LEGACY.items()},
              "aliases": {}, "unresolved_legacy": []}
    if "catalog" in data:
        result["catalog"] = data["catalog"]
    seen = set()
    for row in data["plugins"]:
        name = row.get("name", "")
        if name in LEGACY and "path" not in row:
            result["preferences"]["layerweave." + name] = row.get("on") is not False
            continue
        try:
            path = Path(row["path"]).expanduser()
            path = (path if path.is_absolute() else home(root) / "plugins" / path).resolve()
            folder = path.parent
            meta = read_manifest(folder) if (folder / "plugin.json").is_file() else None
            identity = meta["id"] if meta else "local." + name
            from .plugin_manifest import valid_id
            if not valid_id(identity) or identity in seen:
                raise ValueError(f"身份不合规或发生冲突：{identity}")
            seen.add(identity)
            result["plugins"].append({"id": identity, "kind": "view-plugin", "mode": "link", "root": str(folder),
                                      "entry": meta["entry"] if meta else path.name, "on": row.get("on") is not False,
                                      "version": meta["version"] if meta else None})
            result["aliases"][name] = identity
        except (KeyError, TypeError, ValueError, OSError) as error:
            result["unresolved_legacy"].append({"record": row, "problem": str(error)})
    return result


@contextmanager
def locked(root=None):
    """只在显式修改时创建锁文件；OS 锁随进程退出释放。"""
    with _thread_lock:
        folder = home(root)
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / ".plugins.lock").open("a+b") as stream:
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def write(data, root=None):
    path = list_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".plugins-", delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def writable(root=None):
    data = read(root)
    if data.get("migration_pending"):
        raise ValueError("旧插件清单尚未迁移。先查看 list，再显式执行 view_plugin migrate；会保留原清单备份，不自动安装官方插件")
    return data


def migrate(root=None):
    with locked(root):
        data = read(root)
        if not data.get("migration_pending"):
            return {"status": "unchanged", "message": "清单不需要迁移"}
        backup = list_path(root).with_name(f"plugins.pre-v1-{time.time_ns()}.json")
        shutil.copy2(list_path(root), backup)
        data.pop("migration_pending")
        write(data, root)
    return {"status": "migrated", "backup": str(backup), "issues": [{"severity": "warn", "message": i["problem"], "record": i["record"]} for i in data["unresolved_legacy"]],
            "message": "已迁移；原清单已备份，官方插件未自动安装"}


def canonical(identity, root=None):
    if identity in LEGACY:
        return "layerweave." + identity
    return read(root).get("aliases", {}).get(identity, identity)

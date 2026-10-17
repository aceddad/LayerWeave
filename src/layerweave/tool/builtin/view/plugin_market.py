"""静态目录与完整 ZIP 安装；准备成功后才提交本机登记。"""
from .i18n import ViewError

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen
import zipfile

from . import plugin_store as store
from .i18n import read_localizations
from .plugin_manifest import compatibility, inside, manifest, read_manifest, relative_path, valid_id, version_tuple


def location(value, base=None):
    value = str(value)
    if urlsplit(value).scheme in ("http", "https", "file"):
        return value
    if Path(value).is_absolute():
        return Path(value).resolve().as_uri()
    if base:
        return urljoin(base, value)
    return Path(value).expanduser().resolve().as_uri()


def fetch(reference):
    try:
        return urlopen(reference, timeout=30)
    except OSError as error:
        raise ViewError("pluginError.fetch", {"value1": reference, "value2": error}) from error


def catalog_reference(root=None, catalog=None):
    return location(catalog or store.read(root).get("catalog") or store.DEFAULT_CATALOG)


def read_catalog(reference):
    reference = location(reference)
    try:
        with fetch(reference) as stream:
            data = json.load(stream)
    except (UnicodeError, ValueError, OSError) as error:
        raise ViewError("pluginError.catalogRead", {"value1": reference, "value2": error}) from error
    if not isinstance(data, dict) or data.get("format") != 1 or not isinstance(data.get("plugins"), list):
        raise ValueError("目录格式不受支持：需要 format=1 和 plugins 数组")
    releases, issues, seen = [], [], {}
    for number, item in enumerate(data["plugins"]):
        try:
            if not isinstance(item, dict) or not valid_id(item.get("id")):
                raise ValueError("缺少有效的 publisher.name 身份")
            if item.get("kind") != "view-plugin":
                releases.append({**item, "supported": False, "problem": f"此版本尚不支持安装 {item.get('kind')}"})
                continue
            meta = manifest({"format": 1, **item})
            if meta["id"] != item["id"]:
                raise ValueError("id 与 publisher.name 不一致")
            archive = item.get("archive")
            if not isinstance(archive, dict) or not isinstance(archive.get("url"), str):
                raise ValueError("缺少 archive.url")
            digest = archive.get("sha256")
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("archive.sha256 需要 64 位小写十六进制")
            if type(archive.get("size")) is not int or archive["size"] < 1:
                raise ValueError("archive.size 需要正整数 ZIP 字节数")
            address = location(archive["url"], reference)
            if urlsplit(reference).scheme in ("http", "https") and urlsplit(address).scheme not in ("http", "https"):
                raise ValueError("网络目录的发布包必须使用 http/https 地址")
            key = item["id"], item["version"]
            if key in seen:
                if seen[key] != digest:
                    releases = [r for r in releases if (r.get("id"), r.get("version")) != key]
                    seen[key] = None
                    raise ValueError("同 ID、同版本存在不同内容，此版本不能安装")
                continue
            seen[key] = digest
            releases.append({**item, "archive": {**archive, "url": address}, "supported": True,
                             "problem": compatibility(item["requires"])})
        except (TypeError, ValueError, KeyError) as error:
            issues.append({"severity": "error", "index": number, "id": item.get("id") if isinstance(item, dict) else None, "message": str(error)})
    return {"catalog": reference, "releases": releases, "issues": issues}


def select_release(data, identity, version=None):
    rows = [r for r in data["releases"] if r["id"] == identity and (version is None or r.get("version") == version)]
    available = [r for r in rows if r["supported"] and not r["problem"]]
    if not available:
        reasons = "；".join(f"{r.get('version', '?')}: {r['problem']}" for r in rows)
        problems = "；".join(i["message"] for i in data["issues"] if i.get("id") == identity)
        raise ValueError(f"{identity}{' ' + version if version else ''} 没有可安装版本：{reasons or problems or '目录中不存在'}")
    return max(available, key=lambda r: version_tuple(r["version"]))


def digest_file(path):
    with Path(path).open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"size": Path(path).stat().st_size, "sha256": digest}


def download(release, root=None):
    archive = release["archive"]
    folder = store.home(root) / "plugins" / ".cache"
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / (archive["sha256"] + ".zip")
    if destination.is_file() and digest_file(destination) == {k: archive[k] for k in ("size", "sha256")}:
        return destination
    with tempfile.NamedTemporaryFile(dir=folder, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with fetch(archive["url"]) as source:
                shutil.copyfileobj(source, stream)
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        actual = digest_file(temporary)
        for key in ("size", "sha256"):
            if actual[key] != archive[key]:
                raise ValueError(f"发布包 {key} 不符：目录 {archive[key]}，实际 {actual[key]}")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def unpack(path, folder):
    try:
        with zipfile.ZipFile(path) as archive:
            seen = set()
            for entry in archive.infolist():
                relative = relative_path(entry.filename)
                if stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError(f"ZIP 不支持符号链接：{entry.filename}")
                key = relative.casefold() if os.name == "nt" else relative
                if key in seen:
                    raise ValueError(f"ZIP 文件路径重复：{relative}")
                seen.add(key)
                target = inside(folder, relative)
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
    except (zipfile.BadZipFile, RuntimeError) as error:
        raise ViewError("pluginError.zipRead", {"value1": error}) from error
    return read_manifest(folder)


def check_release(meta, release):
    if release is not None:
        for key in ("id", "kind", "publisher", "name", "version", "requires", "label", "description"):
            if meta[key] != release[key]:
                raise ValueError(f"包内 {key} 与目录不一致")
    if problem := compatibility(meta["requires"]):
        raise ValueError(problem)


def same_source(a, b):
    return a.get("type") == b.get("type") and (a.get("type") == "file" or a.get("catalog") == b.get("catalog"))


def read_receipt(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("origin"), dict):
            raise ValueError("需要身份、版本和来源对象")
        return data
    except (OSError, ValueError) as error:
        raise ValueError(f"安装收据读不了：{path.name}：{error}") from error


def install(*, identity=None, version=None, catalog=None, file=None, root=None, updating=False):
    if file is not None and (identity or version or catalog):
        raise ValueError("install --file 不同时传 ID、--version 或 --catalog；身份由包内声明提供")
    release = None
    if file is not None:
        package = Path(file).expanduser().resolve()
        origin = {"type": "file", "archive": str(package), **digest_file(package)}
    else:
        if not valid_id(identity):
            raise ValueError("安装需要完整 ID，例如 layerweave.preview")
        reference = catalog_reference(root, catalog)
        current = next((r for r in store.read(root)["plugins"] if r.get("id") == identity), None)
        if current:
            origin = current.get("origin", {})
            if current.get("mode") != "managed" or origin.get("type") != "catalog" or origin.get("catalog") != reference:
                raise ValueError(f"{identity} 已从其他来源登记：{origin or current.get('root')}；先 remove 再明确安装新来源")
            if version is None and not updating:
                return {"status": "unchanged", "id": identity, "version": current["version"], "message": "已安装；更新请用 update"}
        data = read_catalog(reference)
        release = select_release(data, identity, version)
        if current and updating and version_tuple(release["version"]) <= version_tuple(current["version"]):
            return {"status": "unchanged", "id": identity, "version": current["version"], "message": "没有更新的兼容版本"}
        package = download(release, root)
        origin = {"type": "catalog", "catalog": data["catalog"], **release["archive"]}
        origin["archive"] = origin.pop("url")
    store.writable(root)  # 旧清单需先经用户显式迁移。
    staging = store.home(root) / "plugins" / ".staging"
    staging.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=staging) as temporary:
        prepared = Path(temporary) / "package"
        prepared.mkdir()
        meta = unpack(package, prepared)
        check_release(meta, release)
        identity, version = meta["id"], meta["version"]
        with store.locked(root):
            data = store.writable(root)
            current = next((r for r in data["plugins"] if r.get("id") == identity), None)
            if current and (current.get("mode") != "managed" or not same_source(current.get("origin", {}), origin)):
                raise ValueError(f"{identity} 已从其他来源登记；先 remove 再明确安装新来源")
            if current and updating and version_tuple(version) <= version_tuple(current["version"]):
                return {"status": "unchanged", "id": identity, "version": current["version"], "message": "当前版本已更新，无需再次切换"}
            parent = store.home(root) / "plugins" / "_managed" / ("pkg-" + identity)
            destination = parent / version
            receipt = parent / (version + ".receipt.json")
            if destination.exists():
                if not receipt.is_file():
                    raise ValueError(f"目标目录已存在且没有安装收据：{destination}")
                saved = read_receipt(receipt)
                if saved.get("id") != identity or saved.get("version") != version or saved["origin"].get("sha256") != origin["sha256"]:
                    raise ValueError("同版本内容冲突，不能覆盖；发布者需要升版本")
                if current and current.get("version") == version and current.get("origin", {}).get("sha256") == origin["sha256"]:
                    return {"status": "unchanged", "id": identity, "version": version, "message": "已安装相同版本，未重写文件"}
            else:
                parent.mkdir(parents=True, exist_ok=True)
                os.replace(prepared, destination)
                receipt.write_text(json.dumps({"id": identity, "version": version, "origin": origin}, ensure_ascii=False, indent=2), encoding="utf-8")
            row = {"id": identity, "kind": "view-plugin", "mode": "managed", "version": version,
                   "root": str(destination), "entry": meta["entry"], "on": current["on"] if current else data.get("preferences", {}).get(identity, True), "origin": origin}
            data["plugins"] = [row if r.get("id") == identity else r for r in data["plugins"]]
            if current is None:
                data["plugins"].append(row)
            store.write(data, root)
    return {"status": "updated" if current else "installed", "id": identity, "version": version, "path": str(destination),
            "message": "已登记安装；页面加载结果由浏览器另行报告", "runtime": "unverified"}


def update(identity=None, *, root=None):
    rows = store.writable(root)["plugins"]
    if identity and not any(r.get("id") == identity for r in rows):
        raise ValueError(f"没有安装 {identity}")
    results = []
    for row in rows:
        if identity and row.get("id") != identity:
            continue
        if row.get("mode") != "managed" or row.get("origin", {}).get("type") != "catalog":
            results.append({"id": row["id"], "status": "skipped", "message": "开发链接或离线安装没有目录更新来源"})
            continue
        try:
            results.append(install(identity=row["id"], catalog=row["origin"]["catalog"], root=root, updating=True))
        except (OSError, ValueError) as error:
            results.append({"id": row["id"], "status": "failed", "message": str(error)})
    return {"results": results, "status": "failed" if any(r["status"] == "failed" for r in results) else "completed"}


def market(identity=None, *, catalog=None, root=None):
    data = read_catalog(catalog_reference(root, catalog))
    installed = {r.get("id"): r for r in store.read(root)["plugins"]}
    groups = {}
    for release in data["releases"]:
        if identity and release["id"] != identity:
            continue
        groups.setdefault(release["id"], []).append(release)
    items = []
    for key, rows in groups.items():
        usable = [r for r in rows if r["supported"] and not r["problem"]]
        chosen = max(usable, key=lambda r: version_tuple(r["version"])) if usable else rows[0]
        item = {k: chosen.get(k) for k in ("id", "kind", "label", "description", "version", "supported", "problem", "localizations")}
        item["installed_version"] = installed.get(key, {}).get("version")
        item["compatible"] = bool(usable)
        if identity:
            item["versions"] = rows
        items.append(item)
    return {"items": items, "catalog": data["catalog"], "issues": data["issues"]}


def info(identity, *, version=None, catalog=None, root=None):
    current = next((r for r in store.read(root)["plugins"] if r.get("id") == identity), None)
    if current is not None and version is None and catalog is None:
        folder = Path(current["root"])
        if not (folder / "plugin.json").is_file():
            return {"id": identity, "record": current, "manifest": None, "usage": "本地开发链接没有 plugin.json；未声明参数和兼容范围。"}
        meta = read_manifest(folder)
        localizations, warnings = read_localizations(folder, meta, include_usage=True)
        return {"id": identity, "record": current, "manifest": meta, "usage": inside(folder, meta["usage"]).read_text(encoding="utf-8"),
                "localizations": localizations, "language_warnings": warnings}
    data = read_catalog(catalog_reference(root, catalog or (current or {}).get("origin", {}).get("catalog")))
    if version:
        choices = [r for r in data["releases"] if r["id"] == identity and r.get("version") == version and r["supported"]]
        if not choices:
            raise ValueError(f"目录没有可读取的视图插件 {identity} {version}")
        release = choices[0]  # 详情允许解释一个不兼容的版本，不执行它。
    else:
        release = select_release(data, identity)
    package = download(release, root)
    with tempfile.TemporaryDirectory(prefix="layerweave-plugin-info-") as temporary:
        meta = unpack(package, temporary)
        for key in ("id", "version", "requires"):
            if meta[key] != release[key]:
                raise ValueError(f"包内 {key} 与目录不一致")
        usage = inside(temporary, meta["usage"]).read_text(encoding="utf-8")
        localizations, warnings = read_localizations(temporary, meta, include_usage=True)
    return {"id": identity, "manifest": meta, "usage": usage, "catalog": data["catalog"], "problem": compatibility(meta["requires"]), "localizations": localizations, "language_warnings": warnings}


def remove(identity, *, files=False, root=None):
    with store.locked(root):
        data = store.writable(root)
        row = next((r for r in data["plugins"] if r.get("id") == identity), None)
        if row is None:
            raise ValueError(f"清单里没有 {identity}")
        moved = None
        reason = None
        if files:
            parent = store.home(root) / "plugins" / "_managed" / ("pkg-" + identity)
            expected = parent / str(row.get("version"))
            receipts = list(parent.glob("*.receipt.json")) if parent.is_dir() else []
            owned = row.get("mode") == "managed" and Path(row["root"]).resolve() == expected.resolve() and receipts
            if owned:
                try:
                    owned = not parent.is_symlink() and all(read_receipt(p).get("id") == identity for p in receipts)
                except (ValueError, OSError):
                    owned = False
            if owned:
                trash = store.home(root) / "plugins" / ".trash"
                trash.mkdir(parents=True, exist_ok=True)
                moved = trash / f"pkg-{identity}-{time.time_ns()}"
                os.replace(parent, moved)
            else:
                reason = "文件不是安装器拥有的目录，仅解除登记"
        data["plugins"] = [r for r in data["plugins"] if r.get("id") != identity]
        try:
            store.write(data, root)
        except BaseException:
            if moved:
                os.replace(moved, parent)
            raise
    return {"removed": identity, "status": "removed", "recycled": str(moved) if moved else None, "message": reason or "已解除登记"}

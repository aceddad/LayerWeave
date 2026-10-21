"""Versioned example sources. Only immutable downloads live in the cache."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from urllib.request import urlopen
import zipfile

DATA = Path(__file__).with_name("data")
SOURCE = Path(__file__).resolve().parents[6]


def catalog():
    if (DATA / "catalog.json").is_file():
        return json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))
    return source_catalog(SOURCE)


def source_catalog(root):
    """Editable installs and the wheel build share the same discovery logic."""
    config = json.loads((root / "distribution/demos.json").read_text(encoding="utf-8"))
    items = []
    for path in sorted((root / "examples/showcases").glob("*/project.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        name = path.parent.name
        items.append({"name": name, "title": document.get("name", name),
                      "when": document.get("when", ""), "bundled": name in config["bundled"]})
    return {"format": 1, "archive": config["archive"], "items": items}


def cache_root():
    if os.environ.get("LAYERWEAVE_CACHE_DIR"):
        return Path(os.environ["LAYERWEAVE_CACHE_DIR"]).expanduser()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "LayerWeave/cache"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "layerweave"


def cached_archive(spec, *, cache=None):
    root = Path(cache) if cache is not None else cache_root()
    root.mkdir(parents=True, exist_ok=True)
    target = root / (spec["sha256"] + ".zip")
    if target.is_file():
        with target.open("rb") as cached:
            if hashlib.file_digest(cached, "sha256").hexdigest() == spec["sha256"]:
                return target
    descriptor, temporary = tempfile.mkstemp(prefix="download-", suffix=".zip", dir=root)
    path = Path(temporary)
    try:
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "wb") as output, urlopen(spec["url"], timeout=60) as response:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != spec["sha256"]:
            raise ValueError("案例包校验失败；请重新运行。Example archive checksum mismatch; retry the command.")
        path.replace(target)
        return target
    finally:
        path.unlink(missing_ok=True)


def extract_case(archive, name, destination):
    prefix = "showcases/" + name + "/"
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            if not member.filename.startswith(prefix):
                continue
            relative = member.filename[len(prefix):].replace("\\", "/")
            target = (destination / relative).resolve()
            if not target.is_relative_to(destination.resolve()) or (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("案例包含不安全路径 / Unsafe example archive path")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(member) as input_, target.open("wb") as output:
                    shutil.copyfileobj(input_, output)
    if not (destination / "project.json").is_file():
        raise ValueError("案例包缺少 project.json / Missing project.json in example archive")


def copy_example(name, destination, *, cache=None):
    data = catalog()
    item = next((item for item in data["items"] if item["name"] == name), None)
    if item is None:
        raise ValueError("未知案例 / Unknown example: " + name + "; use: layerweave demo --list")
    if item["bundled"]:
        bundled = DATA / (name + ".zip")
        if bundled.is_file():
            extract_case(bundled, name, destination)
        else:
            shutil.copytree(SOURCE / "examples/showcases" / name, destination, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.sqlite3*", "*.db", "*.log", ".env*", "keys.json", "keys.local.json"))
    else:
        extract_case(cached_archive(data["archive"], cache=cache), name, destination)
    # Selected examples live independently of the source tree's parent README.
    guide = "https://github.com/aceddad/LayerWeave/blob/v" + data["archive"]["version"] + "/examples/showcases/README.md"
    for readme in destination.glob("README*.md"):
        original = readme.read_text(encoding="utf-8")
        standalone = original.replace("](../README.md", "](" + guide)
        if standalone != original:
            readme.write_text(standalone, encoding="utf-8")

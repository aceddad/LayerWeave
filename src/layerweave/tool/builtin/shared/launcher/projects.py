"""Prepare once, then reopen the same database. Only new folders are populated."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile

from layerweave.support.api import initialize_database, open_database, read_record

MARKER = "layerweave.json"


def existing(directory, *, kind=None, name=None):
    directory = Path(directory).expanduser().resolve()
    marker = directory / MARKER
    if not marker.is_file():
        raise ValueError(f"目录没有 layerweave.json；已有数据库请用 view 指定文件，新建请换目录 / Choose another directory for a new project, or use view PATH.sqlite3: {directory}")
    data = json.loads(marker.read_text(encoding="utf-8"))
    if data.get("format") != 1 or (kind and data.get("kind") != kind) or (name and data.get("name") != name):
        raise ValueError(f"目录属于另一个项目 / Directory belongs to a different project: {directory}")
    database = directory / "project.sqlite3"
    verify_database(database, data["project_id"])
    return {"directory": directory, "database": database, "project_id": data["project_id"], "created": False}


def verify_database(database, project_id=None):
    database = Path(database).expanduser().resolve()
    if not database.is_file():
        raise ValueError(f"数据库不存在 / Database not found: {database}")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        if project_id is not None and read_record(connection, "project", id=project_id) is None:
            raise ValueError(f"项目不存在 / Project not found: {project_id}")
        if project_id is None:
            read_record(connection, "project")
    return database


def prepare(directory, kind, name, populate):
    directory = Path(directory).expanduser().resolve()
    if directory.exists():
        return existing(directory, kind=kind, name=name)
    directory.parent.mkdir(parents=True, exist_ok=True)
    # Build next to the destination, then rename the completed folder atomically.
    with tempfile.TemporaryDirectory(prefix=".layerweave-", dir=directory.parent) as temporary:
        staging = Path(temporary) / "project"
        staging.mkdir()
        document = populate(staging)
        from layerweave.tool.builtin.usage.exchange import import_project
        database = initialize_database(staging / "project.sqlite3")
        with closing(open_database(database)) as connection:
            result = import_project(connection, document, new_project=True)
        if not result["ok"]:
            raise ValueError("导入失败 / Import failed: " + json.dumps(result.get("error"), ensure_ascii=False))
        metadata = {"format": 1, "kind": kind, "name": name, "project_id": result["data"]["project_id"]}
        (staging / MARKER).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            staging.rename(directory)
        except FileExistsError:
            return existing(directory, kind=kind, name=name)
    return {"directory": directory, "database": directory / "project.sqlite3",
            "project_id": metadata["project_id"], "created": True,
            "issues": [*result["data"].get("issues", []), *result["checks"].get("issues", [])]}


def prepare_demo(name="article-reading", directory=None, *, cache=None):
    from .catalog import copy_example
    def populate(staging):
        copy_example(name, staging, cache=cache)
        return json.loads((staging / "project.json").read_text(encoding="utf-8"))
    return prepare(directory or Path.cwd() / "layerweave-demo" / name, "demo", name, populate)


def prepare_new(directory, template="subtitles"):
    def populate(staging):
        from layerweave.tool.builtin.usage.exchange import template_help
        result = template_help(template)
        if not result["items"]:
            raise ValueError(str(result["issues"]))
        document = result["items"][0]["document"]
        (staging / "project.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return document
    return prepare(directory, "template", template, populate)

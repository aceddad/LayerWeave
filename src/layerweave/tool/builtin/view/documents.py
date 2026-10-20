"""Explicit, process-local mounts for HTML documents and their relative resources."""
from pathlib import Path
import secrets
import threading
from urllib.parse import quote

from .i18n import ViewError


class DocumentMounts:
    def __init__(self, base):
        self.base = Path(base)
        self.roots = {}
        self.lock = threading.Lock()

    def _path(self, value):
        path = Path(value).expanduser()
        return (self.base / path).resolve() if not path.is_absolute() else path.resolve()

    def open(self, file, root=None):
        if not isinstance(file, str) or not file.strip():
            raise ViewError("document.fileRequired")
        page = self._path(file)
        if page.suffix.lower() not in (".html", ".htm"):
            raise ViewError("document.htmlOnly")
        if not page.is_file():
            raise ViewError("document.fileMissing", {"value1": file})
        folder = self._path(root) if root else page.parent
        if not folder.is_dir() or not page.is_relative_to(folder):
            raise ViewError("document.root")
        with self.lock:
            token = next((key for key, value in self.roots.items() if value == folder), None)
            if token is None:
                token = secrets.token_urlsafe(18)
                self.roots[token] = folder
        return {"url": f"/documents/{token}/{quote(page.relative_to(folder).as_posix())}", "name": page.name}

    def resolve(self, token, relative):
        with self.lock:
            folder = self.roots.get(token)
        if folder is None:
            return None
        path = (folder / relative.replace("\\", "/")).resolve()
        return path if path.is_relative_to(folder) and path.is_file() else None

"""Generate launcher resources from the canonical examples during wheel builds."""
import json
from fnmatch import fnmatch
from pathlib import Path
import runpy
import zipfile
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent


def demo_catalog(root=ROOT):
    module = runpy.run_path(str(root / "src/layerweave/tool/builtin/shared/launcher/catalog.py"))
    return module["source_catalog"](root)


class BuildPy(build_py):
    def run(self):
        super().run()
        if getattr(self, "editable_mode", False):
            return  # Editable installs discover examples directly from their source.
        target = Path(self.build_lib) / "layerweave/tool/builtin/shared/launcher/data"
        target.mkdir(parents=True, exist_ok=True)
        catalog = demo_catalog()
        (target / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for item in catalog["items"]:
            if not item["bundled"]:
                continue
            source = ROOT / "examples/showcases" / item["name"]
            with zipfile.ZipFile(target / (item["name"] + ".zip"), "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(source.rglob("*")):
                    if (path.is_file() and "__pycache__" not in path.parts and not any(fnmatch(path.name, pattern)
                        for pattern in ("*.pyc", "*.sqlite3*", "*.db", "*.log", ".env*", "keys.json", "keys.local.json"))):
                        info = zipfile.ZipInfo("showcases/" + item["name"] + "/" + path.relative_to(source).as_posix())
                        info.compress_type = zipfile.ZIP_DEFLATED
                        archive.writestr(info, path.read_bytes())

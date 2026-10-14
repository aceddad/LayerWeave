"""用法：python tests/check_wheel.py <wheel>。普通安装与完整资源验收，全部使用临时目录。"""
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import tempfile
from zipfile import ZipFile

from test_namespace import COMMON_NAMES, ROOT, SMOKE, make_host_modules


def check(wheel):
    package = ROOT / "src/layerweave"
    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
        roots = {name.split("/", 1)[0] for name in names}
        assert len(roots) == 2 and "layerweave" in roots
        assert all(name == "layerweave" or name.endswith(".dist-info") for name in roots), roots
        metadata = next(name for name in names if name.endswith(".dist-info/top_level.txt"))
        assert archive.read(metadata).decode().splitlines() == ["layerweave"]
        key_template = json.loads(archive.read("layerweave/tool/builtin/developer/keys/example.json"))
        assert all(record["key"] == "" for record in key_template.values())
        assert not any(name.endswith(("/keys.local.json", "/keys.json")) for name in names)
        resources = [package / "support/storage/schema.sql", package / "tool/README.md", package / "tool/builtin/developer/keys/example.json",
                     package / "tool/builtin/developer/keys/README.md"]
        resources += [p for folder in ("configs", "tool/skills") for p in (package / folder).rglob("*")
                      if p.is_file() and "__pycache__" not in p.parts]
        resources += list(package.rglob("component.toml"))
        resources.append(package / "tool/builtin/developer/versions/README.md")
        resources.append(package / "support/numbering/README.md")
        for path in resources:
            member = "layerweave/" + path.relative_to(package).as_posix()
            assert member in names, f"Missing package resource: {member}"
            assert archive.read(member) == path.read_bytes(), f"Outdated resource: {member}"
        for name in names:
            if not name.startswith("layerweave/tool/skills/") or not name.endswith(".md"):
                continue
            text = re.sub(r"```.*?```", "", archive.read(name).decode("utf-8"), flags=re.S)
            for destination in re.findall(r"\]\(([^)]+)\)", text):
                if "://" in destination or destination.startswith("#"):
                    continue
                linked = posixpath.normpath(posixpath.join(posixpath.dirname(name), destination.split("#")[0]))
                assert linked in names, f"Missing installed skill guide: {name} -> {destination}"
        assert not any(name.startswith(tuple(prefix + "/" for prefix in (*COMMON_NAMES, "tests", "scratch"))) for name in names)
        print(f"wheel contents: one import root; {len(resources)} resources match source")

    with tempfile.TemporaryDirectory(prefix="layerweave-wheel-") as folder:
        root = Path(folder)
        installed, host = root / "installed", root / "host"
        host.mkdir()
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        result = subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--no-compile",
                                 "--target", str(installed), str(wheel)], cwd=host, env=env,
                                capture_output=True, text=True, encoding="utf-8", timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
        make_host_modules(host)
        bootstrap = f'import sys\nsys.path.insert(0, {str(installed)!r})\n'
        origin = f'''\nimport layerweave
assert str(layerweave.__file__).startswith({str(installed)!r}), layerweave.__file__
assert {str(ROOT)!r} not in sys.path
'''
        run = subprocess.run([sys.executable, "-X", "utf8", "-B", "-S", "-c", bootstrap + SMOKE + origin],
                             cwd=host, env=env, capture_output=True, text=True, encoding="utf-8", timeout=45)
        assert run.returncode == 0, run.stdout + run.stderr
        print("ordinary install: " + run.stdout.strip())
        command = bootstrap + '\nimport runpy\nsys.argv=["command_help", "--json"]\nrunpy.run_module("layerweave.tool.builtin.shared.help.command_help",run_name="__main__")'
        run = subprocess.run([sys.executable, "-X", "utf8", "-B", "-S", "-c", command], cwd=host,
                             env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert run.returncode == 0, run.stdout + run.stderr
        data = json.loads(run.stdout)
        assert data["status"] == "completed" and len(data["items"]) == 38, data
        print("ordinary install CLI: 38 commands discovered, no editable source fallback")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python tests/check_wheel.py PATH_TO_WHEEL")
    check(Path(sys.argv[1]).resolve())

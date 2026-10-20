"""用法：python -m tests.packaging.check_wheel <wheel>。普通安装与完整资源验收，全部使用临时目录。"""
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import tempfile
from zipfile import ZipFile

from tests._support.namespace import COMMON_NAMES, ROOT, SMOKE, make_host_modules
from tests._support.distribution import local_only


def check(wheel):
    package = ROOT / "src/layerweave"
    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert not any(local_only(name) for name in names), [name for name in names if local_only(name)]
        roots = {name.split("/", 1)[0] for name in names}
        assert len(roots) == 2 and "layerweave" in roots
        assert all(name == "layerweave" or name.endswith(".dist-info") for name in roots), roots
        metadata = next(name for name in names if name.endswith(".dist-info/top_level.txt"))
        assert archive.read(metadata).decode().splitlines() == ["layerweave"]
        from email import message_from_bytes
        metadata_text=message_from_bytes(archive.read(next(n for n in names if n.endswith('.dist-info/METADATA'))))
        assert 'MIT' in metadata_text['License-Expression']
        assert set(metadata_text.get_all('License-File'))=={'LICENSE','THIRD_PARTY_NOTICES.md'}
        for license_name in ('LICENSE','THIRD_PARTY_NOTICES.md'):
            installed_license=next(n for n in names if n.endswith('.dist-info/licenses/'+license_name))
            assert archive.read(installed_license)==(ROOT/license_name).read_bytes()
        key_template = json.loads(archive.read("layerweave/tool/builtin/developer/keys/example.json"))
        assert all(record["key"] == "" for record in key_template.values())
        assert not any(name.endswith(("/keys.local.json", "/keys.json")) for name in names)
        assert not any(name.startswith("layerweave/tool/builtin/view/plugins/") for name in names), "官方插件不能随宿主分发"
        for subtree in ("web", "sdk", "locales"):
            prefix = f"layerweave/tool/builtin/view/{subtree}/"
            expected = {"layerweave/" + p.relative_to(package).as_posix() for p in (package / "tool/builtin/view" / subtree).rglob("*") if p.is_file()}
            actual = {name for name in names if name.startswith(prefix) and not name.endswith("/")}
            assert actual == expected, f"{subtree} 资源与源码不一致；请清理旧 build 生成物后重建：{actual ^ expected}"
        resources = [package / "support/storage/schema.sql", package / "tool/README.md", package / "tool/builtin/developer/keys/example.json",
                     package / "tool/builtin/developer/keys/README.md"]
        resources += [p for folder in ("configs", "tool/skills") for p in (package / folder).rglob("*")
                      if p.is_file() and "__pycache__" not in p.parts]
        resources += list(package.rglob("component.toml"))
        resources.append(package / "tool/builtin/developer/versions/README.md")
        resources.append(package / "support/numbering/README.md")
        resources += list((package / "tool/builtin/usage/exchange/templates").glob("*.json"))
        resources += list((package / "tool/builtin/usage/exchange").glob("*.md"))
        resources += list((package / "tool/builtin/view").glob("*.md"))
        resources += [p for p in (package / "tool/builtin/view/sdk").rglob("*") if p.is_file()]
        resources += list((package / "tool/builtin/view/locales").glob("*.json"))
        resources.append(package / "tool/builtin/view/layout-defaults.json")
        resources += list(package.rglob('*.md'))
        resources += [p for p in (package / "tool/builtin/view/web").rglob("*") if p.is_file()]
        resources = sorted({p for p in resources if not local_only(p.relative_to(package).as_posix())})
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
from importlib.metadata import version
assert layerweave.__version__ == version('layerweave')
from layerweave.tool.builtin.view.layout import arrange
from layerweave.support.api import initialize_database, open_database, transaction
from tempfile import TemporaryDirectory
from pathlib import Path
from contextlib import closing
with TemporaryDirectory() as folder:
    database = initialize_database(Path(folder) / 'layout.sqlite3')
    with closing(open_database(database)) as connection, transaction(connection) as write:
        project = write.create('project', dict(name='installed layout'))['id']
        layer = write.create('layer', dict(type='text', config_ref='layers/text.toml', axis=dict(unit='序号', precision=1)), project_id=project)['id']
    result = arrange(database, project, 'resize', root=layer, width=900, lane_height=180)
    assert result['operation_id'] and result['boards'][0]['width'] == 900, result
    assert arrange(database, project)['boards'][0]['height'] == 248
print('shared layout resource and headless resize passed')
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
        assert data["status"] == "completed" and len(data["items"]) == 46, data
        print("ordinary install CLI: 46 commands discovered, no editable source fallback")
        zero = bootstrap + '''
import tempfile
from layerweave.tool.builtin.view.plugins import list_plugins
with tempfile.TemporaryDirectory() as folder:
    result = list_plugins(folder)
    assert result['plugins'] == [] and not result['problem'], result
print('ordinary install: zero plugins; host available without official payloads')
'''
        run = subprocess.run([sys.executable, "-X", "utf8", "-B", "-S", "-c", zero], cwd=host, env=env,
                             capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert run.returncode == 0, run.stdout + run.stderr
        print(run.stdout.strip())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m tests.packaging.check_wheel PATH_TO_WHEEL")
    check(Path(sys.argv[1]).resolve())

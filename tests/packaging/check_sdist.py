"""解包源码发行物，在隔离目录重建带本地状态排除检查的 wheel。"""
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
from zipfile import ZipFile

from tests._support.distribution import local_only
from tests.packaging.check_wheel import check as check_wheel


def check(archive):
    with tempfile.TemporaryDirectory(prefix='layerweave-sdist-') as folder:
        temporary=Path(folder)
        with tarfile.open(archive,'r:gz') as bundle:
            members=bundle.getmembers()
            roots={PurePosixPath(m.name).parts[0] for m in members}
            assert len(roots)==1,roots
            names={PurePosixPath(m.name).relative_to(next(iter(roots))).as_posix() for m in members}
            required={'LICENSE','THIRD_PARTY_NOTICES.md','README.md','pyproject.toml','MANIFEST.in',
                'src/layerweave/support/storage/schema.sql','frontend/view/package-lock.json',
                'frontend/view/src/plugin/host.ts','frontend/view/tools/third-party-notices.mjs',
                'tests/_support/mcpfixture.py','tests/fixtures/view-plugin/parts/label.js',
                'docs/releasing.md','examples/read_write.py'}
            assert required<=names,required-names
            assert not any(local_only(name) for name in names),[n for n in names if local_only(n)]
            for member in members:
                dest=temporary/member.name
                assert dest.resolve().is_relative_to(temporary.resolve()) and not member.issym() and not member.islnk()
                if member.isdir(): dest.mkdir(parents=True,exist_ok=True)
                elif member.isfile():
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    with bundle.extractfile(member) as source: dest.write_bytes(source.read())
                else: raise AssertionError('Unexpected archive member: '+member.name)
        source=temporary/next(iter(roots))
        # 仅向临时副本放入假的本地文件，证明资源通配符不会重新打包它们。
        skill=source/'src/layerweave/tool/skills/layers/text/text-normalize'
        for name in ('.env','keys.local.json','keys.json','.keys.local.json.sentinel.tmp','local.sqlite3','trace.log','__pycache__/local.pyc'):
            dest=skill/name; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text('test sentinel; no credentials',encoding='utf-8')
        result=subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation',
            '--disable-pip-version-check','--no-cache-dir','--wheel-dir',str(temporary/'wheels'),str(source)],
            capture_output=True,text=True,encoding='utf-8',timeout=180)
        assert result.returncode==0,result.stdout+result.stderr
        wheel=next((temporary/'wheels').glob('*.whl'))
        with ZipFile(wheel) as rebuilt:
            assert not any(local_only(n) for n in rebuilt.namelist())
        check_wheel(wheel)
        print('sdist: complete sources, test fixtures, licenses, clean wheel rebuild and local-file exclusion passed')


if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Usage: python -m tests.packaging.check_sdist PATH_TO_SDIST')
    check(Path(sys.argv[1]).resolve())

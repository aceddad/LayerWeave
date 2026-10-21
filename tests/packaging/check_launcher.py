"""Verify the bundled starter and persistent projects from an installed wheel."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile


def check(wheel):
    with ZipFile(wheel) as package:
        assert 'layerweave/tool/builtin/shared/launcher/data/article-reading.zip' in package.namelist()
        assert 'layerweave/tool/builtin/shared/launcher/data/catalog.json' in package.namelist()
    with tempfile.TemporaryDirectory(prefix='lw-launcher-wheel-') as folder:
        root = Path(folder)
        target = root/'installed'
        subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-index','--no-deps',
                        '--target',str(target),str(wheel)],check=True,capture_output=True)
        script = f'''
import sys
sys.path.insert(0,{str(target)!r})
import io, json
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import patch
import layerweave
from layerweave.tool.builtin.shared.launcher.catalog import catalog, DATA
from layerweave.tool.builtin.shared.launcher.projects import prepare_demo, prepare_new
from layerweave.tool.builtin.shared.launcher.__main__ import main
from layerweave.support.api import open_database, read_record, transaction, change_cursor
assert Path(layerweave.__file__).is_relative_to({str(target)!r})
assert (DATA/'article-reading.zip').is_file()
assert len(catalog()['items']) == 12
work=Path({str(root/'work')!r})
with patch('urllib.request.urlopen',side_effect=AssertionError('bundled demo must not download')):
    prepared=prepare_demo(directory=work)
with closing(open_database(prepared['database'])) as c:
    rows=read_record(c,'object',project_id=prepared['project_id'])
    assert len(rows)==32
    with transaction(c) as write:
        write.update('object',rows[0]['id'],{{'tips':'preserved'}},project_id=prepared['project_id'])
    cursor=change_cursor(c)
again=prepare_demo(directory=work)
assert not again['created']
with closing(open_database(again['database'])) as c:
    assert change_cursor(c)==cursor
    assert read_record(c,'object',project_id=again['project_id'],id=rows[0]['id'])['tips']=='preserved'
with patch('layerweave.tool.builtin.view.server.serve') as serve, redirect_stdout(io.StringIO()):
    assert main(['view',str(work),'--no-browser'])==0
    assert serve.call_args.kwargs['project']==prepared['project_id']
    assert not serve.call_args.kwargs['open_browser']
assert prepare_new(Path({str(root/'new')!r}))['created']
print('installed launcher: 12-case catalog, offline bundled article, preserved edits, view routing and templates passed')
'''
        result=subprocess.run([sys.executable,'-X','utf8','-B','-S','-c',script],cwd=root,
                              env={**os.environ,'PYTHONPATH':''},capture_output=True,text=True,encoding='utf-8',timeout=60)
        assert result.returncode==0,result.stdout+result.stderr
        print(result.stdout.strip())


if __name__=='__main__':
    check(Path(sys.argv[1]).resolve())

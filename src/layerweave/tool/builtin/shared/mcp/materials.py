"""技能材料适配；读取文档不会执行其中的脚本。"""
from pathlib import Path
from hashlib import sha256
import os

from layerweave.support.paths import SKILLS_ROOT
from layerweave.support.feedback import InputError


def _files(root, name=None):
    for folder, directories, filenames in os.walk(root):
        directories[:] = sorted(d for d in directories if d not in {'node_modules','.git','__pycache__'})
        for filename in sorted(filenames):
            if name is None or filename==name:
                yield Path(folder)/filename


def _metadata(text):
    lines=text.splitlines()
    if not lines or lines[0].strip()!='---':
        return {}
    result={}
    current=None
    for line in lines[1:]:
        if line.strip()=='---':
            break
        if line[:1].isspace() and current:
            result[current]=(result[current]+' '+line.strip()).strip()
        elif ':' in line:
            key,_,value=line.partition(':')
            current=key if key in {'name','description'} else None
            if current:
                result[current]='' if value.strip() in {'','|','>','|-','>-'} else value.strip().strip('"\'')
    return result


def discover_skills(roots=None):
    roots = [SKILLS_ROOT] if roots is None else [Path(x) for x in roots]
    items, issues = [], []
    for root in roots:
        root = root.resolve()
        if not root.is_dir():
            issues.append({'code':'skill_source','source':str(root),'message':'技能目录不存在'})
            continue
        for path in _files(root,'SKILL.md'):
            # 技能正文只是数据；简单读取名称、用途用于发现，不解释执行语义。
            try:
                text = path.read_text(encoding='utf-8-sig')
            except (OSError,UnicodeError) as error:
                issues.append({'code':'skill_metadata','source':str(path),'message':str(error)})
                continue
            relative = path.parent.relative_to(root).as_posix()
            suffix = relative.replace('/','.') if relative!='.' else root.name
            namespace = 'layerweave' if root == SKILLS_ROOT.resolve() else sha256(str(root).encode()).hexdigest()[:12]
            identity = f'skill.{namespace}.{suffix}'
            meta=_metadata(text)
            summary=meta.get('description','')
            name=meta.get('name') or path.parent.name
            items.append({'id':identity,'name':name,'summary':summary or f'读取 {name} 的使用说明',
                          'path':str(path),'root':str(path.parent),'relative':relative})
    return items, issues


def read_skill(item, *, resource=None):
    root = Path(item['root'])
    path = Path(item['path']) if resource is None else (root / resource).resolve()
    if not path.is_relative_to(root.resolve()):
        raise InputError('技能支持文件应位于技能目录内', field='resource')
    body = path.read_text(encoding='utf-8-sig')
    files = [p.relative_to(root).as_posix() for p in _files(root)]
    return {'id':item['id'],'name':item['name'],'path':str(path),'content':body,
            'files':files,'executed':False,'note':'仅加载技能材料，未执行脚本或完成技能任务。'}

"""一次加载的本地配置；默认上下文与能力展示分开。"""
from copy import deepcopy
import json
from pathlib import Path

from layerweave.support.feedback import InputError


def absolute(value, workspace):
    path = Path(value).expanduser()
    return str((path if path.is_absolute() else workspace / path).resolve())


def load_config(value=None):
    base = Path.cwd()
    if isinstance(value, (str, Path)):
        source = Path(value).expanduser().resolve()
        base = source.parent
        value = json.loads(source.read_text(encoding='utf-8-sig'))
    value = deepcopy(value or {})
    if not isinstance(value, dict):
        raise InputError('MCP 配置需要 JSON 对象')
    known = {'workspace','database','project_id','groups','exposure','disabled','sources','installed',
             'include_builtin','skills_roots','limit','max_chars','result_cache_size'}
    extra = set(value) - known
    if extra:
        raise InputError('未知 MCP 配置字段', fields=sorted(extra), allowed=sorted(known))
    value['workspace'] = absolute(value.get('workspace', '.'), base)
    workspace = Path(value['workspace'])
    if value.get('database') is not None:
        value['database'] = absolute(value['database'], workspace)
    if value.get('project_id') is not None and type(value['project_id']) is not int:
        raise InputError('project_id 需要整数')
    groups = value.setdefault('groups', {})
    if not isinstance(groups, dict) or set(groups) - {'enable','disable'}:
        raise InputError('groups 只包含 enable/disable 列表')
    for key in ('enable','disable'):
        if key in groups and (not isinstance(groups[key], list) or not all(isinstance(x, str) for x in groups[key])):
            raise InputError(f'groups.{key} 需要名称列表')
    exposure = value.setdefault('exposure', {})
    if not isinstance(exposure, dict) or any(v not in ('direct','routed') for v in exposure.values()):
        raise InputError('exposure 需要完整身份到 direct/routed 的映射')
    disabled = value.setdefault('disabled', [])
    if not isinstance(disabled, list) or not all(isinstance(x, str) for x in disabled):
        raise InputError('disabled 需要完整命令身份列表')
    value.setdefault('sources', [])
    if not isinstance(value['sources'], list):
        raise InputError('sources 需要来源列表')
    for source in value['sources']:
        if not isinstance(source, dict) or 'path' not in source:
            raise InputError('sources 每项需要 namespace/path')
        source['path'] = absolute(source['path'], workspace)
        if source.get('import_root'):
            source['import_root'] = absolute(source['import_root'], workspace)
    for key in ('installed','include_builtin'):
        value.setdefault(key, True)
        if type(value[key]) is not bool:
            raise InputError(f'{key} 需要布尔值')
    roots = value.get('skills_roots')
    if roots is not None:
        if not isinstance(roots, list):
            raise InputError('skills_roots 需要路径列表')
        value['skills_roots'] = [absolute(x, workspace) for x in roots]
    for key, default in (('limit',100),('max_chars',24000),('result_cache_size',32)):
        value.setdefault(key, default)
        if type(value[key]) is not int or value[key] < (256 if key == 'max_chars' else 1):
            raise InputError(f'{key} 需要有效的正整数')
    return value

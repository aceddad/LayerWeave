"""发行物中不能携带的本地状态；只用于构建验收。"""
from pathlib import PurePosixPath


def local_only(name):
    path=PurePosixPath(name)
    parts={part.casefold() for part in path.parts}
    leaf=path.name.casefold()
    return bool(parts & {'__pycache__','.venv','node_modules','.git','.pytest_cache','scratch','output'}) or (
        leaf in {'keys.local.json','keys.json','.env','.ds_store'} or leaf.startswith(('.env.','.keys.local.json.'))
        or leaf.endswith(('.pyc','.pyo','.sqlite3','.db','.log')) or '.sqlite3-' in leaf)

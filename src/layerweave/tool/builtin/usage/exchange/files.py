"""普通 JSON 文件与随包模板；直接传路径可使用任意工作目录里的文件。"""
from pathlib import Path
import json

from .format import document_value


TEMPLATE_ROOT = Path(__file__).parent / "templates"


def load_document(path):
    return document_value(json.loads(Path(path).read_text(encoding="utf-8-sig")))


def save_document(document, path):
    text = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path.resolve())


def export_to_file(connection, project_id, output, *, overwrite=False, **options):
    """显式文件包装；普通 JSON 导出不依赖本函数。"""
    from .exporting import export_project
    document = export_project(connection, project_id, **options)
    path = Path(output).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
    with path.open('w' if overwrite else 'x', encoding='utf-8') as stream:
        stream.write(text)
    return {'path': str(path), 'counts': document['counts'], 'scope': document['scope'],
            'overwritten': overwrite, 'document_complete': True}


def import_from_file(connection, document_file, **options):
    from .importing import import_project
    return import_project(connection, load_document(document_file), **options)


def template_help(name=None, *, template_root=None):
    """不传名称只列用途与路径；传名称返回那一份模板，新增 JSON 自动发现。"""
    root = TEMPLATE_ROOT if template_root is None else Path(template_root)
    if not root.is_dir():
        raise ValueError(f"模板目录不存在：{root}")
    items, issues = [], []
    for path in sorted(root.rglob("*.json")):
        key = path.relative_to(root).with_suffix("").as_posix()
        if name is not None and key != name:
            continue
        try:
            document = load_document(path)
            item = {"name": key, "title": document.get("name", key), "when": document.get("when", ""), "path": str(path.resolve())}
            if name is not None:
                item["document"] = document
            items.append(item)
        except (OSError, ValueError) as error:
            issues.append({"severity": "warn", "template": key, "message": str(error)})
    if name is not None and not items and not issues:
        raise ValueError(f"没有找到模板 {name}；先查询模板总览")
    return {"status": "partial" if issues else "completed", "items": items, "issues": issues}

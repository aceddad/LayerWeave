"""Name-based reading routes using installed LayerWeave public tools.

The edit-undo route always edits a new SQLite backup beside the input database.
It never edits the input database or the Markdown assets.
"""
from pathlib import Path
from contextlib import closing
import argparse
import copy
import json
import sqlite3
import uuid

from layerweave.support.api import open_database, read_record
from layerweave.tool.builtin.usage.query.project_overview import project_overview
from layerweave.tool.builtin.usage.query.project_details import project_details
from layerweave.tool.builtin.usage.query.find_objects import find_objects
from layerweave.tool.builtin.usage.query.relations import query_relations
from layerweave.tool.builtin.usage.query.walk import walk_relations
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.tool.builtin.usage.undo.service import undo_operation

PROJECT_NAME = '留下那声咔哒｜翻译与校对'


def choose_project(connection, explicit=None):
    if explicit is not None:
        result = read_record(connection, 'project', id=explicit)
        if result is None:
            raise ValueError('指定项目不存在')
        return result['id']
    projects = read_record(connection, 'project', filters={'name': PROJECT_NAME})
    if len(projects) != 1:
        raise ValueError('请用 --project-id 指定导入结果中的项目编号，避免选错同名项目')
    return projects[0]['id']


def find_one(connection, project_id, name):
    matches = [item for item in find_objects(connection, project_id, name=name)
               if item['name'] == name]
    if len(matches) != 1:
        raise ValueError(f'对象名称需唯一：{name}，找到 {len(matches)} 条')
    return matches[0]


def walk(connection, project_id, name, direction='both', depth=1):
    item = find_one(connection, project_id, name)
    result = walk_relations(connection, project_id, 'object', item['id'],
                            direction=direction, max_depth=depth,
                            max_nodes=200, max_edges=400)
    if result['truncated']:
        raise RuntimeError('关系结果被截断，请增大查询上限')
    return result


def edit_and_undo(database, project_id):
    clone = database.with_name(f'exercise-{uuid.uuid4().hex[:8]}.sqlite3')
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source:
        with closing(sqlite3.connect(clone)) as destination:
            source.backup(destination)
    with closing(open_database(clone)) as connection:
        before = project_details(connection, project_id)
        target = find_one(connection, project_id, 'REV-P02｜抽屉里的维修手册')
        identity_before = {key: target[key] for key in ('project_id', 'id', 'layer', 'begin', 'end')}
        relations_before = query_relations(connection, project_id, 'object', target['id'])
        information = copy.deepcopy(target['information'])
        if information['text'].count('杂音') != 1:
            raise ValueError('此练习要求目标句保留一处原始用词“杂音”')
        information['text'] = information['text'].replace('杂音', '噪声', 1)
        changed = dispatch(connection, {
            'action': 'update', 'kind': 'object', 'project_id': project_id,
            'id': target['id'], 'data': {'information': information},
        })
        if not (changed['ok'] and changed['applied']):
            raise RuntimeError(json.dumps(changed, ensure_ascii=False))
        try:
            after = find_one(connection, project_id, target['name'])
            identity_retained = identity_before == {key: after[key] for key in identity_before}
            relations_retained = relations_before == query_relations(connection, project_id, 'object', target['id'])
            consistency_graph = walk(connection, project_id, 'T03｜static → 杂音', 'outgoing')
            current_examples = [node['record'] for node in consistency_graph['nodes']
                                if node.get('record', {}).get('information', {}).get('version') == 'recommended']
            issue_visible = any('噪声' in r['information']['text'] for r in current_examples) and any(
                '杂音' in r['information']['text'] for r in current_examples)
            if not (identity_retained and relations_retained and issue_visible):
                raise AssertionError('修改后的身份、关联或一致性检查未通过')
        finally:
            undone = undo_operation(connection, changed['operation_id'])
            if not (undone['ok'] and undone['applied']):
                raise RuntimeError('撤销未完成：' + json.dumps(undone, ensure_ascii=False))
        restored = before == project_details(connection, project_id)
        if not restored:
            raise AssertionError('撤销后项目内容未完全恢复')
        return {
            'temporary_database': str(clone), 'project_id': project_id,
            'changed_object': target['name'], 'identity_retained': identity_retained,
            'relations_retained': relations_retained,
            'consistency_issue_visible': issue_visible,
            'review_next': ['T03｜static → 杂音', 'REV-P05｜送出与留下', 'R01｜static 的语义'],
            'changed_recommended_examples': current_examples,
            'change': changed, 'undo': undone, 'whole_project_restored': restored,
            'note': '结构复查不判断自然语言术语是否统一；此处通过关联人工比较。Markdown素材不随数据库编辑自动更新，本练习已经撤销。',
        }


def run(database, action, explicit=None):
    database = Path(database).resolve()
    if not database.is_file():
        raise FileNotFoundError(database)
    with closing(open_database(database)) as connection:
        project_id = choose_project(connection, explicit)
        if action == 'overview':
            return project_overview(connection, project_id)
        if action == 'trace':
            return walk(connection, project_id, 'REV-P03A1｜先听见咔哒声', 'outgoing')
        if action == 'split':
            return walk(connection, project_id, 'EN-P03A｜咔哒声带回厨房', 'incoming')
        if action == 'terms':
            return walk(connection, project_id, 'T03｜static → 杂音', 'outgoing')
        if action == 'compare':
            return walk(connection, project_id, 'R05｜末句的两种合理表达', 'both', 2)
    return edit_and_undo(database, project_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('action', choices=['overview', 'trace', 'split', 'terms', 'compare', 'edit-undo'])
    parser.add_argument('--project-id', type=int)
    args = parser.parse_args()
    print(json.dumps(run(args.database, args.action, args.project_id), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

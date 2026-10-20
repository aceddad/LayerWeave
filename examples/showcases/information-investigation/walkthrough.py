"""Read the five case routes; optional edit/undo takes place only in a new copy."""
import argparse
import copy
import json
from pathlib import Path

from layerweave.support.api import open_database, read_record
from layerweave.tool.builtin.usage.exchange import import_project
from layerweave.tool.builtin.usage.query.find_objects import find_objects
from layerweave.tool.builtin.usage.query.walk import walk_relations
from layerweave.tool.builtin.usage.undo.service import undo_operation
from layerweave.tool.builtin.usage.validation.recheck import recheck


def locate(connection, project_id, code):
    hits = [r for r in find_objects(connection, project_id, name=code+'｜')
            if r['information'].get('code') == code]
    if len(hits) != 1:
        raise ValueError(f'{code}: 需要恰好一个匹配，实际 {len(hits)}')
    return hits[0]


def walk(connection, project_id, code, direction='outgoing', depth=3):
    row = locate(connection, project_id, code)
    graph = walk_relations(connection, project_id, 'object', row['id'],
                           direction=direction, max_depth=depth,
                           max_nodes=200, max_edges=400)
    assert not graph['truncated'], graph['truncation_reasons']
    assert all(n['status'] == 'found' for n in graph['nodes']), '关联中存在未找到的端点'
    return graph


def codes(graph):
    return {n['record']['information']['code'] for n in graph['nodes']}


def snapshot(connection, project_id):
    records = {kind: read_record(connection, kind, project_id=project_id)
               for kind in ('layer', 'object')}
    # Bind identities are database-wide. Comparing every binding also proves
    # that relations belonging to any other project remain unchanged.
    records['bind'] = read_record(connection, 'bind')
    return records


def edit_demo(source_path, project_id, target_path):
    source_path, target_path = Path(source_path).resolve(), Path(target_path).resolve()
    if source_path == target_path or target_path.exists():
        raise ValueError('副本必须是不同于原库且尚不存在的文件；不会覆盖任何已有数据库。')
    if not target_path.parent.is_dir():
        raise ValueError('请先建立副本所在目录。')
    source = open_database(source_path)
    target = open_database(target_path)
    try:
        source.backup(target)
    finally:
        source.close()
    try:
        before = snapshot(target, project_id)
        original = locate(target, project_id, 'S05')
        information = copy.deepcopy(original['information'])
        information['text'] += '\n[撤销练习：此行为演示附注，不是调查事实。]'
        result = import_project(target, {'format_version': 1, 'project_id': project_id,
            'items': [{'kind': 'object', 'op': 'update', 'id': original['id'],
                       'data': {'information': information}}]})
        assert result['ok'] and result['applied'], result
        assert result['data']['counts']['skipped'] == 0, result
        after = snapshot(target, project_id)
        assert before['layer'] == after['layer']
        assert before['bind'] == after['bind']
        changed = [r['id'] for r, s in zip(before['object'], after['object']) if r != s]
        assert len(before['object']) == len(after['object'])
        assert changed == [original['id']], changed
        changed_record = locate(target, project_id, 'S05')
        for key, value in original.items():
            if key != 'information':
                assert changed_record[key] == value, key
        assert changed_record['information']['text'].endswith('不是调查事实。]')
        undone = undo_operation(target, result['operation_id'])
        assert undone['ok'] and undone['applied'], undone
        assert snapshot(target, project_id) == before, '撤销后内容或关联未完全恢复'
        checks = recheck(target, project_id)
        assert not checks['issues'], checks
        return {'copy': str(target_path), 'modified_code': 'S05', 'object_id': original['id'],
                'update_operation_id': result['operation_id'],
                'undo_operation_id': undone['operation_id'],
                'only_one_record_changed': True, 'identities_and_bindings_preserved': True,
                'restored_exactly': True, 'recheck': checks}
    finally:
        target.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--project-id', type=int)
    group.add_argument('--import-result', type=Path)
    parser.add_argument('--edit-copy', type=Path, help='仅在这个尚不存在的副本中修改并撤销')
    parser.add_argument('--output', type=Path, help='保存阅读路线与验证结果 JSON')
    args = parser.parse_args()
    project_id = args.project_id
    if args.import_result:
        feedback = json.loads(args.import_result.read_text(encoding='utf-8-sig'))
        assert feedback['ok'], feedback
        project_id = feedback['data']['project_id']
    connection = open_database(args.database)
    try:
        route1 = walk(connection, project_id, 'K04')
        assert {'CW4','CE4','CS4','E04','E09','E14','S01','S04','S06','S08','P1','P2'} <= codes(route1)
        route2 = {c: walk(connection, project_id, c, depth=2) for c in ('CW4','CE4')}
        assert {'E04','S01'} <= codes(route2['CW4'])
        assert {'E09','S04'} <= codes(route2['CE4'])
        route3 = locate(connection, project_id, 'U1')
        assert route3['information']['status'] == 'unresolved'
        route3_graph = walk(connection, project_id, 'U1')
        assert {'CW2','E02','S01','S02'} <= codes(route3_graph)
        route4 = walk(connection, project_id, 'S05', direction='incoming')
        affected = sorted(c for c in codes(route4) if c.startswith('K'))
        assert affected == ['K00','K02','K03','K05'], affected
        report = {'project_id':project_id, 'route1_conclusion_to_sources':route1,
                  'route2_same_question_comparison':route2, 'route3_unknown':route3,
                  'route3_unknown_evidence':route3_graph,
                  'route4_source_impact':route4, 'affected_conclusions':affected}
        for n, c in [(1,'K04'),(3,'U1')]:
            row = locate(connection, project_id, c)
            print(f'路线 {n}：{row["name"]}\n{row["information"]["text"]}\n')
        print('路线 1：已沿出向找到 CW4/CE4/CS4、证据、S01/S04/S06/S08 和 P1/P2。')
        for code in ('CW4','CE4'):
            row = locate(connection, project_id, code)
            print(f'路线 2：{row["name"]}\n{row["information"]["text"]}')
        print('路线 4：S05 更新后需复查的结论：'+', '.join(affected))
    finally:
        connection.close()
    if args.edit_copy:
        report['route5_edit_undo'] = edit_demo(args.database, project_id, args.edit_copy)
        print('路线 5：副本中只修改 S05；全部身份与关联保持；已撤销并逐项确认原内容恢复。')
    else:
        print('路线 5 尚未执行；指定 --edit-copy 一个新的数据库文件路径即可。')
    if args.output:
        if args.output.exists():
            raise ValueError('报告路径已存在，请选择新文件。')
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()

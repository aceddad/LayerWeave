"""Edit and undo one dialogue in a copied case; never rewrites image files."""
from pathlib import Path
from contextlib import closing
import argparse
import hashlib
import json
from layerweave.support.api import open_database, read_record, read_bindings
from layerweave.tool.builtin.usage.records.dispatch import dispatch
from layerweave.tool.builtin.usage.undo.service import undo_operation

parser = argparse.ArgumentParser(description='在漫画工作副本修改对白、标记待排版，或撤销该练习。')
parser.add_argument('database', type=Path)
parser.add_argument('import_result', type=Path)
parser.add_argument('action', choices=['edit', 'undo'])
args = parser.parse_args()
database = args.database.resolve()
if not database.is_file():
    raise SystemExit('数据库不存在；请先在工作副本导入案例。')
report = json.loads(args.import_result.read_text(encoding='utf-8-sig'))
project_id = report['data']['project_id']
ids = {m['source']['key']: m['target']['id']
       for m in report['data']['id_map'] if 'key' in m['source']}
receipt_path = database.parent / 'exercise-result.json'
undo_path = database.parent / 'exercise-undo.json'

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

with closing(open_database(database)) as connection:
    if args.action == 'undo':
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        if receipt['database'] != str(database):
            raise SystemExit('练习记录来自另一数据库；不会执行撤销。')
        result = undo_operation(connection, receipt['result']['operation_id'])
        save(undo_path, result)
        if not result['ok']:
            raise SystemExit(json.dumps(result, ensure_ascii=False))
        for key, before in receipt['before'].items():
            now = read_record(connection, 'object', project_id=project_id, id=ids[key])
            assert now == before, f'{key} 未完整恢复'
        assert read_bindings(connection, 'object', project_id, ids['line-7-1'], direction='both') == receipt['relations']
        print('已撤销：对白和两个制作状态恢复，编号与关联保留。图片文件未改动。')
    else:
        if receipt_path.exists():
            raise SystemExit('此副本已有练习记录。请先检查或撤销；再次体验请建立新的工作副本。')
        keys = ['line-7-1', 'art-7', 'page-2']
        before = {key: read_record(connection, 'object', project_id=project_id, id=ids[key]) for key in keys}
        if any(row is None for row in before.values()):
            raise SystemExit('导入映射与数据库不匹配，停止写入。')
        assert before['line-7-1']['name'] == '对白07-1｜小禾'
        assert before['art-7']['information']['source'] == 'assets/panel-07.svg'
        assert before['page-2']['information']['source'] == 'assets/page-02.svg'
        relations = read_bindings(connection, 'object', project_id, ids['line-7-1'], direction='both')
        paths = [database.parent / before[key]['information']['source'] for key in keys[1:]]
        hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
        requests = []
        for key, row in before.items():
            information = dict(row['information'])
            if key == 'line-7-1':
                information['text'] = '下次叫上我，一起给小苗挡雨。'
            else:
                information.update(production_status='needs_relayout', production_note='对白07-1已修改，待重新制作画面与第二页；图片未自动更新。')
            requests.append({'action': 'update', 'kind': 'object', 'project_id': project_id,
                             'id': ids[key], 'data': {'information': information}})
        result = dispatch(connection, requests)
        save(receipt_path, {'database': str(database), 'before': before, 'relations': relations, 'result': result})
        if not result['ok']:
            raise SystemExit(json.dumps(result, ensure_ascii=False))
        assert read_bindings(connection, 'object', project_id, ids['line-7-1'], direction='both') == relations
        assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths] == hashes
        print('已更新原对白；画面07和第二页标为 needs_relayout。编号、关联和图片文件均保留。')
        print('操作编号：' + result['operation_id'])
        print('检查后运行同一命令，将 edit 改为 undo。')

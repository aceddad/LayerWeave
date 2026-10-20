"""Read five local reading routes using public LayerWeave queries.

No view dependencies; opens SQLite in read-only mode and resolves real IDs by name.
"""
import argparse
import json
import sqlite3
from pathlib import Path
from layerweave.tool.builtin.usage.query.find_objects import find_objects
from layerweave.tool.builtin.usage.query.walk import walk_relations

STARTS = {
    1: ('C01 全文结论：可核查提案值得试验', 'outgoing', 1),
    2: ('P02 审查文章的实践观察', 'outgoing', 1),
    3: ('I02 观察与解释的分界', 'outgoing', 2),
    4: ('D01 质疑：相关变化能证明因果吗', 'outgoing', 2),
    5: ('C02 模型账单不是完整工程成本', 'outgoing', 1),
}
EXPECTED = {
    1: {'c01','p02','p03','p04','p10','c03'},
    2: {'p02','e01','i02','g01'},
    3: {'i02','p02','p03','e01','e03','g01'},
    4: {'d01','p07','p02','e01','e02','i02','g01','s01'},
    5: {'c02','p05','p08','e04','i04','d02','g02'},
}
ANSWERS = {
    1: 'C01 关联 P02 与 P03 两条不同观察，经 P04 归纳，在 P10 形成有条件结论；C03 限制推广。',
    2: 'P02 的出向关联可到 I02（解释）、G01（实际 SVG）和 E01（来源定位）。',
    3: 'P02/P03 的 attribution 区分外文陈述与原创解释；I02 是读者的阅读方法，不是外文作者自述。',
    4: 'D01 针对 P07 对 P02 数据的质疑；E01 给出来源及可证明范围。仍缺同口径的因果识别材料。',
    5: '仅由 C02 的一跳邻域可知：E04 比较局部 API 花费与发现数，P05/P08 追问人工和返工；因此不能据此给出总工程成本排名。',
}

def route(connection, project_id, task):
    name, direction, depth = STARTS[task]
    found = [o for o in find_objects(connection, project_id, name=name) if o['name'] == name]
    if len(found) != 1:
        raise ValueError(f'需要唯一对象 {name!r}，实际 {len(found)} 个；确认项目编号和导入结果。')
    graph = walk_relations(connection, project_id, 'object', found[0]['id'], direction=direction, max_depth=depth, max_nodes=30, max_edges=80)
    if graph['truncated'] or any(n.get('record') is None for n in graph['nodes']):
        raise ValueError('局部图被截断或含失效端点，不能视为完整阅读结果。')
    keys = {n['record']['information']['source_key'] for n in graph['nodes'] if n['kind']=='object'}
    missing = EXPECTED[task] - keys
    if missing:
        raise ValueError(f'案例路径缺少节点：{sorted(missing)}')
    return {'task':task,'start_name':name,'answer':ANSWERS[task],'graph':graph}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database',type=Path)
    parser.add_argument('--project',type=int,required=True)
    parser.add_argument('--task',type=int,choices=range(1,6),required=True)
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args()
    path=args.database.resolve(strict=True)
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as connection:
        connection.row_factory=sqlite3.Row
        result=route(connection,args.project,args.task)
    if args.json:
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return
    graph=result['graph']
    print(f"任务 {args.task} · {len(graph['nodes'])} 个局部节点 / {len(graph['edges'])} 条关联")
    for n in graph['nodes']:
        r=n['record'];info=r.get('information',{})
        print(f"\n[{n['id']}] {r['name']}\n归属：{info.get('attribution','')}\n{info.get('text',info.get('caption',''))}")
        for k in ['source','url','locator']:
            if k in info:print(f'{k}: {info[k]}')
    print('\n局部解释：'+result['answer'])
    print('\n原始关联与两端身份可用 --json 查看。')

if __name__=='__main__':main()

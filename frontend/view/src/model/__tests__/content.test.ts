// 批注成楼、接缝、改动标记、关系、空当、键盘跳转、链接、时间写法
import {describe, expect, it} from 'vitest';
import {changeMarks} from '../changes';
import {cutList} from '../cuts';
import {gapAt} from '../gaps';
import {refLabel, relationsOf} from '../labels';
import {linkQuery} from '../link';
import {cutPoints, editPoints, stepObject, stepTime, stepTrack} from '../navigate';
import {noteIndex, noteList, noteThreads, waitingFor} from '../notes';
import {fmt, fmtSpan, ticks} from '../units';
import type {ChangeOp} from '../../types';
import {bind, chapters, data, layer, model, obj, ref, root} from './fixtures';

const board = (rows: number[][]) => ({rows, x: 0, y: 0, pps: null});

function withNotes() {
  const d = chapters();
  const note = (id: number, n: number, info: Record<string, unknown>) => obj(id, n, n + 1, {type: 'note', media: null, text: String(info.text ?? ''), information: info});
  d.roots.push(root(30, '批注', [0, 5], '条'));
  d.layers.push(layer(30, '批注', 30, null, [
    note(31, 0, {text: '这里要换吗', author: 'Claude', status: 'open'}),
    note(32, 1, {text: '先不换', author: '用户', status: 'open'}),
    note(33, 2, {text: '好', author: 'Claude', status: 'open'}),
    note(34, 3, {text: '已经改了', author: '用户', status: 'done'}),
    note(35, 4, {text: '这两秒空着', author: '用户', status: 'open', span: {begin: 6, end: 8}}),
  ], {role: 'note', hidden: true, type: 'note'}));
  d.binds.push(bind(1, ref('object', 31), ref('object', 3)), bind(2, ref('object', 32), ref('object', 31)),
               bind(3, ref('object', 33), ref('object', 32)), bind(4, ref('object', 34), ref('object', 4)),
               bind(5, ref('object', 35), ref('layer', 2)));
  return d;
}

describe('批注成楼', () => {
  const list = noteList(model(withNotes())), threads = noteThreads(list);

  it('指向另一条批注的是回复；顺着回复找到楼主', () => {
    expect(list.map((n) => [n.id, n.replyTo, n.thread])).toEqual([[31, null, 31], [32, 31, 31], [33, 32, 31], [34, null, 34], [35, null, 35]]);
    expect(threads.map((t) => [t.top.id, t.replies.map((r) => r.id)])).toEqual([[31, [32, 33]], [34, []], [35, []]]);
  });

  it('画布上的 💬 只标待处理楼主指的地方，回复指向批注不算', () => {
    expect([...noteIndex(threads, 1).keys()]).toEqual(['object:3', 'layer:2']);
  });

  it('等谁回复：没处理、最后一句不是他说的（和 view_note --waiting 一样）', () => {
    expect(waitingFor(threads, '用户').map((t) => t.top.id)).toEqual([31]);
    expect(waitingFor(threads, 'Claude').map((t) => t.top.id)).toEqual([35]);
  });
});

describe('接缝', () => {
  const m = model(chapters());

  it('同一轨道里前后相接的图片、视频；接续的两段之间也算；文字和音频不算', () => {
    const cuts = cutList(m, [board([[1, 10]]), board([[20]])], {});
    expect(cuts.map((c) => [c.a.o.id, c.b.o.id, c.gap])).toEqual([[3, 4, 0], [4, 5, 1], [5, 14, 0]]);
  });

  it('按下一段的开始时间筛选', () => {
    expect(cutList(m, [board([[1, 10]])], {begin: 5}).map((c) => c.b.o.id)).toEqual([5, 14]);
  });

  it('重叠的对象在不同小行里，各自和同一小行的前一个相接', () => {
    const d = data([root(1, '根', [0, 10])], [layer(1, '根', 1, null), layer(2, 'a', 1, 1, [obj(3, 0, 3), obj(4, 1, 2), obj(5, 3, 4)])]);
    expect(cutList(model(d), [board([[1]])], {}).map((c) => [c.a.o.id, c.b.o.id])).toEqual([[3, 5]]);
  });
});

describe('改动标记', () => {
  const ops = (items: ChangeOp['items'][]): ChangeOp[] => items.map((it, i) => ({operation_id: `op${i}`, at: '2026-10-11T00:00:00Z', undo_of: null, items: it}));

  it('移动、删除前的位置留下虚线框；数字是倒数第几次操作', () => {
    const marks = changeMarks(ops([
      [{kind: 'object', id: 4, action: 'update', before: {layer: 2, begin: 2, end: 6}, after: {layer: 2, begin: 4, end: 8}}],
      [{kind: 'object', id: 99, action: 'delete', before: {layer: 2, begin: 10, end: 11, name: '删掉的'}, after: null}],
      [{kind: 'object', id: 3, action: 'create', before: null, after: {layer: 2, begin: 0, end: 4}}],
    ]), model(chapters()));
    expect([...marks.changed]).toEqual([[4, {n: 1, action: 'update'}], [3, {n: 3, action: 'create'}]]);
    expect(marks.ghosts.get(2)).toEqual([
      {id: 4, action: 'move', begin: 2, end: 6, label: ''},
      {id: 99, action: 'delete', begin: 10, end: 11, label: '删掉的'},
    ]);
  });

  it('挪走又挪回原处的不留虚线框', () => {
    const marks = changeMarks(ops([
      [{kind: 'object', id: 5, action: 'update', before: {layer: 2, begin: 0, end: 1}, after: {layer: 2, begin: 9, end: 10}}],
      [{kind: 'object', id: 5, action: 'update', before: {layer: 2, begin: 9, end: 10}, after: {layer: 2, begin: 0, end: 1}}],
    ]), model(chapters()));
    expect(marks.ghosts.size).toBe(0);
  });
});

describe('关系', () => {
  it('批注发出的关联不算对象的关系；两个方向都列', () => {
    const d = withNotes();
    d.binds.push(bind(6, ref('object', 3), ref('object', 14), '下一镜'), bind(7, ref('object', 7), ref('object', 3)));
    const m = model(d);
    expect(relationsOf(m, 'object', 3).map((r) => [r.dir, r.ref.id, r.tips])).toEqual([['→', 14, '下一镜'], ['←', 7, '']]);
    expect(refLabel(m, ref('object', 99))).toBe('对象 #99（已不存在）');
    expect(refLabel(m, ref('object', 3, 2))).toBe('项目 2 的对象 #3');
  });
});

describe('空当', () => {
  const objects = [{begin: 1, end: 3}, {begin: 6, end: 9}, {begin: 12, end: 12}];

  it('分清还没开始、两个对象之间、已经结束', () => {
    expect(gapAt(objects, 0)).toEqual({kind: 'before', next: 1});
    expect(gapAt(objects, 4)).toEqual({kind: 'between', from: 3, to: 6});
    expect(gapAt(objects, 9)).toEqual({kind: 'between', from: 9, to: 12});
    expect(gapAt(objects, 13)).toEqual({kind: 'after', last: 12});
  });

  it('有对象、落在瞬间对象上、整层没有对象：都不算空当', () => {
    expect(gapAt(objects, 2)).toBeNull();
    expect(gapAt(objects, 12.01, 0.05)).toBeNull();
    expect(gapAt([], 5)).toBeNull();
    expect(gapAt([{begin: 0, end: 2}, {begin: 2, end: 4}], 2)).toBeNull();
  });
});

describe('键盘跳转', () => {
  const m = model(chapters()), b = board([[1, 10]]);

  it('←/→：同一轨道的前后对象，接续时跨段接着走', () => {
    expect(stepObject(m, b, 3, 1)?.o.id).toBe(4);
    expect(stepObject(m, b, 4, -1)?.o.id).toBe(3);
    expect(stepObject(m, b, 5, 1)?.o.id).toBe(14);
    expect(stepObject(m, b, 14, 1)).toBeNull();
  });

  it('↑/↓：相邻轨道上离这一刻最近的对象，跳过没有对象的轨道', () => {
    expect(stepTrack(m, b, 7, 2, -1)?.o.id).toBe(3);
    expect(stepTrack(m, b, 3, 0, 1)?.o.id).toBe(7);
    expect(stepTrack(m, b, 3, 0, -1)).toBeNull();
  });

  it('没选中对象时在剪辑点之间跳；[ ] 在接缝之间跳', () => {
    const points = editPoints(m, b);
    expect(points).toEqual([0, 1, 3, 4, 8, 9, 10, 12, 15]);
    expect([stepTime(points, 4, 1), stepTime(points, 4, -1), stepTime(points, 15, 1), stepTime(points, 0, -1)]).toEqual([8, 3, null, null]);
    expect(stepTime(points, 4.0000001, -1)).toBe(3);
    expect(cutPoints(m, b)).toEqual([4, 9, 10]);
  });
});

describe('复制链接', () => {
  it('写出画板、看得见的范围、播放头、选中的对象', () => {
    expect(linkQuery({project: 1, view: 'canvas', side: 'now', board: 1, range: [8.12345, 14], playhead: 10, select: 16}))
      .toBe('project=1&board=1&begin=8.123&end=14&playhead=10&select=16');
  });

  it('批注面板对准某条批注时写 note；接缝页不写范围', () => {
    expect(linkQuery({project: 2, view: 'canvas', side: 'notes', note: 42})).toBe('project=2&note=42');
    expect(linkQuery({project: 2, view: 'canvas', side: 'notes'})).toBe('project=2&side=notes');
    expect(linkQuery({project: 1, view: 'cuts', side: 'now', board: 1, range: [0, 5]})).toBe('project=1&view=cuts&board=1');
  });
});

describe('时间写法', () => {
  it('秒写成 分:秒，其他单位照数字写', () => {
    expect([fmt(75.5, '秒'), fmt(-3, 's'), fmt(12, '帧'), fmt(null), fmtSpan(3, '秒'), fmtSpan(2.5, '条')]).toEqual(['1:15.50', '-0:03.00', '12 帧', '—', '3 秒', '2.5 条']);
  });

  it('尺子刻度：屏幕上相邻两格至少 70 像素', () => {
    const marks = ticks(0, 10, 100, 1, '秒');
    expect(marks[1].t - marks[0].t).toBe(1);
    expect(ticks(0, 10, 100, 0.5, '秒')[1].t).toBe(2);
  });
});

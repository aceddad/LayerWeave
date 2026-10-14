// 批注成楼、接缝、改动标记、关系、空当、键盘跳转、链接、时间写法
import {describe, expect, it} from 'vitest';
import {changeMarks} from '../changes';
import {decimalsOf, fmtLength, gapAt, trackGaps} from '../gaps';
import {refLabel, relationsOf} from '../labels';
import {linkQuery} from '../link';
import {editPoints, stepObject, stepTime, stepTrack} from '../navigate';
import {noteIndex, noteList, noteThreads, readBy, waitingFor} from '../notes';
import {withFolds, withNoteStatus, withRead} from '../optimistic';
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

  it('已读：读到楼里最后一条就不算等他；之后有人再写一条又算；各记各的', () => {
    expect(waitingFor(threads, 'Claude', {'35': {Claude: 35}}).map((t) => t.top.id)).toEqual([]);
    expect(waitingFor(threads, 'Claude', {'35': {用户: 35}}).map((t) => t.top.id)).toEqual([35]);
    expect(waitingFor(threads, '用户', {'31': {用户: 32}}).map((t) => t.top.id)).toEqual([31]);   // 读到 32，后面还有 33
    expect(waitingFor(threads, '用户', {'31': {用户: 33}}).map((t) => t.top.id)).toEqual([]);
    expect(readBy(threads[0], '用户', {'31': {用户: 33}})).toBe(true);
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

  it('轨道里的空当：只算有时长的对象之间，几个小行合起来算；瞬间标记不分割、也不单独成空当', () => {
    expect(trackGaps([{begin: 0, end: 2}, {begin: 3, end: 5}, {begin: 4, end: 8}, {begin: 8, end: 8}, {begin: 10, end: 12}]))
      .toEqual([{from: 2, to: 3}, {from: 8, to: 10}]);
    expect(trackGaps([{begin: 4, end: 8}, {begin: 9, end: 9}, {begin: 10, end: 12}])).toEqual([{from: 8, to: 10}]);
    expect(trackGaps([{begin: 1, end: 1}, {begin: 3, end: 3}, {begin: 5, end: 5}])).toEqual([]);   // 一整条小节线
    expect(trackGaps([{begin: 0, end: 2.0004}, {begin: 2.0006, end: 3}], 0.0005)).toEqual([]);
  });

  it('画布上的空当跟着接续偏移走：第一章的画面 8–9 空着，接缝两边紧接', () => {
    const m = model(chapters());
    expect(m.trackLayout(m.rowTracks([1, 10])[1], [1, 10]).gaps).toEqual([{from: 8, to: 9}]);
  });

  it('长度的位数按轴的精度', () => {
    expect([decimalsOf(0.001), decimalsOf(1), decimalsOf(0.5), decimalsOf(0.25), decimalsOf(1 / 24), decimalsOf(undefined)]).toEqual([3, 0, 1, 2, 2, null]);
    expect([fmtLength(3, 3), fmtLength(2.9999999, 3), fmtLength(24, 0), fmtLength(1.5, null)]).toEqual(['3.000', '3.000', '24', '1.5']);
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

  it('没选中对象时在剪辑点之间跳（[ ] 的接缝跳转点由接缝插件给，测试在 plugins/cuts）', () => {
    const points = editPoints(m, b);
    expect(points).toEqual([0, 1, 3, 4, 8, 9, 10, 12, 15]);
    expect([stepTime(points, 4, 1), stepTime(points, 4, -1), stepTime(points, 15, 1), stepTime(points, 0, -1)]).toEqual([8, 3, null, null]);
    expect(stepTime(points, 4.0000001, -1)).toBe(3);
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

  it('沿着读写起点；方向、步数不是默认的才写', () => {
    expect(linkQuery({project: 1, view: 'canvas', side: 'walk', walk: {from: 'object:16', direction: 'both', depth: 3}})).toBe('project=1&walk=object%3A16');
    expect(linkQuery({project: 1, view: 'canvas', side: 'walk', walk: {from: 'layer:5', direction: 'out', depth: 2}}))
      .toBe('project=1&walk=layer%3A5&walkdir=out&walkdepth=2');
    expect(linkQuery({project: 1, view: 'canvas', side: 'now', walk: {from: 'object:16', direction: 'both', depth: 3}})).toBe('project=1');
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

// 先改画面、再写数据库：本地改的这一份要和服务端写完以后读回来的一样（note.py 的 set_read、fold.py 的 set_folds）
describe('先改画面的写入', () => {
  it('已读记下楼里最新的一条，标为未读去掉这个人；别人的不动', () => {
    const d = withNotes(), threads = noteThreads(noteList(model(d)));
    const read = withRead({'31': {Claude: 31}}, threads[0], ' 用户 ', true);
    expect(read).toEqual({'31': {Claude: 31, 用户: 33}});
    expect(readBy(threads[0], '用户', read)).toBe(true);
    expect(withRead(read, threads[0], '用户', false)).toEqual({'31': {Claude: 31}});
  });

  it('已处理只改那一条批注的状态，楼跟着进"已处理"', () => {
    const d = withNotes(), after = withNoteStatus(d, 31, 'done');
    const threads = noteThreads(noteList(model(after)));
    expect(threads.map((t) => [t.top.id, t.top.status])).toEqual([[31, 'done'], [34, 'done'], [35, 'open']]);
    expect(noteThreads(noteList(model(d)))[0].top.status).toBe('open');   // 原来那份不变
  });

  it('折叠：已经折着的保留原来的人，没带说明留着原来的；展开清掉；对方那边不动', () => {
    const start = [{layer: 2, user: '小林', user_tips: '先不看', ai: 'Claude', ai_tips: '对过了'}];
    expect(withFolds(start, [2, 3], 'user', 'fold', '用户')).toEqual([
      {layer: 2, user: '小林', user_tips: '先不看', ai: 'Claude', ai_tips: '对过了'},
      {layer: 3, user: '用户', user_tips: '', ai: '', ai_tips: ''},
    ]);
    expect(withFolds(start, [2], 'user', 'unfold', '用户')).toEqual([{layer: 2, user: '', user_tips: '', ai: 'Claude', ai_tips: '对过了'}]);
    expect(withFolds(start, [2], 'ai', 'unfold', '用户')).toEqual([{layer: 2, user: '小林', user_tips: '先不看', ai: '', ai_tips: ''}]);
    expect(withFolds(start, [2], 'user', 'tips', '用户', ' 换了方向 ')[0].user_tips).toBe('换了方向');
    expect(withFolds([], [4], 'user', 'fold', '  ')).toEqual([{layer: 4, user: '用户', user_tips: '', ai: '', ai_tips: ''}]);
  });
});

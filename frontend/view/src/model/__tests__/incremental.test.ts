import {describe, expect, it} from 'vitest';
import {applyChanges} from '../incremental';
import {Model} from '../model';
import {SyncGate} from '../syncGate';
import {chapters, model, obj} from './fixtures';
import type {Board, ViewChange} from '../../types';

describe('完整页增量投影', () => {
  it('保留未变层和对象，重新计算删除极值后的根范围', () => {
    const before = chapters(), old = before.layers[1].objects[0];
    const next = applyChanges(before, [{kind: 'object', id: 5, before_layer: 2, after_layer: null, after: null}]);
    expect(next.layers[1]).not.toBe(before.layers[1]);
    expect(next.layers[1].objects[0]).toBe(old);
    expect(next.layers[6]).toBe(before.layers[6]);
    expect(next.roots[0].extent).toEqual([0, 8]);
    expect(next.roots[1]).toBe(before.roots[1]);
    expect(before.layers[1].objects).toHaveLength(3);
  });
  it('按顺序处理同一对象多次修改、换层、删除和恢复', () => {
    const before = chapters();
    const changes: ViewChange[] = [
      {kind: 'object', id: 3, before_layer: 2, after_layer: 11, after: obj(3, 0, 7)},
      {kind: 'object', id: 3, before_layer: 11, after_layer: null, after: null},
      {kind: 'object', id: 3, before_layer: null, after_layer: 2, after: obj(3, 4, 6)},
    ];
    const next = applyChanges(before, changes);
    expect(next.layers[1].objects.find((o) => o.id === 3)?.begin).toBe(4);
    expect(next.layers[4].objects.map((o) => o.id)).toEqual([12]);
    expect(applyChanges(next, changes)).toEqual(next); // 页重试可以重新应用
  });
  it('已读变化不替换内容、根或关系；空页保留整个数据引用', () => {
    const before = chapters();
    const next = applyChanges(before, [{kind: 'view_note', id: 50, after: {user: 53}}]);
    expect(next.layers).toBe(before.layers);
    expect(next.roots).toBe(before.roots);
    expect(next.binds).toBe(before.binds);
    expect(next.noteReads).toEqual({'50': {user: 53}});
    expect(applyChanges(before, [])).toBe(before);
    expect(applyChanges(next, [{kind: 'view_note', id: 50, after: null}]).noteReads).toEqual({});
  });
  it('根变化使整行接续失效，另一块画板的布局与索引复用', () => {
    const data = chapters(), previous = model(data);
    const chain: Board = {rows: [[1, 10]], x: 0, y: 0, pps: 20};
    const music: Board = {rows: [[20]], x: 0, y: 300, pps: 20};
    const oldChain = previous.boardLayout(chain), oldMusic = previous.boardLayout(music);
    const nextData = applyChanges(data, [{kind: 'object', id: 5, before_layer: 2, after_layer: 2, after: obj(5, 9, 13)}]);
    const next = new Model(nextData, previous.opts, previous);
    expect(next.boardLayout(music)).toBe(oldMusic);
    expect(next.object(22)).toBe(previous.object(22));
    expect(next.boardLayout(chain)).not.toBe(oldChain);
    expect(next.segments([1, 10])[1].offset).toBe(13);
    expect(previous.segments([1, 10])[1].offset).toBe(10);
  });
  it('折叠使对应根布局失效；配置过滤变化不误用之前缓存', () => {
    const data = chapters(), previous = model(data), board: Board = {rows: [[1]], x: 0, y: 0, pps: 20};
    const old = previous.boardLayout(board);
    const nextData = applyChanges(data, [{kind: 'view_layer', id: 2, after: {layer: 2, user: 'U', user_tips: '', ai: '', ai_tips: ''}}]);
    const next = new Model(nextData, previous.opts, previous);
    expect(next.boardLayout(board)).not.toBe(old);
    expect(next.boardLayout(board)!.height).toBeLessThan(old!.height);
    expect(new Model(data, {...previous.opts, only: new Set([1])}, previous).boardLayout(board)).not.toBe(old);
  });
});

describe('同步请求凭据', () => {
  it('切走再切回来也不能让旧响应覆盖', () => {
    const gate = new SyncGate(); gate.select(1); const old = gate.token()!;
    gate.select(2); gate.select(1);
    expect(gate.valid(old)).toBe(false);
  });
  it('写入期间拒绝读取覆盖，最后一项结束以后取得新凭据', () => {
    const gate = new SyncGate(); gate.select(1); const old = gate.token()!;
    const one = gate.beginWrite(1), two = gate.beginWrite(1);
    expect(gate.token()).toBeNull();
    one(); one(); expect(gate.token()).toBeNull();
    two(); expect(gate.valid(old)).toBe(false);
    expect(gate.valid(gate.token()!)).toBe(true);
  });
});

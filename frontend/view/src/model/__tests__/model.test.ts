// 画面模型：接续偏移、轨道合并、小行、画板尺寸。期望值按 model.ts 顶部的常量手算
import {describe, expect, it} from 'vitest';
import {HEAD, ROW, RULER, STRIP, lanes} from '../model';
import {chapters, data, layer, model, obj, root} from './fixtures';

const board = (rows: number[][], extra = {}) => ({rows, x: 0, y: 0, pps: null, ...extra});

describe('左右接续', () => {
  it('后一段的 0 接在前一段的结尾', () => {
    expect(model(chapters()).segments([1, 10])).toEqual([
      {root: 1, offset: 0, begin: 0, end: 10},
      {root: 10, offset: 10, begin: 10, end: 15},
    ]);
  });

  it('后一段从负数开始时，整段往后挪，让它的起点接上（和 Python 的 chain_offsets 一致）', () => {
    const d = chapters();
    d.roots[1] = root(10, '第二章', [-2, 5]);
    expect(model(d).segments([1, 10])[1]).toEqual({root: 10, offset: 12, begin: 10, end: 17});
  });

  it('接缝那一刻算后一段；最后一段的结尾也算最后一段', () => {
    const m = model(chapters());
    expect(m.segmentAt([1, 10], 9.99)?.root).toBe(1);
    expect(m.segmentAt([1, 10], 10)?.root).toBe(10);
    expect(m.segmentAt([1, 10], 15)?.root).toBe(10);
    expect(m.segmentAt([1, 10], 15.5)).toBeNull();
  });

  it('offsetOf 给出某个根在它那块画板上的起点', () => {
    expect(model(chapters()).offsetOf([board([[1, 10]]), board([[20]])], 10)).toBe(10);
  });
});

describe('轨道', () => {
  it('接续的两段里名字路径相同的层合成一条轨道，顺序按第一次出现', () => {
    const tracks = model(chapters()).rowTracks([1, 10]);
    expect(tracks.map((t) => t.key)).toEqual(['', '/画面', '/字幕']);
    expect(tracks.map((t) => t.parts.map((p) => p.layer.id))).toEqual([[1, 10], [2, 13], [6, 11]]);
  });

  it('同一父层下重名的层按出现次序区分，不合并', () => {
    const d = data([root(1, '根', [0, 10])], [layer(1, '根', 1, null), layer(2, 'x', 1, 1), layer(3, 'x', 1, 1)]);
    expect(model(d).rowTracks([1]).map((t) => t.key)).toEqual(['', '/x', '/x#2']);
  });

  it('折叠根以后只剩根轨道', () => {
    expect(model(chapters(), {collapsed: new Set(['1|'])}).visibleTracks([1, 10]).map((t) => t.key)).toEqual(['']);
  });

  it('只显示部分层：轨道里有这个层才留下', () => {
    expect(model(chapters(), {only: new Set([6])}).visibleTracks([1, 10]).map((t) => t.key)).toEqual(['/字幕']);
  });

  it('接续时后一段的对象加上偏移，按开始时间排在同一条轨道里', () => {
    const m = model(chapters());
    const items = m.trackLayout(m.rowTracks([1, 10])[1], [1, 10]).items;
    expect(items.map((it) => [it.o.id, it.begin, it.end, it.lane])).toEqual([[3, 0, 4, 0], [4, 4, 8, 0], [5, 9, 10, 0], [14, 10, 15, 0]]);
  });
});

describe('小行', () => {
  it('互相重叠的对象排进不同的小行，首尾相接的不算重叠', () => {
    expect(lanes([{begin: 0, end: 5}, {begin: 3, end: 8}, {begin: 5, end: 9}])).toEqual([0, 1, 0]);
  });

  it('瞬间对象落在前一个对象的结尾上时另起一行，免得被盖住', () => {
    expect(lanes([{begin: 0, end: 5}, {begin: 5, end: 5}, {begin: 5, end: 7}])).toEqual([0, 1, 0]);
  });

  it('两个小行的轨道高 2×40+2×3 = 86，一个小行的是 46', () => {
    const d = data([root(1, '根', [0, 10])], [layer(1, '根', 1, null), layer(2, 'a', 1, 1, [obj(3, 0, 5), obj(4, 2, 6)]), layer(5, 'b', 1, 1, [obj(6, 0, 1)])]);
    const m = model(d), [, a, b] = m.rowTracks([1]);
    expect(m.trackLayout(a, [1]).height).toBe(86);
    expect(m.trackLayout(b, [1]).height).toBe(ROW);
  });
});

describe('画板尺寸（由数据算，不量页面）', () => {
  it('自动缩放：画板铺满 1000 像素', () => {
    const m = model(chapters());
    expect(m.pps(board([[1]]))).toBe(100);
    expect(m.pps(board([[1]], {pps: 7}))).toBe(7);
    expect(m.pps(board([[1]], {pps: 7, tempPps: 3}))).toBe(3);
  });

  it('两行的画板：接续行多一条窄带，第二行上面有 2 像素的分隔', () => {
    const layout = model(chapters()).boardLayout(board([[1, 10], [20]]))!;
    expect([layout.a, layout.e, layout.pps]).toEqual([0, 20, 50]);
    expect(layout.sections.map((s) => [s.top, s.height, s.strip])).toEqual([[HEAD + RULER, STRIP + 3 * ROW, true], [224, 2 * ROW, false]]);
    expect(layout.height).toBe(318);
    expect(layout.width).toBe(200 + 20 * 50 + 40 + 2);
  });

  it('收起的层（批注层这类）不画；整块画板都收起时不画这块画板', () => {
    const d = chapters();
    d.layers = d.layers.map((l) => (l.root === 20 ? {...l, hidden: true} : l));
    expect(model(d).boardLayout(board([[20]]))).toBeNull();
    expect(model(d, {showHidden: true}).boardLayout(board([[20]]))).not.toBeNull();
    expect(model(d).boardLayout(board([[1, 10], [20]]))!.height).toBe(HEAD + RULER + STRIP + 3 * ROW + 2);
  });
});

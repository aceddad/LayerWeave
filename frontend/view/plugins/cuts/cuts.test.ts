// 接缝插件的计算（从视图本体搬过来的测试）：用宿主真正的工具函数
import {describe, expect, it} from 'vitest';
import {kindOf} from '../../src/model/kinds';
import {keyOf, lanes, rootsOf} from '../../src/model/model';
import {chapters, data, folded, layer, model, obj, root} from '../../src/model/__tests__/fixtures';
import {cutList, cutPoints} from './cuts';

const util = {kindOf, lanes, keyOf, rootsOf};
const board = (rows: number[][]) => ({rows, x: 0, y: 0, pps: null});

describe('接缝', () => {
  const m = model(chapters());

  it('同一轨道里前后相接的图片、视频；接续的两段之间也算；文字和音频不算', () => {
    const cuts = cutList(util, m, [board([[1, 10]]), board([[20]])], {});
    expect(cuts.map((c) => [c.a.o.id, c.b.o.id, c.gap])).toEqual([[3, 4, 0], [4, 5, 1], [5, 14, 0]]);
  });

  it('按下一段的开始时间筛选', () => {
    expect(cutList(util, m, [board([[1, 10]])], {begin: 5}).map((c) => c.b.o.id)).toEqual([5, 14]);
  });

  it('重叠的对象在不同小行里，各自和同一小行的前一个相接', () => {
    const d = data([root(1, '根', [0, 10])], [layer(1, '根', 1, null), layer(2, 'a', 1, 1, [obj(3, 0, 3), obj(4, 1, 2), obj(5, 3, 4)])]);
    expect(cutList(util, model(d), [board([[1]])], {}).map((c) => [c.a.o.id, c.b.o.id])).toEqual([[3, 5]]);
  });

  it('折叠的轨道不列接缝', () => {
    expect(cutList(util, model(folded(chapters(), 13)), [board([[1, 10]])], {})).toEqual([]);
  });

  it('键盘 [ ] 的跳转点：下一段开始的地方', () => {
    expect(cutPoints(util, m, board([[1, 10]]))).toEqual([4, 9, 10]);
  });
});

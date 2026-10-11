// 排版操作和拖动拼接的判断。三块画板的高度：第一章、第二章各 3 条轨道 → 60+138+2 = 200；配乐 2 条 → 154
import {describe, expect, it} from 'vitest';
import {decideDrop} from '../dropRule';
import {afterResize, merge, placeAuto, separate, sizeOf, snap, split} from '../layoutOps';
import {keyOf} from '../model';
import type {Board} from '../../types';
import {chapters, data, folded, layer, model, root} from './fixtures';

const at = (rows: number[][], x: number | null, y: number | null): Board => ({rows, x, y, pps: null});
const find = (boards: Board[], key: number) => boards.find((b) => keyOf(b) === key)!;

describe('画板尺寸', () => {
  it('和页面上的一样按轨道数算', () => {
    const m = model(chapters());
    expect([sizeOf(m, at([[1]], 0, 0)).h, sizeOf(m, at([[10]], 0, 0)).h, sizeOf(m, at([[20]], 0, 0)).h]).toEqual([200, 200, 154]);
  });
});

describe('自动摆放', () => {
  it('没有位置的画板依次排在下方，间隔 48', () => {
    const {boards} = placeAuto([at([[1]], null, null), at([[10]], null, null), at([[20]], null, null)], model(chapters()));
    expect(boards.map((b) => [b.x, b.y])).toEqual([[0, 0], [0, 248], [0, 496]]);
  });

  it('已有位置的画板不动，新的排在它们下面、和最左边对齐', () => {
    const {boards, changed} = placeAuto([at([[1]], 100, 50), at([[10]], null, null)], model(chapters()));
    expect(changed).toBe(true);
    expect(boards.map((b) => [b.x, b.y])).toEqual([[100, 50], [100, 298]]);
  });
});

describe('拼接和拆出', () => {
  const m = model(chapters());

  it('上下拼成新的一行，左右接在这一段的前后', () => {
    const start = [at([[1]], 0, 0), at([[10]], 0, 248)];
    expect(merge(start, 10, 1, 1, 'below', null, m)[0].rows).toEqual([[1], [10]]);
    expect(merge(start, 10, 1, 1, 'above', null, m)[0].rows).toEqual([[10], [1]]);
    expect(merge(start, 10, 1, 1, 'right', null, m)[0].rows).toEqual([[1, 10]]);
    expect(merge(start, 10, 1, 1, 'left', null, m)[0].rows).toEqual([[10, 1]]);
    expect(merge(start, 10, 1, 1, 'right', null, m)).toHaveLength(1);
  });

  it('不改传进来的排版', () => {
    const start = [at([[1]], 0, 0), at([[10]], 0, 248)];
    merge(start, 10, 1, 1, 'below', null, m);
    expect(start[0].rows).toEqual([[1]]);
  });

  it('拆出放在原画板正下方，下面的画板往下推', () => {
    const start = [at([[1], [20]], 0, 0), at([[10]], 0, 342)];   // 两行的画板高 60+138+2+92+2 = 294
    const out = split(start, 20, m);
    expect(find(out, 1).rows).toEqual([[1]]);
    expect([find(out, 20).x, find(out, 20).y]).toEqual([0, 248]);
    expect(find(out, 10).y).toBe(342 + (248 + 154 - 294));
  });

  it('拆出再拼回去，其他画板回到原处（以前画板越漂越远就是这里不对称）', () => {
    const start = [at([[1], [20]], 0, 0), at([[10]], 0, 342)];
    const split1 = split(start, 20, m), c = find(split1, 20), {w, h} = sizeOf(m, c);
    const back = merge(split1, 20, 1, 1, 'below', {x: c.x!, y: c.y!, w, h}, m);
    expect(find(back, 1).rows).toEqual([[1], [20]]);
    expect(find(back, 10).y).toBe(342);
  });

  it('折叠后画板变矮，下面的画板跟着往上', () => {
    const out = afterResize([at([[1]], 0, 0), at([[10]], 0, 248)], 1, 200, model(folded(chapters(), 1)));
    expect(find(out, 10).y).toBe(248 - (200 - (60 + 26 + 2)));
  });

  it('压在一起的画板（页面没开着时 AI 展开了一层）：从上往下挪开，不压的不动', () => {
    const m = model(chapters());
    const {boards, changed} = separate([at([[1]], 0, 0), at([[10]], 0, 150), at([[20]], 2000, 100)], m);
    expect(changed).toBe(true);
    expect([find(boards, 10).y, find(boards, 20).y]).toEqual([248, 100]);
    expect(separate(boards, m).changed).toBe(false);
  });

  it('靠近别的画板左边缘时对齐；离得远的方向不动', () => {
    expect(snap({x: 5, y: 300}, 20, [at([[1]], 0, 0), at([[20]], 5, 300)], m, 1)).toEqual({x: 0, y: 300});
  });
});

describe('拖动拼接的判断', () => {
  // 目标：第一章 → 第二章 接续一行，画板时间 [0, 15]，铺满 1000 像素；接续区宽 max(段长 15%, 36 像素)
  const m = model(chapters());
  const target = at([[1, 10]], 0, 0), moving = at([[20]], 0, 400);

  it('落在开头附近：接在前面；结尾附近：接在后面；两段之间：接在前一段后面', () => {
    expect(decideDrop(m, moving, target, 0, 0.5, true, true, 1)).toMatchObject({side: 'left', root: 1, at: 0, ok: true});
    expect(decideDrop(m, moving, target, 0, 14.5, true, true, 1)).toMatchObject({side: 'right', root: 10, at: 15});
    expect(decideDrop(m, moving, target, 0, 9.5, true, true, 1)).toMatchObject({side: 'right', root: 1, at: 10});
  });

  it('落在中间：按上下半边拼成新的一行；在名字列上也是', () => {
    expect(decideDrop(m, moving, target, 0, 5, true, true, 1)).toMatchObject({side: 'above', root: 1, at: null});
    expect(decideDrop(m, moving, target, 0, 5, true, false, 1)).toMatchObject({side: 'below'});
    expect(decideDrop(m, moving, target, 0, 0.5, false, false, 1)).toMatchObject({side: 'below'});
  });

  it('好几行的画板不能左右接；单位不同不能拼。都说明原因', () => {
    const tall = at([[20], [99]], 0, 400);
    const d = chapters();
    d.roots.push(root(99, '分镜', [0, 3])); d.layers.push(layer(99, '分镜', 99, null));
    expect(decideDrop(model(d), tall, target, 0, 14.5, true, true, 1)).toMatchObject({ok: false, reason: expect.stringContaining('好几行')});
    const frames = data([root(1, '第一章', [0, 10]), root(30, '逐帧', [0, 24], '帧')], [layer(1, '第一章', 1, null), layer(30, '逐帧', 30, null)]);
    expect(decideDrop(model(frames), at([[30]], 0, 0), at([[1]], 0, 0), 0, 5, true, true, 1)).toMatchObject({ok: false, reason: expect.stringContaining('单位不同')});
  });
});

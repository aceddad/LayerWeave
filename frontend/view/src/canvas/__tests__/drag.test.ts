import {afterEach, describe, expect, it, vi} from 'vitest';
import type {Board} from '../../types';
import {bind, chapters, folded, model, ref} from '../../model/__tests__/fixtures';
import {snap} from '../../model/layoutOps';
import {dragPosition, liveBoard, moveBoard, sameDrop, setLivePosition} from '../dragState';
import {createRelationReader} from '../relations';

const boards = (): Board[] => [
  {rows: [[1]], x: 0, y: 0, pps: null},
  {rows: [[10]], x: 0, y: 248, pps: null},
];
afterEach(() => { setLivePosition(1, null); setLivePosition(10, null); });

describe('拖动位置与业务排版', () => {
  it('瞬时坐标不改业务数据，结束的原始位置不会冲掉吸附结果', () => {
    const initial = boards(), m = model(chapters());
    const snapped = dragPosition({x: 5, y: 300}, null, false, (p) => snap(p, 10, initial, m, 1));
    expect(snapped).toEqual({x: 0, y: 300});
    setLivePosition(10, snapped);
    expect(liveBoard(initial[1])).toMatchObject({x: 0, y: 300});
    expect(initial[1]).toMatchObject({x: 0, y: 248});
    const constrain = vi.fn(() => ({x: 5, y: 300}));
    const final = dragPosition({x: 5, y: 300}, snapped, true, constrain);
    expect(final).toBe(snapped);
    expect(constrain).not.toHaveBeenCalled();
    const committed = moveBoard(initial, 10, final);
    expect(committed[0]).toBe(initial[0]);
    expect(committed[1].rows).toBe(initial[1].rows);
    expect(committed[1]).toMatchObject({x: 0, y: 300});
  });
  it('取消后读取原坐标；同位置结束不制造新排版引用', () => {
    const initial = boards();
    setLivePosition(1, {x: 500, y: 600});
    setLivePosition(1, null);
    expect(liveBoard(initial[0])).toBe(initial[0]);
    expect(moveBoard(initial, 1, {x: 0, y: 0})).toBe(initial);
  });
  it('拼接提示只在目标或语义改变时变化', () => {
    const drop = {targetKey: 1, root: 1, side: 'right' as const, ok: true, reason: '', rowIndex: 0, at: 10};
    expect(sameDrop(null, null)).toBe(true);
    expect(sameDrop(drop, {...drop})).toBe(true);
    expect(sameDrop(drop, {...drop, root: 10})).toBe(false);
    expect(sameDrop(drop, {...drop, at: 20})).toBe(false);
    expect(sameDrop(drop, null)).toBe(false);
  });
});

describe('关系拓扑和位置分开缓存', () => {
  const fixture = () => ({...chapters(), binds: [
    bind(1, ref('object', 3), ref('object', 12), 'related'),
    bind(2, ref('object', 4), ref('object', 22, 2)),
  ]});
  it('不画关系线时不遍历各对象端点', () => {
    const m = model(fixture()), scan = vi.spyOn(m, 'boardLayout');
    expect(createRelationReader()(m, boards(), false, null)).toEqual([]);
    expect(scan).not.toHaveBeenCalled();
  });
  it('仅平移保留边数组；拼接后端点属于新画板', () => {
    const m = model(fixture()), read = createRelationReader(), initial = boards();
    const edges = read(m, initial, true, null);
    expect(edges).toHaveLength(1);
    expect(edges[0]).toMatchObject({source: 'b1', target: 'b10', sourceHandle: 'o3', targetHandle: 't12'});
    expect(read(m, moveBoard(initial, 1, {x: 100, y: 200}), true, null)).toBe(edges);
    const joined = read(m, [{rows: [[1, 10]], x: 100, y: 200, pps: null}], true, null);
    expect(joined[0]).toMatchObject({source: 'b1', target: 'b1'});
  });
  it('选择、折叠、关系内容变化会更新，跨项目边不画', () => {
    const data = fixture(), m = model(data), read = createRelationReader();
    expect(read(m, boards(), false, 4)).toEqual([]);
    expect(read(m, boards(), false, 3)[0].data?.hot).toBe(true);
    expect(read(model(folded(data, 10)), boards(), true, null)).toEqual([]);
    const changed = model({...data, binds: [bind(1, ref('object', 3), ref('object', 12), 'new')]});
    expect(read(changed, boards(), true, null)[0].data?.tips).toBe('new');
  });
});

// 分页：取第几页、页码夹在范围里
import {describe, expect, it} from 'vitest';
import {pageSlice} from '../Pager';

describe('分页', () => {
  const items = Array.from({length: 600}, (_, i) => i);
  it('600 个分 10 页，每页 60', () => {
    const third = pageSlice(items, 3, 60);
    expect([third.pages, third.page, third.items.length, third.items[0]]).toEqual([10, 3, 60, 120]);
    expect(pageSlice(items, 10, 60).items.at(-1)).toBe(599);
  });
  it('页码超出范围夹到两头；没有东西时也是 1 页', () => {
    expect(pageSlice(items, 99, 60).page).toBe(10);
    expect(pageSlice(items, 0, 60).page).toBe(1);
    expect(pageSlice(items, NaN, 60).page).toBe(1);
    expect(pageSlice([], 2, 60)).toEqual({items: [], page: 1, pages: 1});
  });
});

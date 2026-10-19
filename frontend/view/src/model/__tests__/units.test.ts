import {describe, expect, it} from 'vitest';
import {translator} from '../../i18n/core';
import {displayUnit, ticks} from '../units';
import {chapters, model} from './fixtures';

describe('轴刻度和显示单位', () => {
  it('精度为 1 时放大仍只出现整数刻度，缩小时仍保持合适间距', () => {
    for (const unit of ['序号', '帧', 'second']) {
      for (const zoom of [.5, 1, 5]) {
        const marks = ticks(-2, 3, 350, zoom, unit, 1);
        expect(marks.length).toBeGreaterThan(1);
        expect(marks.every(m => Number.isInteger(m.t))).toBe(true);
        expect((marks[1].x - marks[0].x) * zoom).toBeGreaterThanOrEqual(70);
      }
    }
  });
  it('小数步长按精度的整数倍选取，不把其他轴强制变为整数', () => {
    expect(ticks(0, 1, 700, 1, '拍', .25).map(m => m.t)).toEqual([0, .25, .5, .75, 1, 1.25]);
    const marks = ticks(-.1, .3, 700, 1, 'second', .04);
    expect(marks[1].t - marks[0].t).toBeCloseTo(.12);
    for (const m of marks) expect(m.t / .04).toBeCloseTo(Math.round(m.t / .04));
    expect(ticks(0, .004, 70000, 1, '序号', .001)[1].t).toBe(.001);
    expect(ticks(.28, .4, 3500, 1, 'second', .04)[0].t).toBe(.28);
  });
  it('组合画板选最细精度，未声明精度沿用基础默认值', () => {
    const d = chapters();
    d.roots[0].axis = {unit: 'second', precision: 1};
    d.roots[1].axis = {unit: 'second', precision: .25};
    const m = model(d), board = (rows: number[][]) => ({rows, x: 0, y: 0, pps: null});
    expect(m.boardLayout(board([[1]]))?.precision).toBe(1);
    expect(m.boardLayout(board([[1], [10]]))?.precision).toBe(.25);
    expect(m.boardLayout(board([[1, 10]]))?.precision).toBe(.25);
    expect(m.boardLayout(board([[1], [20]]))?.precision).toBe(1e-6);
  });
  it('秒的同义写法随语言显示，自定义单位保持原文', () => {
    for (const unit of ['second', 'seconds', 'sec', 's', '秒', ' SECOND ']) {
      expect(displayUnit(unit, translator('zh'))).toBe('秒');
      expect(displayUnit(unit, translator('en'))).toBe('s');
    }
    for (const unit of ['序号', '拍', 'custom-unit', '']) {
      expect(displayUnit(unit, translator('en'))).toBe(unit);
    }
  });
});

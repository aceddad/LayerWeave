// 预览插件的纯计算：间隔的写法、取哪些时刻、GIF 的第几帧、SVG 会不会动、多长
import {describe, expect, it} from 'vitest';
import {frameAt, maybeAnimated, parseStep, sampleTimes, shots, svgAnimated, svgDuration} from './frames';

describe('预览的取帧', () => {
  it('间隔：1f 逐帧、3f、0.5s；写错的不认', () => {
    expect(parseStep('1f')).toEqual({unit: 'f', n: 1});
    expect(parseStep(' 0.5S ')).toEqual({unit: 's', n: 0.5});
    for (const bad of ['', '0f', '1.5f', 'abc', '-1s', null]) expect(parseStep(bad)).toBeNull();
  });

  it('按秒取：含两头，不超过总长', () => {
    expect(sampleTimes(2, 0, 0.5)).toEqual([0, 0.5, 1, 1.5, 2]);
    expect(sampleTimes(2, 1.2, 0.5)).toEqual([1.2, 1.7]);
    expect(sampleTimes(0, 0, 1)).toEqual([]);
  });

  it('视频逐帧：按帧率算时刻和帧号', () => {
    const list = shots({duration: 1, from: 0, step: {unit: 'f', n: 1}, fps: 24});
    expect(list).toHaveLength(25);
    expect(list[12]).toEqual({t: 0.5, frame: 12});
    expect(shots({duration: 1, from: 0.5, step: {unit: 'f', n: 6}, fps: 24}).map((s) => s.frame)).toEqual([12, 18, 24]);
  });

  it('GIF：按真实帧数帧；按秒取时换算成那一刻的帧', () => {
    const starts = [0, 0.1, 0.3, 0.6];
    expect(frameAt(starts, 0.25)).toBe(1);
    expect(frameAt(starts, 0.3)).toBe(2);
    expect(shots({duration: 0.8, from: 0, step: {unit: 'f', n: 2}, fps: 24, starts}).map((s) => s.frame)).toEqual([0, 2]);
    expect(shots({duration: 0.8, from: 0, step: {unit: 's', n: 0.4}, fps: 24, starts}).map((s) => s.frame)).toEqual([0, 2, 3]);
  });

  it('SVG：认 SMIL 和 CSS 动画，取最长的 dur', () => {
    expect(svgAnimated('<svg><circle><animate attributeName="r" dur="2s"/></circle></svg>')).toBe(true);
    expect(svgAnimated('<svg><style>@keyframes x {}</style></svg>')).toBe(true);
    expect(svgAnimated('<svg><circle r="3"/></svg>')).toBe(false);
    expect(svgDuration('<animate dur="2s"/><animate dur="1500ms"/>', 4)).toBe(2);
    expect(svgDuration('<style>.a { animation: spin 3s linear infinite }</style>', 4)).toBe(3);
    expect(svgDuration('<svg/>', 4)).toBe(4);
    expect([maybeAnimated('a/b.GIF'), maybeAnimated('x.svg?v=1'), maybeAnimated('x.jpg'), maybeAnimated('x.png')]).toEqual([true, true, false, false]);
  });
});

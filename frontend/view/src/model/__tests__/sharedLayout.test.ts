import {describe, expect, it} from 'vitest';
import fixture from '../../../../../tests/fixtures/view-layout-geometry.json';
import type {Board, ProjectData} from '../../types';
import {Model, keyOf} from '../model';
import {merge, split} from '../layoutOps';
import {heightFactor, scaleRows, setRowHeight, setScale} from '../boardStyle';
import {chapters, model} from './fixtures';

describe('shared layout geometry contract (also checked by Python)', () => {
  for (const entry of fixture.cases) it(entry.name, () => {
    const data = {...fixture.data, folds: entry.folds} as unknown as ProjectData;
    const m = new Model(data, {viewer: 'user', only: null, showHidden: false, canvasWidth: 1290});
    const b = {rows: entry.rows, pps: entry.pps, styles: entry.styles, x: 20, y: 30} as Board;
    const result = m.boardLayout(b)!;
    expect({width: result.width, height: result.height}).toEqual(entry.expected);
  });
});

describe('root preferences survive composition', () => {
  it('shrinking different heights honors the minimum without overshooting the target', () => {
    const factor = heightFactor([{laneHeight: 100, count: 1}, {laneHeight: 200, count: 1}], 64);
    const b: Board = {rows: [[1], [10]], x: 0, y: 0, pps: 10,
      styles: {1: {pps: 10, lane_height: 100}, 10: {pps: 20, lane_height: 200}}};
    const resized = scaleRows(b, factor);
    expect(resized.styles![1].lane_height! + resized.styles![10].lane_height!).toBeCloseTo(64, 6);
  });
  it('top and left supply scale; split restores each member without mutating inputs', () => {
    const m = model(chapters());
    const a: Board = setRowHeight({rows: [[1]], x: 0, y: 0, pps: 30}, 100);
    const b: Board = setRowHeight({rows: [[10]], x: 600, y: 400, pps: 50}, 200);
    const merged = merge([a, b], 10, 1, 1, 'above', null, m);
    expect(merged[0].pps).toBe(50);
    expect(m.boardLayout(merged[0])!.sections.map((s) => s.tracks[0].laneHeight)).toEqual([200, 100]);
    const separated = split(merged, 10, m);
    expect(separated.find((x) => keyOf(x) === 1)?.pps).toBe(30);
    expect(separated.find((x) => keyOf(x) === 10)?.pps).toBe(50);
    expect(a.styles?.[1].lane_height).toBe(100);
    expect(b.styles?.[10].lane_height).toBe(200);
  });
  it('size changes invalidate geometry without changing business content', () => {
    const data = chapters(), m = model(data);
    const b: Board = {rows: [[1]], x: 0, y: 0, pps: 30};
    const before = m.boardLayout(b)!;
    const next = m.boardLayout(setRowHeight(setScale(b, 60), 180))!;
    expect(next.width).toBeGreaterThan(before.width);
    expect(next.height).toBeGreaterThan(before.height);
    expect(next.sections[0].tracks[1].items[0].o).toBe(data.layers[1].objects[0]);
    expect(m.boardLayout(b)).toBe(before);
  });
});

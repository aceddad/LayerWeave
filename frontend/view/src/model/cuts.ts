// 接缝：同一条轨道里前后相接的图片、视频（和画布一样按小行排，同一小行里相邻的两个就是一个接缝）
import type {Board} from '../types';
import {kindOf} from './kinds';
import type {Item, Model, Track} from './model';
import {keyOf, lanes, rootsOf} from './model';

export interface CutItem extends Item { root: number; offset: number }
export interface Cut { board: Board; row: number[]; rowIndex: number; track: Track; a: CutItem; b: CutItem; gap: number }

export function cutList(model: Model, boards: Board[], filter: {board?: number | null; begin?: number | null; end?: number | null}): Cut[] {
  const cuts: Cut[] = [];
  for (const b of boards) {
    if (filter.board != null && !rootsOf(b).includes(filter.board)) continue;
    b.rows.forEach((row, rowIndex) => {
      for (const track of model.visibleTracks(row)) {
        const items: CutItem[] = track.parts.flatMap(({layer, seg}) => layer.objects.filter((o) => ['image', 'video'].includes(kindOf(o)))
          .map((o) => ({o, layer, offset: seg.offset, root: seg.root, begin: o.begin + seg.offset, end: o.end + seg.offset, lane: 0})))
          .sort((p, q) => p.begin - q.begin || p.end - q.end || p.o.id - q.o.id);
        const ln = lanes(items), last: CutItem[] = [];
        items.forEach((it, i) => {
          const prev = last[ln[i]];
          if (prev) cuts.push({board: b, row, rowIndex, track, a: prev, b: it, gap: it.begin - prev.end});
          last[ln[i]] = it;
        });
      }
    });
  }
  const lo = filter.begin ?? -Infinity, hi = filter.end ?? Infinity;
  return cuts.filter((c) => c.b.begin >= lo && c.b.begin <= hi);
}

export const cutGroupKey = (c: Cut) => `${keyOf(c.board)}|${c.rowIndex}|${c.track.key}`;

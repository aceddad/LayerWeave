// 接缝：同一条轨道里前后相接的图片、视频（和画布一样按小行排，同一小行里相邻的两个就是一个接缝）；折叠的轨道不算。
// 纯计算，用到的工具函数由宿主给（host.util），测试里传真的进来
import type {PluginHost} from '../../src/plugin/host';
import type {Item, Model, Track} from '../../src/model/model';
import type {Board} from '../../src/types';

export interface CutItem extends Item { root: number; offset: number }
export interface Cut { board: Board; row: number[]; rowIndex: number; track: Track; a: CutItem; b: CutItem; gap: number }
type Util = Pick<PluginHost['util'], 'kindOf' | 'lanes' | 'keyOf' | 'rootsOf'>;

export function cutList(util: Util, model: Model, boards: Board[], filter: {board?: number | null; begin?: number | null; end?: number | null}): Cut[] {
  const cuts: Cut[] = [];
  for (const b of boards) {
    if (filter.board != null && !util.rootsOf(b).includes(filter.board)) continue;
    b.rows.forEach((row, rowIndex) => {
      for (const track of model.visibleTracks(row)) {
        if (model.foldOf(track) != null) continue;          // 折叠的轨道不列接缝
        const items: CutItem[] = track.parts.flatMap(({layer, seg}) => layer.objects.filter((o) => ['image', 'video'].includes(util.kindOf(o)))
          .map((o) => ({o, layer, offset: seg.offset, root: seg.root, begin: o.begin + seg.offset, end: o.end + seg.offset, lane: 0})))
          .sort((p, q) => p.begin - q.begin || p.end - q.end || p.o.id - q.o.id);
        const ln = util.lanes(items), last: CutItem[] = [];
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

export const cutGroupKey = (util: Util, c: Cut) => `${util.keyOf(c.board)}|${c.rowIndex}|${c.track.key}`;

// 键盘 [ ] 的跳转点：下一段开始的地方
export function cutPoints(util: Util, model: Model, board: Board): number[] {
  const set = new Set(cutList(util, model, [board], {}).map((c) => +c.b.begin.toFixed(6)));
  return [...set].sort((p, q) => p - q);
}

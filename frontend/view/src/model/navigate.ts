// 键盘跳转（纯计算）：
// ←/→ 选中同一条轨道上的上一个、下一个对象；没选中对象时，播放头跳到上一个、下一个剪辑点（对象的开头、结尾）
// ↑/↓ 选中上一条、下一条有对象的轨道上离这一刻最近的对象
// [ / ] 播放头跳到上一个、下一个接缝
import type {Board} from '../types';
import type {Item, Model} from './model';

const EPS = 1e-6;

function tracksOf(model: Model, board: Board): Item[][] {
  return (model.boardLayout(board)?.sections ?? []).flatMap((sec) => sec.tracks.map((t) => t.items));
}

function where(model: Model, board: Board, id: number): {tracks: Item[][]; ti: number; ii: number} | null {
  const tracks = tracksOf(model, board);
  for (let ti = 0; ti < tracks.length; ti++) {
    const ii = tracks[ti].findIndex((it) => it.o.id === id);
    if (ii >= 0) return {tracks, ti, ii};
  }
  return null;
}

// 同一轨道上的前后对象（轨道里已按开始时间排好；左右接续时跨段也接着走）
export function stepObject(model: Model, board: Board, id: number, dir: -1 | 1): Item | null {
  const at = where(model, board, id);
  return at ? at.tracks[at.ti][at.ii + dir] ?? null : null;
}

// 相邻轨道上离 t 最近的对象：盖住 t 的优先，否则取离得最近的；中间没有对象的轨道（容器层）跳过
export function stepTrack(model: Model, board: Board, id: number, t: number, dir: -1 | 1): Item | null {
  const at = where(model, board, id);
  if (!at) return null;
  for (let ti = at.ti + dir; ti >= 0 && ti < at.tracks.length; ti += dir) {
    const items = at.tracks[ti];
    if (!items.length) continue;
    const distance = (it: Item) => (it.begin <= t && t < it.end ? 0 : Math.min(Math.abs(it.begin - t), Math.abs(it.end - t)));
    return items.reduce((best, it) => (distance(it) < distance(best) ? it : best));
  }
  return null;
}

// 画板上所有对象的开头和结尾（画板时间，去重排好）
export function editPoints(model: Model, board: Board): number[] {
  const set = new Set<number>();
  for (const items of tracksOf(model, board)) for (const it of items) { set.add(+it.begin.toFixed(6)); set.add(+it.end.toFixed(6)); }
  return [...set].sort((p, q) => p - q);
}

export function stepTime(points: number[], t: number, dir: -1 | 1): number | null {
  if (dir > 0) return points.find((p) => p > t + EPS) ?? null;
  for (let i = points.length - 1; i >= 0; i--) if (points[i] < t - EPS) return points[i];
  return null;
}


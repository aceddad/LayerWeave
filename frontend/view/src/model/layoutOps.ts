// 画板排版的操作：自动摆放、上下拼 / 左右接、拆出、拼走后补空当、靠边吸附。
// 都在拷贝上算，尺寸来自 Model（由数据算出），不量页面。保存由 sync.saveLayout 负责，服务端还会按现有的根再校正一次。
import type {Board} from '../types';
import {GAP, keyOf, rootsOf} from './model';
import type {Model} from './model';
import {rememberStyles, leaderStyle} from './boardStyle';

export type Side = 'above' | 'below' | 'left' | 'right';
interface Box { x: number; w: number }

export const sizeOf = (model: Model, b: Board) => {
  const l = model.boardLayout(b);
  return l ? {w: l.width, h: l.height} : {w: 0, h: 0};
};
const clone = (boards: Board[]): Board[] => boards.map((b) => ({...b, styles: b.styles ? Object.fromEntries(Object.entries(b.styles).map(([r, s]) => [r, {...s}])) : undefined, rows: b.rows.map((r) => [...r])}));
const overlapX = (p: Box, q: Box) => p.x < q.x + q.w && q.x < p.x + p.w;

// 没有位置的画板（第一次打开、AI 刚拆出来的）依次排在已有画板的下方
export function placeAuto(boards: Board[], model: Model): {boards: Board[]; changed: boolean} {
  const out = clone(boards);
  const fixed = out.filter((b) => b.x != null && b.y != null && sizeOf(model, b).h);
  let x = fixed.length ? Math.min(...fixed.map((b) => b.x!)) : 0;
  let y = fixed.length ? Math.max(...fixed.map((b) => b.y! + sizeOf(model, b).h)) + GAP : 0;
  let changed = false;
  for (const b of out) {
    if (b.x != null && b.y != null) continue;
    const {h} = sizeOf(model, b);
    if (!h) continue;                                     // 现在不画的（收起的批注层）等显示时再摆
    b.x = x; b.y = y; y += h + GAP; changed = true;
  }
  return {boards: out, changed};
}

// 画板变高后，把它正下方的画板往下推
function pushBelow(boards: Board[], target: Board, oldH: number, delta: number, model: Model) {
  if (!delta) return;
  const w = sizeOf(model, target).w;
  for (const o of boards) {
    if (o === target || o.y == null || o.y < target.y! + oldH - 1) continue;
    if (overlapX({x: o.x!, w: sizeOf(model, o).w}, {x: target.x!, w})) o.y += delta;
  }
}

// 被拼走的画板原来的位置留下空当：正下方的画板往上补，补到碰到上面的画板为止（和拆出时往下推对应）
function closeGap(boards: Board[], gap: {x: number; y: number; w: number; h: number}, model: Model) {
  const box = new Map(boards.map((b) => [b, {x: b.x ?? 0, ...sizeOf(model, b)}]));
  const below = boards.filter((o) => o.y != null && o.y >= gap.y + gap.h - 1 && overlapX(box.get(o)!, gap)).sort((p, q) => p.y! - q.y!);
  for (const o of below) {
    const above = boards.filter((p) => p !== o && p.y != null && p.y < o.y! && overlapX(box.get(p)!, box.get(o)!)).map((p) => p.y! + box.get(p)!.h + GAP);
    const floor = Math.max(gap.y, ...above);
    if (floor < o.y!) o.y = Math.max(floor, o.y! - gap.h - GAP);
  }
}

// 把 moving 整块拼到 target 里 rootId 那一行 / 那一段的旁边。above / below：新的行（同时）；left / right：接在前后（接续）
export function merge(boards: Board[], movingKey: number, targetKey: number, rootId: number, side: Side,
                      gap: {x: number; y: number; w: number; h: number} | null, model: Model): Board[] {
  const out = clone(boards);
  const moving = out.find((b) => keyOf(b) === movingKey)!, target = out.find((b) => keyOf(b) === targetKey)!;
  const oldH = sizeOf(model, target).h;
  target.styles = {...rememberStyles(target).styles, ...rememberStyles(moving).styles};
  const ri = target.rows.findIndex((r) => r.includes(rootId));
  if (side === 'above' || side === 'below') target.rows.splice(ri + (side === 'below' ? 1 : 0), 0, ...moving.rows);
  else { const row = target.rows[ri]; row.splice(row.indexOf(rootId) + (side === 'right' ? 1 : 0), 0, ...moving.rows[0]); }
  target.pps = leaderStyle(target).pps;
  out.splice(out.indexOf(moving), 1);
  pushBelow(out, target, oldH, sizeOf(model, target).h - oldH, model);
  if (gap) closeGap(out, gap, model);
  return out;
}

// 拆出：新画板放在原画板正下方，把更下面的画板往下推
export function split(boards: Board[], rootId: number, model: Model): Board[] {
  const out = clone(boards);
  const b = out.find((x) => rootsOf(x).includes(rootId))!;
  const old = sizeOf(model, b), oldBottom = (b.y ?? 0) + old.h;
  b.styles = rememberStyles(b).styles;
  const style = b.styles![rootId];
  delete b.styles![rootId];
  b.rows = b.rows.map((r) => r.filter((x) => x !== rootId)).filter((r) => r.length);
  b.pps = leaderStyle(b).pps;
  const nb: Board = {rows: [[rootId]], x: b.x, y: (b.y ?? 0) + sizeOf(model, b).h + GAP, pps: style.pps, styles: {[rootId]: style}};
  out.splice(out.indexOf(b) + 1, 0, nb);
  const delta = nb.y! + sizeOf(model, nb).h - oldBottom;
  if (delta > 0) for (const o of out) {
    if (o !== b && o !== nb && o.y != null && o.y >= oldBottom - 1 && overlapX({x: o.x!, w: sizeOf(model, o).w}, {x: b.x ?? 0, w: old.w})) o.y += delta;
  }
  return out;
}

// 折叠、展开改变高度后，下方画板跟着挪
export function afterResize(boards: Board[], key: number, oldH: number, model: Model): Board[] {
  const out = clone(boards);
  const target = out.find((b) => keyOf(b) === key);
  if (target) pushBelow(out, target, oldH, sizeOf(model, target).h - oldH, model);
  return out;
}

// 数据变了（AI 折叠、加了层）以后画板可能变高、压到下面的画板：从上往下，压到的往下挪开。只往下推，不往上收
export function separate(boards: Board[], model: Model): {boards: Board[]; changed: boolean} {
  const out = clone(boards);
  const placed = out.filter((b) => b.x != null && b.y != null && sizeOf(model, b).h).sort((p, q) => p.y! - q.y! || p.x! - q.x!);
  let changed = false;
  placed.forEach((b, i) => {
    const me = {x: b.x!, w: sizeOf(model, b).w};
    for (const o of placed.slice(0, i)) {
      const h = sizeOf(model, o).h;
      if (overlapX(me, {x: o.x!, w: sizeOf(model, o).w}) && b.y! < o.y! + h && o.y! < b.y! + sizeOf(model, b).h) {
        b.y = o.y! + h + GAP;
        changed = true;
      }
    }
  });
  return {boards: out, changed};
}

// 靠近别的画板边缘时吸附：左右上下对齐，或隔一个间距并排。只是摆放，不改变时间
export function snap(pos: {x: number; y: number}, key: number, boards: Board[], model: Model, zoom: number): {x: number; y: number} {
  const me = boards.find((b) => keyOf(b) === key);
  if (!me) return pos;
  const {w, h} = sizeOf(model, me), tol = 10 / zoom;
  let bx: number | null = null, by: number | null = null;
  for (const o of boards) {
    if (o === me || o.x == null || o.y == null) continue;
    const s = sizeOf(model, o);
    if (!s.h) continue;
    for (const x of [o.x, o.x + s.w - w, o.x + s.w + GAP, o.x - w - GAP]) if (Math.abs(pos.x - x) < tol && (bx == null || Math.abs(pos.x - x) < Math.abs(pos.x - bx))) bx = x;
    for (const y of [o.y, o.y + s.h - h, o.y + s.h + GAP, o.y - h - GAP]) if (Math.abs(pos.y - y) < tol && (by == null || Math.abs(pos.y - y) < Math.abs(pos.y - by))) by = y;
  }
  return {x: bx ?? pos.x, y: by ?? pos.y};
}

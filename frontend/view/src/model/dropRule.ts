import {tr as defaultTranslate, translator} from '../i18n/core';
import type {Translate, Locale} from '../i18n/types';
// 拖着画板经过另一块画板时怎么拼（纯计算；鼠标落在哪一行、哪个时刻由 canvas/drop.ts 从页面换算好传进来）：
// 落在某一段的开头或结尾附近 → 左右接续；落在一行的中间 → 拼在这一行的上方或下方（同时）
import type {Board} from '../types';
import type {Side} from './layoutOps';
import {keyOf} from './model';
import type {Model} from './model';

export interface Drop {
  targetKey: number; root: number; side: Side; ok: boolean; reason: string;
  rowIndex: number; at: number | null;                    // at：左右接时接缝在画板上的时间
}

// t：鼠标下的画板时间；onTracks：落在轨道区（不是名字列、标题）；upperHalf：落在这一行的上半部分；zoom：画布缩放
export function decideDrop(model: Model, moving: Board, target: Board, rowIndex: number, t: number,
                           onTracks: boolean, upperHalf: boolean, zoom: number, tr: Translate = defaultTranslate): Drop {
  const row = target.rows[rowIndex], segs = model.segments(row), pps = model.pps(target);
  const edge = (s: {begin: number; end: number}) => Math.max((s.end - s.begin) * 0.15, 36 / pps / zoom);   // 至少 36 屏幕像素宽的接续区
  let side: Side | null = null, root = row[0], at: number | null = null;
  const first = segs[0], last = segs[segs.length - 1];
  if (onTracks) {
    if (t < first.begin + edge(first)) { side = 'left'; root = first.root; at = first.offset; }
    else if (t > last.end - edge(last)) { side = 'right'; root = last.root; at = last.end; }
    else for (const s of segs.slice(0, -1)) if (Math.abs(t - s.end) < edge(s)) { side = 'right'; root = s.root; at = s.end; break; }
  }
  if (!side) side = upperHalf ? 'above' : 'below';
  const ka = model.root(keyOf(moving))?.key, kb = model.root(keyOf(target))?.key;
  const unitA = model.unitOfRoot(keyOf(moving)) || tr("common.noUnit"), unitB = model.unitOfRoot(keyOf(target)) || tr("common.noUnit");
  let reason = '';
  if (ka == null || ka !== kb) reason = tr("drop.differentUnits", {value1: unitA, value2: unitB});
  else if ((side === 'left' || side === 'right') && moving.rows.length > 1) reason = tr("drop.multipleRows");
  return {targetKey: keyOf(target), root, side, ok: !reason, reason, rowIndex, at};
}

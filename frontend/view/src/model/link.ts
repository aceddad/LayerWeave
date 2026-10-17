// "复制链接"：把现在看的位置写成视图地址的参数。截图工具 view_screenshot --link 读同样的参数，拍到同一个画面
import {SIDES} from '../types';
import type {Side, View} from '../types';

export interface LinkState {
  project: number; view: View; side: Side; lang?: 'zh' | 'en';
  board?: number | null; range?: [number, number] | null; playhead?: number | null; select?: number | null;
  layers?: Set<number> | null; note?: number | null; changes?: number | null;
  walk?: {from: string; direction: string; depth: number} | null;
  pluginParams?: URLSearchParams;
}

const OWN_KEYS = new Set(['lang', 'view', 'board', 'begin', 'end', 'playhead', 'select', 'focus', 'note', 'changes', 'layers', 'side', 'links',
  'walk', 'walkdir', 'walkdepth', 'project', 'record', 'capture', 'full', 'tree', 'as', 'media']);

const num = (v: number) => String(+v.toFixed(3));

export function linkQuery(s: LinkState): string {
  const q = new URLSearchParams({project: String(s.project)});
  if (s.lang) q.set('lang', s.lang);
  if (s.view !== 'canvas' || !SIDES.includes(s.side)) s.pluginParams?.forEach((value, key) => {
    if (!OWN_KEYS.has(key) && /^[a-z][a-z0-9_]{0,31}$/.test(key)) q.set(key, value);
  });
  if (s.view !== 'canvas') q.set('view', s.view);
  if (s.board != null) q.set('board', String(s.board));
  if (s.view === 'canvas' && s.range) { q.set('begin', num(s.range[0])); q.set('end', num(s.range[1])); }
  if (s.playhead != null) q.set('playhead', num(s.playhead));
  if (s.select != null) q.set('select', String(s.select));
  if (s.layers?.size) q.set('layers', [...s.layers].sort((p, q2) => p - q2).join(','));
  if (s.side === 'notes') { if (s.note != null) q.set('note', String(s.note)); else q.set('side', 'notes'); }
  if (s.side === 'changes' && s.changes) q.set('changes', String(s.changes));
  if (!SIDES.includes(s.side)) q.set('side', s.side);   // 插件的侧栏
  if (s.side === 'walk' && s.walk) {
    q.set('walk', s.walk.from);
    if (s.walk.direction !== 'both') q.set('walkdir', s.walk.direction);
    if (s.walk.depth !== 3) q.set('walkdepth', String(s.walk.depth));
  }
  return q.toString();
}

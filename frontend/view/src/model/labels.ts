// 给人看的指称：#16 小球落下（视频）、层 #5 字幕、项目 2 的对象 #7
import type {Bind, Ref} from '../types';
import type {Model} from './model';

export function refLabel(model: Model, ref: Ref): string {
  if (ref.project !== model.project) return `项目 ${ref.project} 的${ref.kind === 'layer' ? '层' : '对象'} #${ref.id}`;
  if (ref.kind === 'layer') return `层 #${ref.id} ${model.layer(ref.id)?.name ?? ''}`.trim();
  const o = model.object(ref.id);
  return o ? `#${o.id} ${o.name || o.text || ''}（${o.layer.name || '层 ' + o.layer.id}）` : `对象 #${ref.id}（已不存在）`;
}

export const refExists = (model: Model, ref: Ref) =>
  ref.project !== model.project || (ref.kind === 'object' ? !!model.object(ref.id) : !!model.layer(ref.id));

const same = (model: Model, ref: Ref, kind: Ref['kind'], id: number) => ref.kind === kind && ref.project === model.project && ref.id === id;

// 这个对象或层的关系：→ 它指向的，← 指向它的。批注发出的关联不算（批注另列在"批注"里）
export interface Relation { dir: '→' | '←'; ref: Ref; tips: string }
export function relationsOf(model: Model, kind: Ref['kind'], id: number): Relation[] {
  const isNote = (ref: Ref) => ref.kind === 'object' && ref.project === model.project && model.object(ref.id)?.layer.role === 'note';
  return model.data.binds.flatMap((b): Relation[] => (same(model, b.source, kind, id) ? [{dir: '→', ref: b.target, tips: b.tips}]
    : same(model, b.target, kind, id) && !isNote(b.source) ? [{dir: '←', ref: b.source, tips: b.tips}] : []));
}

// 另一头在别的项目的关系（色块角上标 ↗）
export function externalLabels(model: Model): Map<number, string[]> {
  const out = new Map<number, string[]>();
  const add = (b: Bind, mine: Ref, other: Ref) => {
    if (mine.kind !== 'object' || mine.project !== model.project || other.project === model.project) return;
    if (!out.has(mine.id)) out.set(mine.id, []);
    out.get(mine.id)!.push(refLabel(model, other) + (b.tips ? '：' + b.tips : ''));
  };
  for (const b of model.data.binds) { add(b, b.source, b.target); add(b, b.target, b.source); }
  return out;
}

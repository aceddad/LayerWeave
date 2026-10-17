import {tr as defaultTranslate, translator} from '../i18n/core';
import type {Translate, Locale} from '../i18n/types';
// 给人看的指称：#16 小球落下（视频）、层 #5 字幕、项目 2 的对象 #7
import type {Bind, Ref} from '../types';
import type {Model} from './model';

export function refLabel(model: Model, ref: Ref, tr: Translate = defaultTranslate): string {
  if (ref.project !== model.project) return tr("ref.otherProject", {value1: ref.project, value2: ref.kind === 'layer' ? tr("common.layer") : tr("common.object"), value3: ref.id});
  if (ref.kind === 'layer') return tr("ref.layer", {value1: ref.id, value2: model.layer(ref.id)?.name ?? ''}).trim();
  const o = model.object(ref.id);
  return o ? tr("ref.object", {value1: o.id, value2: o.name || o.text || '', value3: o.layer.name || tr("common.layerPrefix") + o.layer.id}) : tr("ref.missingObject", {value1: ref.id});
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
export function externalLabels(model: Model, tr: Translate = defaultTranslate): Map<number, string[]> {
  const out = new Map<number, string[]>();
  const add = (b: Bind, mine: Ref, other: Ref) => {
    if (mine.kind !== 'object' || mine.project !== model.project || other.project === model.project) return;
    if (!out.has(mine.id)) out.set(mine.id, []);
    out.get(mine.id)!.push(refLabel(model, other, tr) + (b.tips ? '：' + b.tips : ''));
  };
  for (const b of model.data.binds) { add(b, b.source, b.target); add(b, b.target, b.source); }
  return out;
}

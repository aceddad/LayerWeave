import {currentLocale} from '../i18n';
import {tr, useI18n} from '../i18n';
// 改动：最近几次操作改了什么；打开时画布上标出改过的对象，删除或移动前的位置画成虚线框
import {selectObject} from '../actions';
import {focusObject} from '../camera';
import type {Model} from '../model/model';
import {ago, fmt} from '../model/units';
import {useShallow} from 'zustand/react/shallow';
import {setState, useModel, useStore} from '../store';
import {loadChanges} from '../sync';
import type {ChangeItem, ChangeRecord} from '../types';

function describe(model: Model, it: ChangeItem): string[] {
  const unitOf = (layer?: number) => model.unitOfRoot(layer != null ? model.layer(layer)?.root : null);
  const pos = (r: ChangeRecord) => `${fmt(r.begin, unitOf(r.layer))} – ${fmt(r.end, unitOf(r.layer))}`;
  const layerName = (id?: number) => (id != null ? model.layer(id)?.name || tr("common.layerId", {value1: id}) : '');
  const out: string[] = [];
  if (it.kind === 'object' && it.action === 'update' && it.before && it.after) {
    if (it.before.layer !== it.after.layer) out.push(`${layerName(it.before.layer)} → ${layerName(it.after.layer)}`);
    if (it.before.begin !== it.after.begin || it.before.end !== it.after.end) out.push(`${pos(it.before)} → ${pos(it.after)}`);
    for (const x of it.information ?? []) out.push(`${x.key}：${x.before ?? '—'} → ${x.after ?? '—'}`);
    const other = (it.fields ?? []).filter((f) => !['layer', 'begin', 'end', 'information'].includes(f));
    if (other.length) out.push(tr("changes.changed") + ": " + other.join('、'));
  } else if (it.kind === 'object') {
    const rec = it.after ?? it.before ?? {};
    out.push(`${layerName(rec.layer)} · ${pos(rec)}`);
  } else if (it.action === 'update' && it.fields?.length) out.push(tr("changes.changed") + ": " + it.fields.join('、'));
  return out;
}

export function ChangesPanel() {
  useI18n();
  const model = useModel();
  const {ops, limit} = useStore(useShallow((s) => ({ops: s.changeOps, limit: s.changeLimit})));
  if (!model) return null;
  const verb = {create: tr("changes.created"), update: tr("changes.updated"), delete: tr("changes.deleted")};
  const what = {object: '', layer: tr("common.layer"), bind: tr("common.relation"), project: tr("common.project")};
  return (
    <section>
      <h2>{tr("changes.recent")} <select value={limit} onChange={async (e) => { setState({changeLimit: Number(e.target.value)}); await loadChanges(); }}>
        {[1, 5, 10, 30, 100].map((n) => <option key={n} value={n}>{n}</option>)}
      </select>  {tr("changes.operationsSuffix")}</h2>
      <p className="hint legend"><i className="chg-n">1</i>  {tr("changes.changedHint")}　<span className="ghost-key">{tr("changes.dashed")}</span>  {tr("changes.previousPosition")}</p>
      {!ops.length && <p className="hint">{tr("changes.empty")}</p>}
      {ops.map((op, i) => (
        <div key={op.operation_id} className="op">
          <div className="op-head"><b>{i + 1}</b>{ago(op.at, currentLocale())}{op.undo_of ? tr("changes.undo") : ''} · {op.items.length}  {tr("changes.itemsSuffix")}</div>
          {op.items.map((it, j) => {
            const rec = it.after ?? it.before ?? {};
            const label = rec.name || rec.text || (rec.source || '').split(/[\\/]/).pop() || '';
            const exists = it.kind === 'object' && !!model.object(it.id);
            const go = it.kind === 'object' ? () => (exists ? selectObject(it.id) : focusObject(it.id, true)) : undefined;
            const details = describe(model, it);
            return (
              <div key={j} className={`chg-item ${it.action}${go ? ' goto' : ''}`} onClick={go}>
                <span className="verb">{verb[it.action]}{what[it.kind]}</span> #{it.id} {label}
                {details.length > 0 && <div className="det">{details.map((d, k) => <div key={k}>{d}</div>)}</div>}
              </div>
            );
          })}
        </div>
      ))}
    </section>
  );
}

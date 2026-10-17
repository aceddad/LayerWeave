import {tr, useI18n} from '../i18n';
// 沿读：从一个对象或一楼批注出发，顺着关联一步步往外走（服务端 view/walk.py，和 AI 用的 view_walk 是同一份结果）。
// 按步数分组列出，每一步写明是从哪一个、顺着哪条关联到的。「去看」：对象就选中并飞过去，层就对准它，批注就对准它那一楼；
// 「从这里读」：换成从这一步出发
import {useShallow} from 'zustand/react/shallow';
import {goToTarget, locateNote, selectObject, startWalk} from '../actions';
import {Thumb} from '../canvas/Media';
import {kindOf} from '../model/kinds';
import type {Model} from '../model/model';
import {fmt} from '../model/units';
import {useModel, useStore} from '../store';
import type {WalkDirection, WalkStep, WalkVia} from '../types';

const DIRECTIONS: {value: WalkDirection; label: string}[] = [
  {value: 'both', label: "relations.both"}, {value: 'out', label: "relations.out"}, {value: 'in', label: "relations.in"},
];

export function label(step: WalkStep): string {
  if (step.status === 'other_project') return tr("ref.otherProject", {value1: step.project, value2: step.kind === 'layer' ? tr("common.layer") : tr("common.object"), value3: step.id});
  if (step.status === 'missing') return tr("relations.deleted", {value1: step.kind === 'layer' ? tr("common.layer") : tr("common.object"), value2: step.id});
  if (step.kind === 'layer') return tr("relations.layer", {value1: step.id, value2: step.name});
  if (step.note) return tr("relations.note", {value1: step.id});
  const name = step.name || (step.source ? step.source.split(/[\\/]/).pop() : '');
  return name ? `#${step.id}「${name}」` : `#${step.id}`;
}

function facts(step: WalkStep): string[] {
  if (step.status !== 'found') return [step.status === 'missing' ? tr("relations.missing") : tr("relations.otherProject")];
  if (step.kind === 'layer') return [step.type, ...(step.unit ? [tr("relations.unit", {value1: step.unit})] : [])];
  if (step.note) {
    const {author, reply, status, span} = step.note;
    return [author || tr("notes.anonymous"), reply ? tr("notes.reply") : status === 'done' ? tr("notes.resolved") : tr("notes.open"), ...(span ? [tr("relations.selectedRange", {value1: fmt(span.begin, step.unit), value2: fmt(span.end, step.unit)})] : [])];
  }
  return [step.type, ...(step.layer ? [tr("relations.parentLayer", {value1: step.layer.name})] : []), `${fmt(step.begin, step.unit)} – ${fmt(step.end, step.unit)}`];
}

const via = (v: WalkVia) => tr("relations.via", {value1: v.arrow === 'from' ? tr("relations.incoming", {value1: (v.other.split(':').pop() ?? '')}) : tr("relations.outgoing", {value1: (v.other.split(':').pop() ?? '')}), value2: v.tips ? `（${v.tips}）` : ''});

function go(step: WalkStep) {
  if (step.kind === 'layer') return goToTarget({kind: 'layer', project: step.project, id: step.id}, null);
  if (step.note) return locateNote(step.id);
  return selectObject(step.id);
}

function Step({step, model, project, frames}: {step: WalkStep; model: Model; project: number; frames: boolean}) {
  useI18n();
  const o = step.kind === 'object' ? model.object(step.id) : undefined;
  const image = o && kindOf(o) === 'image' && o.media?.available;
  const found = step.status === 'found';
  return (
    <div className={`card walk-step${found ? '' : ' gone'}`}>
      <div className="meta">
        <b>{label(step)}</b> · {facts(step).join(' · ')}
        {step.source && !step.note && <div className="walk-file" title={step.source}>{tr("kind.file")} {step.source}</div>}
      </div>
      {image && <div className="walk-thumb"><Thumb project={project} o={o} width={320} frames={frames} /></div>}
      {step.text && <div className="walk-text" title={step.text}>{step.text}</div>}
      {step.via.map((v) => <div key={v.bind} className="walk-via">{via(v)}</div>)}
      {found && step.project === project && <div className="note-row">
        <span className="grow" />
        <button onClick={() => go(step)} title={tr("relations.locateHint")}>{tr("relations.go")}</button>
        {step.depth > 0 && <button onClick={() => startWalk(step.ref)} title={tr("relations.restartHint")}>{tr("relations.restart")}</button>}
      </div>}
    </div>
  );
}

export function WalkPanel() {
  useI18n();
  const model = useModel();
  const {walk, result, project, frames} = useStore(useShallow((s) => ({walk: s.walk, result: s.walkResult, project: s.project, frames: s.frames})));
  if (!walk) return (
    <section>
      <h2>{tr("relations.title.variant")}</h2>
      <p className="hint">{tr("relations.emptyHint")}</p>
    </section>
  );
  const steps = result?.steps ?? [];
  const depths = [...new Set(steps.map((s) => s.depth))];
  return (
    <section>
      <h2>{tr("relations.title.variant")} <small>{steps.length ? tr("relations.summary", {value1: label(steps[0]), value2: steps.length}) : tr("common.loading")}</small></h2>
      <div className="note-row filters">
        {DIRECTIONS.map((d) => <button key={d.value} className={walk.direction === d.value ? 'on' : ''} onClick={() => startWalk(walk.from, {direction: d.value})}>{tr(d.label)}</button>)}
        <span className="grow" />
        <label title={tr("relations.depthHint")}>{tr("relations.depth")} <select value={walk.depth} onChange={(e) => startWalk(walk.from, {depth: Number(e.target.value)})}>
          {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
        </select></label>
      </div>
      {result && (result.loops > 0 || result.beyond > 0 || result.skipped > 0) && <p className="hint">
        {result.loops > 0 && tr("relations.loops", {value1: result.loops})}
        {result.beyond > 0 && tr("relations.beyond", {value1: result.depth, value2: result.beyond})}
        {result.skipped > 0 && tr("relations.limit", {value1: result.max_nodes, value2: result.skipped})}
      </p>}
      {model && project != null && depths.map((d) => <div key={d}>
        <h3>{d === 0 ? tr("relations.start") : tr("relations.step", {value1: d})}</h3>
        {steps.filter((s) => s.depth === d).map((s) => <Step key={s.ref} step={s} model={model} project={project} frames={frames} />)}
      </div>)}
    </section>
  );
}

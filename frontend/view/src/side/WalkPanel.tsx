// 沿着读：从一个对象或一楼批注出发，顺着关联一步步往外走（服务端 view/walk.py，和 AI 用的 view_walk 是同一份结果）。
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
  {value: 'both', label: '两个方向'}, {value: 'out', label: '它指着谁'}, {value: 'in', label: '谁指着它'},
];

export function label(step: WalkStep): string {
  if (step.status === 'other_project') return `项目 ${step.project} 的${step.kind === 'layer' ? '层' : '对象'} #${step.id}`;
  if (step.status === 'missing') return `${step.kind === 'layer' ? '层' : '对象'} #${step.id}（已删除）`;
  if (step.kind === 'layer') return `层 #${step.id}「${step.name}」`;
  if (step.note) return `批注 #${step.id}`;
  const name = step.name || (step.source ? step.source.split(/[\\/]/).pop() : '');
  return name ? `#${step.id}「${name}」` : `#${step.id}`;
}

function facts(step: WalkStep): string[] {
  if (step.status !== 'found') return [step.status === 'missing' ? '已经不在了' : '别的项目，没有接着走'];
  if (step.kind === 'layer') return [step.type, ...(step.unit ? [`单位 ${step.unit}`] : [])];
  if (step.note) {
    const {author, reply, status, span} = step.note;
    return [author || '没署名', reply ? '回复' : status === 'done' ? '已处理' : '待处理', ...(span ? [`圈的是 ${fmt(span.begin, step.unit)} – ${fmt(span.end, step.unit)}`] : [])];
  }
  return [step.type, ...(step.layer ? [`层「${step.layer.name}」`] : []), `${fmt(step.begin, step.unit)} – ${fmt(step.end, step.unit)}`];
}

const via = (v: WalkVia) => `${v.arrow === 'from' ? `← #${v.other.split(':').pop()} 指着它` : `→ 它指着 #${v.other.split(':').pop()}`}${v.tips ? `（${v.tips}）` : ''}`;

function go(step: WalkStep) {
  if (step.kind === 'layer') return goToTarget({kind: 'layer', project: step.project, id: step.id}, null);
  if (step.note) return locateNote(step.id);
  return selectObject(step.id);
}

function Step({step, model, project, frames}: {step: WalkStep; model: Model; project: number; frames: boolean}) {
  const o = step.kind === 'object' ? model.object(step.id) : undefined;
  const image = o && kindOf(o) === 'image' && o.media?.available;
  const found = step.status === 'found';
  return (
    <div className={`card walk-step${found ? '' : ' gone'}`}>
      <div className="meta">
        <b>{label(step)}</b> · {facts(step).join(' · ')}
        {step.source && !step.note && <div className="walk-file" title={step.source}>文件 {step.source}</div>}
      </div>
      {image && <div className="walk-thumb"><Thumb project={project} o={o} width={320} frames={frames} /></div>}
      {step.text && <div className="walk-text" title={step.text}>{step.text}</div>}
      {step.via.map((v) => <div key={v.bind} className="walk-via">{via(v)}</div>)}
      {found && step.project === project && <div className="note-row">
        <span className="grow" />
        <button onClick={() => go(step)} title="镜头过去：对象选中，层对准，批注对准它那一楼">去看</button>
        {step.depth > 0 && <button onClick={() => startWalk(step.ref)} title="换成从这一步出发">从这里读</button>}
      </div>}
    </div>
  );
}

export function WalkPanel() {
  const model = useModel();
  const {walk, result, project, frames} = useStore(useShallow((s) => ({walk: s.walk, result: s.walkResult, project: s.project, frames: s.frames})));
  if (!walk) return (
    <section>
      <h2>沿着读</h2>
      <p className="hint">点选一个对象（详情在「此刻」里），或者在批注的楼主卡片上点「沿着读」：从它出发，顺着关联一步步往外读——它指着谁、谁指着它、再往外一步……批注和回复也是关联，楼也能顺着读。</p>
    </section>
  );
  const steps = result?.steps ?? [];
  const depths = [...new Set(steps.map((s) => s.depth))];
  return (
    <section>
      <h2>沿着读 <small>{steps.length ? `从 ${label(steps[0])} 出发，列出 ${steps.length} 个` : '读取中……'}</small></h2>
      <div className="note-row filters">
        {DIRECTIONS.map((d) => <button key={d.value} className={walk.direction === d.value ? 'on' : ''} onClick={() => startWalk(walk.from, {direction: d.value})}>{d.label}</button>)}
        <span className="grow" />
        <label title="走几步：0 只看起点">步数 <select value={walk.depth} onChange={(e) => startWalk(walk.from, {depth: Number(e.target.value)})}>
          {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
        </select></label>
      </div>
      {result && (result.loops > 0 || result.beyond > 0 || result.skipped > 0) && <p className="hint">
        {result.loops > 0 && `另有 ${result.loops} 条关联连在已经列出的东西之间（成环，没有重复列）。`}
        {result.beyond > 0 && `第 ${result.depth} 步的东西还连着 ${result.beyond} 条关联没走，步数调大可以接着读。`}
        {result.skipped > 0 && `到了 ${result.max_nodes} 个的上限，还有 ${result.skipped} 个没列出。`}
      </p>}
      {model && project != null && depths.map((d) => <div key={d}>
        <h3>{d === 0 ? '起点' : `第 ${d} 步`}</h3>
        {steps.filter((s) => s.depth === d).map((s) => <Step key={s.ref} step={s} model={model} project={project} frames={frames} />)}
      </div>)}
    </section>
  );
}

// 接缝页：同一条轨道里前后相接的图片和视频，上一段的最后一帧和下一段的第一帧并排，用来查衔接
import {useEffect} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {selectObject} from '../actions';
import {Frame, Thumb} from '../canvas/Media';
import {markReady} from '../capture';
import {cutGroupKey, cutList} from '../model/cuts';
import type {Cut, CutItem} from '../model/cuts';
import {kindOf, lastAt} from '../model/kinds';
import type {Model} from '../model/model';
import {fmt, fmtSpan, isSec} from '../model/units';
import {numParam} from '../params';
import {useModel, useStore} from '../store';

function Shot({model, it, end, project, frames}: {model: Model; it: CutItem; end: boolean; project: number; frames: boolean}) {
  const o = it.o, unit = model.unitOfRoot(it.root);
  if (o.media && !o.media.available) return <div className="shot missing">文件不存在<br />{o.media.source}</div>;
  if (!o.media?.url) return <div className="shot missing">没有文件</div>;
  if (kindOf(o) === 'image') return <div className="shot"><Thumb project={project} o={o} width={640} frames={frames} /></div>;
  return <div className="shot"><Frame project={project} o={o} at={end ? lastAt(o, isSec(unit)) : 0.05} frames={frames} /></div>;
}

function CutRow({model, cut, project, frames}: {model: Model; cut: Cut; project: number; frames: boolean}) {
  const unit = model.unitOfRoot(cut.a.root);
  const what = (it: CutItem, end: boolean) => (kindOf(it.o) === 'video' ? (end ? '最后一帧' : '第一帧') : '图片');
  const when = (it: CutItem, t: number) => fmt(t - it.offset, model.unitOfRoot(it.root)) + (it.offset ? `（画板 ${fmt(t, unit)}）` : '');
  const gap = Math.abs(cut.gap) < 1e-6 ? '紧接' : cut.gap > 0 ? `中间空 ${fmtSpan(cut.gap, unit)}` : `叠了 ${fmtSpan(-cut.gap, unit)}`;
  const name = (it: CutItem) => `#${it.o.id} ${it.o.name || (it.o.media?.source || '').split(/[\\/]/).pop()}`;
  return (
    <div className="cut" onClick={() => selectObject(cut.b.o.id)}>
      <figure><Shot model={model} it={cut.a} end project={project} frames={frames} />
        <figcaption>{name(cut.a)} 的{what(cut.a, true)}<br /><small>结束于 {when(cut.a, cut.a.end)}</small></figcaption></figure>
      <div className="cut-mid"><b>→</b><small>{gap}</small>
        {cut.a.root !== cut.b.root && <small className="cross">跨段：{model.nameOf(cut.a.root)} → {model.nameOf(cut.b.root)}</small>}</div>
      <figure><Shot model={model} it={cut.b} end={false} project={project} frames={frames} />
        <figcaption>{name(cut.b)} 的{what(cut.b, false)}<br /><small>开始于 {when(cut.b, cut.b.begin)}</small></figcaption></figure>
    </div>
  );
}

export function CutsView() {
  const model = useModel();
  const {boards, project, frames} = useStore(useShallow((s) => ({boards: s.boards, project: s.project!, frames: s.frames})));
  useEffect(() => { if (model) markReady(); }, [model]);
  if (!model) return null;
  const cuts = cutList(model, boards, {board: numParam('board'), begin: numParam('begin'), end: numParam('end')});
  const groups = new Map<string, Cut[]>();
  for (const c of cuts) { const key = cutGroupKey(c); if (!groups.has(key)) groups.set(key, []); groups.get(key)!.push(c); }
  return (
    <main className="cuts-view">
      {!cuts.length && <p className="hint">没有接缝：同一条轨道里至少要有前后两个图片或视频。</p>}
      {[...groups.entries()].map(([key, list]) => {
        const c = list[0], where = c.row.map((r) => model.nameOf(r)).join(' → ') + (c.track.key ? ' · ' + (c.track.name || c.track.type) : '');
        return <section key={key} className="cut-group">
          <h3>{where} <small>{list.length} 个接缝</small></h3>
          {list.map((cut) => <CutRow key={`${cut.a.o.id}-${cut.b.o.id}`} model={model} cut={cut} project={project} frames={frames} />)}
        </section>;
      })}
    </main>
  );
}

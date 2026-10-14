// 接缝插件（视图的第一个插件）：同一条轨道里前后相接的图片和视频，上一段的最后一帧和下一段的第一帧并排，用来查衔接——
// 比如上一段球落在地上，下一段却从桌上开始。另外给键盘 [ ] 提供跳转点（接缝的时刻）。
// 编译成 view/plugins/cuts/plugin.js（vite.plugins.config.ts），是视图的内置插件（view/plugins.py 的 BUILTIN），本机清单里可以关掉。
// 只用宿主给的东西（host）：React 是宿主那一份，JSX 编译成 h(...)，h 在插件被加载时从 host.React 拿
import type {PluginHost, ViewPlugin} from '../../src/plugin/host';
import type {Model} from '../../src/model/model';
import {cutGroupKey, cutList, cutPoints} from './cuts';
import type {Cut, CutItem} from './cuts';
import css from './cuts.css?raw';

let host: PluginHost;
// JSX 编译成 h(...)、<>…</> 编译成 Fragment（vite.plugins.config.ts）；类型检查按 react-jsx，看不见这两个的用法
let h: PluginHost['React']['createElement'];
let Fragment: PluginHost['React']['Fragment'];

function Shot({model, it, end, project, frames}: {model: Model; it: CutItem; end: boolean; project: number; frames: boolean}) {
  const {Thumb, Frame} = host.components, {kindOf, lastAt, isSec} = host.util;
  const o = it.o, unit = model.unitOfRoot(it.root);
  if (o.media && !o.media.available) return <div className="shot missing">文件不存在<br />{o.media.source}</div>;
  if (!o.media?.url) return <div className="shot missing">没有文件</div>;
  if (kindOf(o) === 'image') return <div className="shot"><Thumb project={project} o={o} width={640} frames={frames} /></div>;
  return <div className="shot"><Frame project={project} o={o} at={end ? lastAt(o, isSec(unit)) : 0.05} frames={frames} /></div>;
}

function CutRow({model, cut, project, frames}: {model: Model; cut: Cut; project: number; frames: boolean}) {
  const {kindOf, fmt, fmtSpan} = host.util;
  const unit = model.unitOfRoot(cut.a.root);
  const what = (it: CutItem, end: boolean) => (kindOf(it.o) === 'video' ? (end ? '最后一帧' : '第一帧') : '图片');
  const when = (it: CutItem, t: number) => fmt(t - it.offset, model.unitOfRoot(it.root)) + (it.offset ? `（画板 ${fmt(t, unit)}）` : '');
  const gap = Math.abs(cut.gap) < 1e-6 ? '紧接' : cut.gap > 0 ? `中间空 ${fmtSpan(cut.gap, unit)}` : `叠了 ${fmtSpan(-cut.gap, unit)}`;
  const name = (it: CutItem) => `#${it.o.id} ${it.o.name || (it.o.media?.source || '').split(/[\\/]/).pop()}`;
  return (
    <div className="cut" onClick={() => host.selectObject(cut.b.o.id)}>
      <figure><Shot model={model} it={cut.a} end project={project} frames={frames} />
        <figcaption>{name(cut.a)} 的{what(cut.a, true)}<br /><small>结束于 {when(cut.a, cut.a.end)}</small></figcaption></figure>
      <div className="cut-mid"><b>→</b><small>{gap}</small>
        {cut.a.root !== cut.b.root && <small className="cross">跨段：{model.nameOf(cut.a.root)} → {model.nameOf(cut.b.root)}</small>}</div>
      <figure><Shot model={model} it={cut.b} end={false} project={project} frames={frames} />
        <figcaption>{name(cut.b)} 的{what(cut.b, false)}<br /><small>开始于 {when(cut.b, cut.b.begin)}</small></figcaption></figure>
    </div>
  );
}

function CutsPage() {
  const {model, boards, project, frames} = host.useView();
  host.React.useEffect(() => { if (model) host.markReady(); }, [model]);
  if (!model || project == null) return null;
  const cuts = cutList(host.util, model, boards, {board: host.numParam('board'), begin: host.numParam('begin'), end: host.numParam('end')});
  const groups = new Map<string, Cut[]>();
  for (const c of cuts) { const key = cutGroupKey(host.util, c); if (!groups.has(key)) groups.set(key, []); groups.get(key)!.push(c); }
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

export default function cuts(given: PluginHost): ViewPlugin {
  host = given;
  h = given.React.createElement;
  Fragment = given.React.Fragment;
  given.addStyle(css);
  return {
    name: 'cuts', label: '接缝', title: '同一条轨道里前后相接的画面：上一段的最后一帧和下一段的第一帧并排',
    handles: ['image', 'video'], page: CutsPage,
    jumpPoints: (model, board) => cutPoints(given.util, model, board),
  };
}

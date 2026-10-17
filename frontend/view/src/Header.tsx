import {tr, useI18n, currentLocale, setLocale} from './i18n';
// 顶栏：项目、视图（画布 / 插件的页面 / 一览）、找对象、时钟、复制链接、插件、关系线开关、画布缩放、在线指示
import {useRef, useState} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {copyLink, selectObject, setView} from './actions';
import {fitBoards, zoomBy} from './camera';
import {keyOf} from './model/model';
import {fmt} from './model/units';
import {activeBoard, getState, modelOf, setState, useModel, useStore} from './store';
import {CAPTURE} from './params';
import {pluginApplies} from './plugin/registry';
import {PluginManager} from './PluginManager';
import {loadProject, report} from './sync';
import type {View} from './types';

// 画布和按本机清单顺序载入的插件页面；没有对应内容时可隐藏插件标签。
const CANVAS = {view: 'canvas' as View, label: 'canvas.title', title: undefined as string | undefined};

export function Header() {
  useI18n();
  const switching = useRef(0);
  const model = useModel();
  const plugins = useStore((s) => s.plugins);
  const {projects, project, view, playhead, links, live, unit} = useStore(useShallow((s) => {
    const act = activeBoard(s);
    return {projects: s.projects, project: s.project, view: s.view, playhead: s.playhead, links: s.links, live: s.live,
            unit: act ? modelOf(s)?.unitOfRoot(keyOf(act)) ?? '' : ''};
  }));
  const [find, setFind] = useState({q: '', hits: [] as number[], at: -1});
  const [query, setQuery] = useState('');
  const [pluginsOpen, setPluginsOpen] = useState(false);
  // 有问题的插件（文件不在、没载入上……）：按钮上标一个 !
  const trouble = useStore((s) => (s.pluginList?.plugins ?? []).filter((r) => r.on && (r.problem || s.pluginErrors[r.name])).length + (s.pluginList?.problem ? 1 : 0));

  const search = (back: boolean) => {
    const q = query.trim().toLowerCase();
    if (!q || !model) return;
    let state = find;
    if (q !== find.q) {
      const hits = model.allObjects().filter((o) => o.layer.role !== 'note' && [o.name, o.text, o.media?.source, `#${o.id}`]
        .some((v) => v && String(v).toLowerCase().includes(q))).map((o) => o.id);
      state = {q, hits, at: -1};
    }
    if (!state.hits.length) return setFind({...state, at: -1});
    const at = (state.at + (back ? -1 : 1) + state.hits.length) % state.hits.length;
    setFind({...state, at});
    selectObject(state.hits[at]);
  };

  const switchProject = async (id: number) => {
    const request = ++switching.current;
    setState({selected: null, playhead: null, active: null, sel: null, targetLayer: null, autoFit: true});
    await loadProject(id);
    requestAnimationFrame(() => { if (request === switching.current && getState().project === id) fitBoards(); });
  };

  return (
    <header className="bar">
      <strong className="brand">LayerWeave</strong>
      <select className="language" aria-label="Language / 语言" value={currentLocale()} onChange={(e) => { setLocale(e.target.value as 'zh' | 'en'); report(); }}>
        <option value="zh">中文</option><option value="en">English</option>
      </select>
      <select value={project ?? ''} title={tr("common.project")} onChange={(e) => switchProject(Number(e.target.value))}>
        {projects.map((p) => <option key={p.id} value={p.id}>{p.id} · {p.name || tr("common.unnamed")}</option>)}
      </select>
      <nav className="tabs">
        {[{...CANVAS, label: tr(CANVAS.label)}, ...plugins.filter((p) => p.page && pluginApplies(p, model)).map((p) => ({view: p.name, label: p.label, title: p.title}))].map((v) => <button key={v.view} className={view === v.view ? 'on' : ''} title={v.title} onClick={() => setView(v.view)}>{v.label}</button>)}
      </nav>
      <input className="find" type="search" placeholder={tr("header.searchPlaceholder")} title={tr("header.searchHint")}
             value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') search(e.shiftKey); }} />
      <span className="find-count">{find.q && query.trim().toLowerCase() === find.q ? (find.hits.length ? `${find.at + 1}/${find.hits.length}` : tr("header.notFound")) : ''}</span>
      <div className="spacer" />
      <span className="clock" title={tr("header.playheadHint")}>{playhead != null ? fmt(playhead, unit) : '—'}</span>
      <button title={tr("header.copyLinkHint")} onClick={copyLink}>{tr("header.copyLink")}</button>
      {!CAPTURE && <button className={`plugin-toggle${pluginsOpen ? ' on' : ''}`} title={trouble ? tr("header.pluginProblems", {value1: trouble}) : tr("header.pluginsHint")}
                           onClick={() => setPluginsOpen(!pluginsOpen)}>{tr("plugins.title")}{trouble ? <b className="trouble">!</b> : null}</button>}
      {pluginsOpen && <PluginManager onClose={() => setPluginsOpen(false)} />}
      {view === 'canvas' && <>
        <label className="toggle" title={tr("header.relationsHint")}>
          <input type="checkbox" checked={links} onChange={(e) => setState({links: e.target.checked})} />  {tr("header.relations")}
        </label>
        <div className="zoom">
          <button title={tr("header.zoomOut")} onClick={() => { setState({autoFit: false}); zoomBy(0.8); }}>−</button>
          <button title={tr("header.fitHint")} onClick={() => { setState({autoFit: true}); fitBoards(); }}>{tr("common.all")}</button>
          <button title={tr("header.zoomIn")} onClick={() => { setState({autoFit: false}); zoomBy(1.25); }}>＋</button>
        </div>
      </>}
      <span className={`live${live ? ' ok' : ''}`} title={tr("header.liveHint")}>●</span>
    </header>
  );
}


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
import {loadProject} from './sync';
import type {View} from './types';

// 画布和按本机清单顺序载入的插件页面；没有对应内容时可隐藏插件标签。
const CANVAS = {view: 'canvas' as View, label: '画布', title: undefined as string | undefined};

export function Header() {
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
      <select value={project ?? ''} title="项目" onChange={(e) => switchProject(Number(e.target.value))}>
        {projects.map((p) => <option key={p.id} value={p.id}>{p.id} · {p.name || '未命名'}</option>)}
      </select>
      <nav className="tabs">
        {[CANVAS, ...plugins.filter((p) => p.page && pluginApplies(p, model)).map((p) => ({view: p.name, label: p.label, title: p.title}))].map((v) => <button key={v.view} className={view === v.view ? 'on' : ''} title={v.title} onClick={() => setView(v.view)}>{v.label}</button>)}
      </nav>
      <input className="find" type="search" placeholder="找对象：名字、文字、文件名、#编号" title="回车找下一个，Shift+回车找上一个"
             value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') search(e.shiftKey); }} />
      <span className="find-count">{find.q && query.trim().toLowerCase() === find.q ? (find.hits.length ? `${find.at + 1}/${find.hits.length}` : '没找到') : ''}</span>
      <div className="spacer" />
      <span className="clock" title="播放头位置（当前画板的单位）">{playhead != null ? fmt(playhead, unit) : '—'}</span>
      <button title="复制现在看的位置（画板、范围、播放头、选中的对象、对准的批注）。贴给 AI，它能拍到同样的画面" onClick={copyLink}>复制链接</button>
      {!CAPTURE && <button className={`plugin-toggle${pluginsOpen ? ' on' : ''}`} title={trouble ? `插件：有 ${trouble} 个有问题，点开看` : '插件：查询、选装、更新、开关和开发链接'}
                           onClick={() => setPluginsOpen(!pluginsOpen)}>插件{trouble ? <b className="trouble">!</b> : null}</button>}
      {pluginsOpen && <PluginManager onClose={() => setPluginsOpen(false)} />}
      {view === 'canvas' && <>
        <label className="toggle" title="画出全部关系线；不勾时只画选中对象的">
          <input type="checkbox" checked={links} onChange={(e) => setState({links: e.target.checked})} /> 关系线
        </label>
        <div className="zoom">
          <button title="缩小画布" onClick={() => { setState({autoFit: false}); zoomBy(0.8); }}>−</button>
          <button title="显示全部画板" onClick={() => { setState({autoFit: true}); fitBoards(); }}>全部</button>
          <button title="放大画布" onClick={() => { setState({autoFit: false}); zoomBy(1.25); }}>＋</button>
        </div>
      </>}
      <span className={`live${live ? ' ok' : ''}`} title="数据库或排版变化后自动刷新">●</span>
    </header>
  );
}


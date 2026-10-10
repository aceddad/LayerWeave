// 顶栏：项目、视图（画布 / 接缝 / 素材）、找对象、时钟、关系线开关、画布缩放、在线指示
import {useState} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {selectObject, setView} from './actions';
import {fitBoards, zoomBy} from './camera';
import {keyOf} from './model/model';
import {fmt} from './model/units';
import {activeBoard, modelOf, setState, useModel, useStore} from './store';
import {loadProject} from './sync';
import type {View} from './types';

const VIEWS: {view: View; label: string; title?: string}[] = [
  {view: 'canvas', label: '画布'},
  {view: 'cuts', label: '接缝', title: '同一条轨道里前后相接的画面：上一段的最后一帧和下一段的第一帧并排'},
  {view: 'assets', label: '素材'},
];

export function Header() {
  const model = useModel();
  const {projects, project, view, playhead, links, live, unit} = useStore(useShallow((s) => {
    const act = activeBoard(s);
    return {projects: s.projects, project: s.project, view: s.view, playhead: s.playhead, links: s.links, live: s.live,
            unit: act ? modelOf(s)?.unitOfRoot(keyOf(act)) ?? '' : ''};
  }));
  const [find, setFind] = useState({q: '', hits: [] as number[], at: -1});
  const [query, setQuery] = useState('');

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
    setState({selected: null, playhead: null, active: null, sel: null, targetLayer: null, autoFit: true});
    await loadProject(id);
    requestAnimationFrame(() => fitBoards());
  };

  return (
    <header className="bar">
      <strong className="brand">LayerWeave</strong>
      <select value={project ?? ''} title="项目" onChange={(e) => switchProject(Number(e.target.value))}>
        {projects.map((p) => <option key={p.id} value={p.id}>{p.id} · {p.name || '未命名'}</option>)}
      </select>
      <nav className="tabs">
        {VIEWS.map((v) => <button key={v.view} className={view === v.view ? 'on' : ''} title={v.title} onClick={() => setView(v.view)}>{v.label}</button>)}
      </nav>
      <input className="find" type="search" placeholder="找对象：名字、文字、文件名、#编号" title="回车找下一个，Shift+回车找上一个"
             value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') search(e.shiftKey); }} />
      <span className="find-count">{find.q && query.trim().toLowerCase() === find.q ? (find.hits.length ? `${find.at + 1}/${find.hits.length}` : '没找到') : ''}</span>
      <div className="spacer" />
      <span className="clock" title="播放头位置（当前画板的单位）">{playhead != null ? fmt(playhead, unit) : '—'}</span>
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


// LayerWeave 视图：画布上每个根（连同子树）是一块时间轴画板；上下 = 同时，左右 = 接续。
// 只读，写入只有视图自己的两样：批注（只写批注层）和折叠（只写视图的表 view_fold）；"用户正在看哪儿"和画板排版记在本机，不写业务库。
import {ReactFlowProvider} from '@xyflow/react';
import {createElement, useEffect} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {goToTarget, keyStep, locateNote, setTree} from './actions';
import {Flow} from './canvas/Flow';
import {Header} from './Header';
import {CAPTURE, FULL} from './params';
import {SidePanel} from './side/SidePanel';
import {LayerTree} from './tree/LayerTree';
import {getState, setState, useStore, waitingOf} from './store';
import {loadProjects, poll, report} from './sync';
import {loadPlugins} from './plugin/registry';
import {PluginBoundary} from './plugin/slots';
import {targetProblem} from './plugin/plan';

export function App() {
  const {view, page, message, notice, name, hasData, waiting, tree, pluginTargetError} = useStore(useShallow((s) => ({
    page: s.plugins.find((p) => p.name === s.view)?.page,
    view: s.view, message: s.message, notice: s.notice, name: s.data?.project.name, hasData: !!s.data,
    waiting: waitingOf(s).length, tree: s.tree,
    pluginTargetError: s.pluginList ? targetProblem(s.view, 'page', s.pluginList.plugins, s.plugins, s.pluginErrors)
      ?? targetProblem(s.side, 'side', s.pluginList.plugins, s.plugins, s.pluginErrors) : null,
  })));

  useEffect(() => {
    if (CAPTURE) document.body.classList.add('capture');
    if (FULL) document.body.classList.add('full');
    loadPlugins();
    loadProjects().then(poll).catch((error) => { setState({message: '读取失败：' + error.message}); if (CAPTURE) window.__layerweaveError = error.message; });
    if (CAPTURE) return;
    const timer = setInterval(poll, 2000);
    return () => clearInterval(timer);
  }, []);

  // 标签页标题前面写上有几楼在等你回复，切到别的标签页也看得见
  useEffect(() => {
    const title = hasData ? `${name || '项目'} · LayerWeave 视图` : 'LayerWeave 视图';
    document.title = waiting && !CAPTURE ? `(${waiting}) ${title}` : title;
  }, [name, hasData, waiting]);

  // Esc：取消圈出的一段、点选的层、对准的批注；←/→/↑/↓、[ ]：键盘跳转
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target instanceof Element && e.target.closest('textarea, input, select')) || e.ctrlKey || e.altKey || e.metaKey) return;
      if (e.key === 'Escape') { setState({sel: null, targetLayer: null, noteFocus: null}); report(); return; }
      if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', '[', ']'].includes(e.key) && keyStep(e.key)) e.preventDefault();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className="app">
      <Header />
      <div className="body">
        {view === 'canvas' && <div className="canvas-view">
          {tree ? <LayerTree /> : !CAPTURE && <button className="tree-open" title="打开左边的目录：项目的层，一眼看全" onClick={() => setTree(true)}>目录 ›</button>}
          <ReactFlowProvider><Flow /></ReactFlowProvider><SidePanel />
        </div>}
        {view !== 'canvas' && page && <PluginBoundary key={view} name={view}>{createElement(page)}</PluginBoundary>}
      </div>
      {pluginTargetError && <p className="message plugin-target-error">{pluginTargetError} {!CAPTURE && <button onClick={() => setState({view: 'canvas', side: 'now'})}>返回画布</button>}</p>}
      {message && <p className="message">{message}</p>}
      {notice && <p className="notice" title="点一下过去" onClick={() => {
        setState({notice: null});
        if (notice.thread != null) { setState({side: 'notes'}); locateNote(notice.thread); }
        else if (notice.layer != null) goToTarget({kind: 'layer', project: getState().project!, id: notice.layer}, null);
      }}>
        💬 {notice.text}<button onClick={(e) => { e.stopPropagation(); setState({notice: null}); }}>×</button></p>}
    </div>
  );
}

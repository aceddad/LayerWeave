// LayerWeave 视图：画布上每个根（连同子树）是一块时间轴画板；上下 = 同时，左右 = 接续。
// 只读，唯一的写入是批注（只写批注层）；"用户正在看哪儿"和画板排版记在本机，不写业务库。
import {ReactFlowProvider} from '@xyflow/react';
import {useEffect} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {Flow} from './canvas/Flow';
import {markReady} from './capture';
import {Header} from './Header';
import {CAPTURE, FULL} from './params';
import {SidePanel} from './side/SidePanel';
import {setState, useStore} from './store';
import {loadProjects, poll, report} from './sync';
import {AssetsView} from './views/AssetsView';
import {CutsView} from './views/CutsView';

export function App() {
  const {view, message, name, hasData} = useStore(useShallow((s) => ({
    view: s.view, message: s.message, name: s.data?.project.name, hasData: !!s.data,
  })));

  useEffect(() => {
    if (CAPTURE) document.body.classList.add('capture');
    if (FULL) document.body.classList.add('full');
    loadProjects().then(poll).catch((error) => { setState({message: '读取失败：' + error.message}); markReady(); });
    if (CAPTURE) return;
    const timer = setInterval(poll, 2000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => { document.title = hasData ? `${name || '项目'} · LayerWeave 视图` : 'LayerWeave 视图'; }, [name, hasData]);

  // Esc：取消圈出的一段和点选的层
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || (e.target as HTMLElement).closest('textarea, input')) return;
      setState({sel: null, targetLayer: null});
      report();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className="app">
      <Header />
      <div className="body">
        {view === 'canvas' && <div className="canvas-view"><ReactFlowProvider><Flow /></ReactFlowProvider><SidePanel /></div>}
        {view === 'cuts' && <CutsView />}
        {view === 'assets' && <AssetsView />}
      </div>
      {message && <p className="message">{message}</p>}
    </div>
  );
}

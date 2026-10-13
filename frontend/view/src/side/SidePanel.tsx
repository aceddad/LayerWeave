// 右侧面板：此刻 / 改动 / 批注
import {useShallow} from 'zustand/react/shallow';
import {setSide} from '../actions';
import {useStore, waitingOf} from '../store';
import type {Side} from '../types';
import {ChangesPanel} from './ChangesPanel';
import {NotesPanel} from './NotesPanel';
import {NowPanel} from './NowPanel';

const TABS: {side: Side; label: string; title: string}[] = [
  {side: 'now', label: '此刻', title: '播放头这一刻每层都有什么'},
  {side: 'changes', label: '改动', title: '最近几次操作改了什么；打开时画布上会标出来'},
  {side: 'notes', label: '批注', title: '批注：给人或 AI 留的意见、说明、待办'},
];

export function SidePanel() {
  const {side, waiting, me} = useStore(useShallow((s) => ({side: s.side, me: s.me, waiting: waitingOf(s).length})));
  return (
    <aside className="side">
      <nav className="side-tabs">
        {TABS.map((t) => <button key={t.side} className={side === t.side ? 'on' : ''} title={t.title} onClick={() => setSide(t.side)}>
          {t.label}
          {t.side === 'notes' && waiting > 0 && <i className="badge" title={`有 ${waiting} 楼在等你（署名：${me}）回复`}>{waiting}</i>}
        </button>)}
      </nav>
      {side === 'now' && <NowPanel />}
      {side === 'changes' && <ChangesPanel />}
      {side === 'notes' && <NotesPanel />}
    </aside>
  );
}

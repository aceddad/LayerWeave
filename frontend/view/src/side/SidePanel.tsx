// 右侧面板：此刻 / 改动 / 批注 / 沿读，后面是插件的侧栏（项目里没有它管的对象时不显示）
import {createElement} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {setSide} from '../actions';
import {pluginApplies} from '../plugin/registry';
import {PluginBoundary} from '../plugin/slots';
import {useModel, useStore, waitingOf} from '../store';
import type {Side} from '../types';
import {ChangesPanel} from './ChangesPanel';
import {NotesPanel} from './NotesPanel';
import {NowPanel} from './NowPanel';
import {WalkPanel} from './WalkPanel';

const TABS: {side: Side; label: string; title: string}[] = [
  {side: 'now', label: '此刻', title: '播放头这一刻每层都有什么'},
  {side: 'changes', label: '改动', title: '最近几次操作改了什么；打开时画布上会标出来'},
  {side: 'notes', label: '批注', title: '批注：给人或 AI 留的意见、说明、待办'},
  {side: 'walk', label: '沿读', title: '从一个对象或一楼批注出发，顺着关联一步步往外读（对象详情、楼主卡片上的「沿读」）'},
];

export function SidePanel() {
  const model = useModel();
  const {side, waiting, me, plugins} = useStore(useShallow((s) => ({side: s.side, me: s.me, waiting: waitingOf(s).length, plugins: s.plugins})));
  const mine = plugins.filter((p) => p.side && pluginApplies(p, model));
  const current = mine.find((p) => p.name === side);
  return (
    <aside className="side">
      <nav className="side-tabs">
        {TABS.map((t) => <button key={t.side} className={side === t.side ? 'on' : ''} title={t.title} onClick={() => setSide(t.side)}>
          {t.label}
          {t.side === 'notes' && waiting > 0 && <i className="badge" title={`有 ${waiting} 楼在等你（署名：${me}）回复`}>{waiting}</i>}
        </button>)}
        {mine.map((p) => <button key={p.name} className={`plugin-tab${side === p.name ? ' on' : ''}`} title={p.title ?? `插件「${p.name}」`}
                                 onClick={() => setSide(p.name)}>{p.label}</button>)}
      </nav>
      {current && <PluginBoundary key={current.name} name={current.name}>{createElement(current.side!)}</PluginBoundary>}
      {side === 'now' && <NowPanel />}
      {side === 'changes' && <ChangesPanel />}
      {side === 'notes' && <NotesPanel />}
      {side === 'walk' && <WalkPanel />}
    </aside>
  );
}

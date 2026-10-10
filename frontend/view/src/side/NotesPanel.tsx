// 批注：按楼列出；写新批注（写给：圈出的一段 > 点选的层 > 选中的对象 > 整个项目）；卡片里回复、改、删（不用浏览器弹窗）
import {useState} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {goToTarget} from '../actions';
import {refExists, refLabel} from '../model/labels';
import type {Model} from '../model/model';
import type {Note, Thread} from '../model/notes';
import {fmt} from '../model/units';
import {RECORD} from '../params';
import {getState, modelOf, setState, useModel, useNotes, useStore} from '../store';
import {noteAction, selectionInfo, toast} from '../sync';

type Target = {kind: 'span'; root: number; begin: number; end: number; label: string}
  | {kind: 'layer' | 'object'; id: number; label: string} | {kind: 'project'; label: string};

function composeTarget(): Target {
  const s = getState(), model = modelOf(s)!;
  const sel = !s.wholeProject && selectionInfo();
  if (sel) return {kind: 'span', ...sel, label: `${sel.name} 的 ${fmt(sel.begin, model.unitOfRoot(sel.root))} – ${fmt(sel.end, model.unitOfRoot(sel.root))}`};
  if (!s.wholeProject && s.targetLayer != null && model.layer(s.targetLayer))
    return {kind: 'layer', id: s.targetLayer, label: refLabel(model, {kind: 'layer', project: model.project, id: s.targetLayer})};
  if (!s.wholeProject && s.selected != null && model.object(s.selected))
    return {kind: 'object', id: s.selected, label: refLabel(model, {kind: 'object', project: model.project, id: s.selected})};
  return {kind: 'project', label: '整个项目'};
}

const author = () => localStorage.getItem('lw-author') || '用户';

function Targets({model, note}: {model: Model; note: Note}) {
  if (!note.targets.length) return <span className="note-target whole">整个项目</span>;
  return <>{note.targets.map((t, i) => {
    const unit = t.kind === 'layer' ? model.unitOfRoot(model.layer(t.id)?.root) : '';
    const span = note.span && t.kind === 'layer' ? ` 的 ${fmt(note.span.begin, unit)} – ${fmt(note.span.end, unit)}` : '';
    return <span key={i} className={`note-target${refExists(model, t) ? '' : ' gone'}`} onClick={() => goToTarget(t, t.kind === 'layer' ? note.span : null)}>
      {refLabel(model, t)}{span}
    </span>;
  })}</>;
}

function NoteCard({model, note, floors, top, number}: {model: Model; note: Note; floors: Map<number, number>; top?: Note; number?: number}) {
  const [mode, setMode] = useState<'view' | 'edit' | 'reply' | 'delete'>('view');
  const [draft, setDraft] = useState('');
  const isTop = !top;
  const open = (next: typeof mode) => { setMode(next); setDraft(next === 'edit' ? note.text : ''); };
  const save = async () => {
    const text = draft.trim();
    if (!text) return toast(mode === 'edit' ? '正文不能为空' : '先写点什么');
    const ok = mode === 'edit'
      ? await noteAction({action: 'edit', note: note.id, text})
      : await noteAction({action: 'add', text, author: author(), targets: [{kind: 'object', id: note.id}]});
    if (ok) setMode('view');
  };
  const keys = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') setMode('view');
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) save();
  };
  return (
    <div className={`note ${isTop ? note.status : 'reply'}`} data-note={note.id}>
      <div className="note-head">
        {isTop
          ? <label title="勾上表示整楼已处理"><input type="checkbox" checked={note.status === 'done'} disabled={!RECORD}
              onChange={(e) => noteAction({action: e.target.checked ? 'done' : 'reopen', note: note.id})} /> 第 {number} 楼</label>
          : <><span className="floor">{floors.get(note.id)} 楼</span>{note.replyTo !== top.id && floors.has(note.replyTo!) && <span className="reply-to">回复 {floors.get(note.replyTo!)} 楼</span>}</>}
        {note.author && <b>{note.author}</b>}<small>#{note.id}</small><span className="grow" />
        {RECORD && (mode === 'delete'
          ? <><span className="confirm">删除这条{isTop && floors.size > 1 ? '（回复会留下）' : ''}？</span>
              <button onClick={async () => { if (await noteAction({action: 'remove', note: note.id})) setMode('view'); }}>删除</button>
              <button onClick={() => setMode('view')}>取消</button></>
          : <><button onClick={() => open('reply')}>回复</button><button onClick={() => open('edit')}>改</button><button onClick={() => open('delete')}>删</button></>)}
      </div>
      {mode === 'edit'
        ? <><textarea className="note-box" rows={3} autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={keys} />
            <div className="note-row"><span className="grow" /><button onClick={() => setMode('view')}>取消</button><button onClick={save}>保存</button></div></>
        : <div className="note-text">{note.text}</div>}
      {isTop && <div className="note-where">→ <Targets model={model} note={note} /></div>}
      {mode === 'reply' && <div className="note-replybox">
        <textarea className="note-box" rows={2} autoFocus value={draft} placeholder={`回复 ${isTop ? '楼主' : floors.get(note.id) + ' 楼'}……（Ctrl+回车发送）`}
                  onChange={(e) => setDraft(e.target.value)} onKeyDown={keys} />
        <div className="note-row"><span className="grow" /><button onClick={() => setMode('view')}>取消</button><button onClick={save}>发送</button></div>
      </div>}
    </div>
  );
}

function ThreadView({model, thread, number}: {model: Model; thread: Thread; number: number}) {
  const floors = new Map([[thread.top.id, 1], ...thread.replies.map((r, i) => [r.id, i + 2] as [number, number])]);
  return (
    <div className={`thread ${thread.top.status}`}>
      <NoteCard model={model} note={thread.top} floors={floors} number={number} />
      {thread.replies.map((r) => <NoteCard key={r.id} model={model} note={r} floors={floors} top={thread.top} />)}
    </div>
  );
}

export function NotesPanel() {
  const model = useModel(), notes = useNotes();
  // sel、targetLayer、selected、wholeProject 变了，"写给"跟着变，所以一起订阅
  const {filter, showHidden} = useStore(useShallow((s) => ({filter: s.noteFilter, showHidden: s.showHidden,
    sel: s.sel, targetLayer: s.targetLayer, selected: s.selected, wholeProject: s.wholeProject})));
  const [text, setText] = useState('');
  const [name, setName] = useState(author());
  if (!model || !notes) return null;
  const target = composeTarget();
  const threads = notes.threads, shown = threads.filter(({top}) => filter === 'all' || top.status === filter);
  const add = async () => {
    const body: Record<string, unknown> = {action: 'add', text: text.trim(), author: name.trim()};
    if (!body.text) return toast('先写点什么');
    if (target.kind === 'object' || target.kind === 'layer') body.targets = [{kind: target.kind, id: target.id}];
    if (target.kind === 'span') { body.targets = [{kind: 'layer', id: target.root}]; body.span = {begin: target.begin, end: target.end}; }
    localStorage.setItem('lw-author', name.trim());
    if (await noteAction(body)) { setText(''); setState({wholeProject: false}); }
  };
  return (
    <section>
      <h2>批注 <small>{threads.length} 楼，待处理 {threads.filter(({top}) => top.status === 'open').length}</small></h2>
      {RECORD && <div className="compose">
        <textarea rows={3} value={text} placeholder="写一条批注……（Ctrl+回车加上）" onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) add(); }} />
        <div className="note-row">写给：<b>{target.label}</b>
          {target.kind !== 'project' && <a href="#" onClick={(e) => { e.preventDefault(); setState({wholeProject: true}); }}>改成整个项目</a>}</div>
        <div className="note-row"><label>署名 <input size={8} value={name} onChange={(e) => setName(e.target.value)} /></label><span className="grow" /><button onClick={add}>加上</button></div>
        <p className="hint">先选中一个对象、点一个层名，或者在尺子上拖出一段，批注就指向那里；什么都不选就是写给整个项目。每条都可以回复，回复按楼显示。</p>
      </div>}
      <div className="note-row filters">
        {(['all', 'open', 'done'] as const).map((f) => <button key={f} className={filter === f ? 'on' : ''} onClick={() => setState({noteFilter: f})}>{{all: '全部', open: '待处理', done: '已处理'}[f]}</button>)}
        <span className="grow" />
        <label className="toggle" title="批注层默认收起；勾上后在画布上也显示成一块画板"><input type="checkbox" checked={showHidden} onChange={(e) => setState({showHidden: e.target.checked})} /> 画布上显示批注层</label>
      </div>
      {shown.length ? shown.map((th) => <ThreadView key={th.top.id} model={model} thread={th} number={threads.indexOf(th) + 1} />)
        : <p className="hint">还没有批注。选中一个对象、点一个层名，或者在尺子上拖出一段，再写。</p>}
    </section>
  );
}

// 批注：按楼列出；写新批注（写给：圈出的一段 > 点选的层 > 选中的对象 > 整个项目）；卡片里回复、改、删（不用浏览器弹窗）。
// 默认只列待处理的楼；已处理的只在"已处理"里出现（字多了以后不用翻过它们）。
// "等我回复"：没处理、最后一句不是本机署名说的、我也没标已读的楼（和 view_note --waiting 同一条规则），标签上的数字也是它。
// 已读 ≠ 已处理：已读只是"我看过了，别再提醒我"，按署名各记各的；之后有人再写一条，就又算没读
import {useEffect, useRef, useState} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {goToTarget, locateNote} from '../actions';
import {refExists, refLabel} from '../model/labels';
import type {Model} from '../model/model';
import {lastOf, readBy, waitingFor} from '../model/notes';
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

// 楼主卡片上的已读：在等我的楼给"已读"；我标过已读的（而且之后没人再写）给"标为未读"。我自己最后说的、已处理的楼不用标
function ReadButton({thread, me, read}: {thread: Thread; me: string; read: boolean}) {
  if (!RECORD || thread.top.status !== 'open' || lastOf(thread).author === me.trim()) return null;
  const mark = (action: 'read' | 'unread') => noteAction({action, note: thread.top.id, reader: me.trim()});
  return read
    ? <><span className="read-tag" title={`「${me}」看过了：这楼不再算等你回复`}>已读</span><button onClick={() => mark('unread')}>标为未读</button></>
    : <button title="我看过了，这楼不再算等我回复（不是已处理；之后有人再写一条，会重新提醒）" onClick={() => mark('read')}>已读</button>;
}

function NoteCard({model, note, floors, top, number, waiting, thread, me, read}: {model: Model; note: Note; floors: Map<number, number>; top?: Note;
  number?: number; waiting?: boolean; thread?: Thread; me?: string; read?: boolean}) {
  const [mode, setMode] = useState<'view' | 'edit' | 'reply' | 'delete'>('view');
  const [draft, setDraft] = useState('');
  const isTop = !top;
  const open = (next: typeof mode) => { setMode(next); setDraft(next === 'edit' ? note.text : ''); };
  const save = async () => {
    const text = draft.trim();
    if (!text) return toast(mode === 'edit' ? '正文不能为空' : '先写点什么');
    const ok = mode === 'edit'
      ? await noteAction({action: 'edit', note: note.id, text})
      : await noteAction({action: 'add', text, author: getState().me, targets: [{kind: 'object', id: note.id}]});
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
        {note.author && <b>{note.author}</b>}<small>#{note.id}</small>{waiting && <span className="wait-tag">等你回复</span>}<span className="grow" />
        {isTop && thread && me != null && <ReadButton thread={thread} me={me} read={!!read} />}
        {isTop && <button title="镜头对准这一楼指的地方，并标出来" onClick={() => locateNote(note.id)}>定位</button>}
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

function ThreadView({model, thread, number, waiting, focused, me, read}: {model: Model; thread: Thread; number: number; waiting: boolean; focused: boolean;
  me: string; read: boolean}) {
  const floors = new Map([[thread.top.id, 1], ...thread.replies.map((r, i) => [r.id, i + 2] as [number, number])]);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (focused) ref.current?.scrollIntoView({block: 'nearest'}); }, [focused]);
  return (
    <div ref={ref} className={`thread ${thread.top.status}${focused ? ' focus' : ''}`}>
      <NoteCard model={model} note={thread.top} floors={floors} number={number} waiting={waiting} thread={thread} me={me} read={read} />
      {thread.replies.map((r) => <NoteCard key={r.id} model={model} note={r} floors={floors} top={thread.top} />)}
    </div>
  );
}

// 写新批注的框："写给"跟着圈出的一段、点选的层、选中的对象变，所以只有它订阅这些；点画板上的对象，下面几十楼不用跟着重画
function Compose({me}: {me: string}) {
  useStore(useShallow((s) => ({sel: s.sel, targetLayer: s.targetLayer, selected: s.selected, wholeProject: s.wholeProject})));
  const [text, setText] = useState('');
  const target = composeTarget();
  const rename = (name: string) => { setState({me: name}); localStorage.setItem('lw-author', name.trim()); };
  const add = async () => {
    const body: Record<string, unknown> = {action: 'add', text: text.trim(), author: me.trim()};
    if (!body.text) return toast('先写点什么');
    if (target.kind === 'object' || target.kind === 'layer') body.targets = [{kind: target.kind, id: target.id}];
    if (target.kind === 'span') { body.targets = [{kind: 'layer', id: target.root}]; body.span = {begin: target.begin, end: target.end}; }
    if (await noteAction(body)) { setText(''); setState({wholeProject: false}); }
  };
  return (
    <div className="compose">
      <textarea rows={3} value={text} placeholder="写一条批注……（Ctrl+回车加上）" onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) add(); }} />
      <div className="note-row">写给：<b>{target.label}</b>
        {target.kind !== 'project' && <a href="#" onClick={(e) => { e.preventDefault(); setState({wholeProject: true}); }}>改成整个项目</a>}</div>
      <div className="note-row"><label title="你的名字：写批注时署上，也用它算哪些楼在等你回复">署名 <input size={8} value={me} onChange={(e) => rename(e.target.value)} /></label><span className="grow" /><button onClick={add}>加上</button></div>
      <p className="hint">先选中一个对象、点一个层名，或者在尺子上拖出一段，批注就指向那里；什么都不选就是写给整个项目。每条都可以回复，回复按楼显示。</p>
    </div>
  );
}

export function NotesPanel() {
  const model = useModel(), notes = useNotes();
  // 选择器里只取原始值（reads 是状态里的同一个对象）；"等我回复"在这里算，免得每次都返回新数组让页面反复重画
  const {filter, showHidden, me, focus, reads} = useStore(useShallow((s) => ({filter: s.noteFilter, showHidden: s.showHidden, me: s.me,
    focus: s.noteFocus, reads: s.reads})));
  // 对准了一楼（地址参数 note、提示、定位）：列表切到看得见它的那一类。已处理的楼只在"已处理"里；"等我回复"里没有它就回"待处理"
  useEffect(() => {
    const th = notes?.threads.find((t) => t.top.id === focus);
    if (!th) return;
    const want = th.top.status === 'done' ? 'done' : filter === 'done' || (filter === 'waiting' && !waitingFor([th], me, reads).length) ? 'open' : filter;
    if (want !== filter) setState({noteFilter: want});
  }, [focus, notes]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (!model || !notes) return null;
  const threads = notes.threads, waiting = new Set(waitingFor(threads, me, reads));
  const count = {open: threads.filter((th) => th.top.status === 'open').length, done: threads.filter((th) => th.top.status === 'done').length};
  const shown = threads.filter((th) => (filter === 'waiting' ? waiting.has(th) : th.top.status === filter));
  return (
    <section>
      <h2>批注 <small>待处理 {count.open} 楼，已处理 {count.done} 楼</small></h2>
      {RECORD && <Compose me={me} />}
      <div className="note-row filters">
        {(['open', 'waiting', 'done'] as const).map((f) => <button key={f} className={filter === f ? 'on' : ''} onClick={() => setState({noteFilter: f})}
            title={{open: '还没处理的楼', waiting: `没处理、最后一句不是「${me}」说的、你也没标已读的楼`, done: '已处理的楼只在这里出现'}[f]}>
          {{open: `待处理 ${count.open}`, waiting: `等我回复 ${waiting.size}`, done: `已处理 ${count.done}`}[f]}</button>)}
        <span className="grow" />
        <label className="toggle" title="批注层默认收起；勾上后在画布上也显示成一块画板"><input type="checkbox" checked={showHidden} onChange={(e) => setState({showHidden: e.target.checked})} /> 画布上显示批注层</label>
      </div>
      {shown.length ? shown.map((th) => <ThreadView key={th.top.id} model={model} thread={th} number={threads.indexOf(th) + 1}
                                                    waiting={waiting.has(th)} focused={focus === th.top.id} me={me} read={readBy(th, me, reads)} />)
        : <p className="hint">{threads.length ? {open: '没有待处理的楼。', waiting: '没有在等你的楼。', done: '还没有已处理的楼。'}[filter]
                                              : '还没有批注。选中一个对象、点一个层名，或者在尺子上拖出一段，再写。'}</p>}
    </section>
  );
}

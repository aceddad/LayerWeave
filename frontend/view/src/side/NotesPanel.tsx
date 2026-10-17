import {writePreference} from '../preferences';
import {ui, tr, useI18n} from '../i18n';
// 批注：按楼列出；写新批注（写给：圈出的一段 > 点选的层 > 选中的对象 > 整个项目）；卡片里回复、改、删（不用浏览器弹窗）。
// 默认只列待处理的楼；已处理的只在"已处理"里出现（字多了以后不用翻过它们）。
// "等我回复"：没处理、最后一句不是本机署名说的、我也没标已读的楼（和 view_note --waiting 同一条规则），标签上的数字也是它。
// 已读 ≠ 已处理：已读只是"我看过了，别再提醒我"，按署名各记各的；之后有人再写一条，就又算没读
import {useEffect, useRef, useState} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {goToTarget, locateNote, startWalk} from '../actions';
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
  if (sel) return {kind: 'span', ...sel, label: tr("notes.selectionSpan", {value1: sel.name, value2: fmt(sel.begin, model.unitOfRoot(sel.root)), value3: fmt(sel.end, model.unitOfRoot(sel.root))})};
  if (!s.wholeProject && s.targetLayer != null && model.layer(s.targetLayer))
    return {kind: 'layer', id: s.targetLayer, label: refLabel(model, {kind: 'layer', project: model.project, id: s.targetLayer}, tr)};
  if (!s.wholeProject && s.selected != null && model.object(s.selected))
    return {kind: 'object', id: s.selected, label: refLabel(model, {kind: 'object', project: model.project, id: s.selected}, tr)};
  return {kind: 'project', label: tr("notes.wholeProject")};
}

// "写给"的东西 → 请求里的 targets、span（写新批注、改指向共用）
function targetBody(target: Target): Record<string, unknown> {
  if (target.kind === 'object' || target.kind === 'layer') return {targets: [{kind: target.kind, id: target.id}]};
  if (target.kind === 'span') return {targets: [{kind: 'layer', id: target.root}], span: {begin: target.begin, end: target.end}};
  return {targets: []};
}

// 改指向：和写新批注一样，指向页面上现在选中的东西（圈出的一段 > 点选的层 > 选中的对象 > 整个项目）。
// 选择一变"改成指向"跟着变，所以单独订阅选择；回复不能改（服务端会拒绝），按钮只在楼主上
function Retarget({note, onDone}: {note: Note; onDone: () => void}) {
  useI18n();
  useStore(useShallow((s) => ({sel: s.sel, targetLayer: s.targetLayer, selected: s.selected, wholeProject: s.wholeProject})));
  const target = composeTarget();
  const apply = async () => { if (await noteAction({action: 'retarget', note: note.id, ...targetBody(target)})) onDone(); };
  return (
    <div className="note-row retarget">

      {tr("notes.retargetTo")}<b>{target.label}</b>
      {target.kind !== 'project' && <a href="#" onClick={(e) => { e.preventDefault(); setState({wholeProject: true}); }}>{tr("notes.targetProject")}</a>}
      <span className="grow" /><button onClick={onDone}>{tr("common.cancel")}</button><button onClick={apply}>{tr("common.edit")}</button>
      <p className="hint">{tr("notes.retargetHint")}</p>
    </div>
  );
}

function Targets({model, note}: {model: Model; note: Note}) {
  useI18n();
  if (!note.targets.length) return <span className="note-target whole">{tr("notes.wholeProject")}</span>;
  return <>{note.targets.map((t, i) => {
    const unit = t.kind === 'layer' ? model.unitOfRoot(model.layer(t.id)?.root) : '';
    const span = note.span && t.kind === 'layer' ? tr("notes.targetSpan", {value1: fmt(note.span.begin, unit), value2: fmt(note.span.end, unit)}) : '';
    return <span key={i} className={`note-target${refExists(model, t) ? '' : ' gone'}`} onClick={() => goToTarget(t, t.kind === 'layer' ? note.span : null)}>
      {refLabel(model, t, tr)}{span}
    </span>;
  })}</>;
}

// 楼主卡片上的已读：在等我的楼给"已读"；我标过已读的（而且之后没人再写）给"标为未读"。我自己最后说的、已处理的楼不用标
function ReadButton({thread, me, read}: {thread: Thread; me: string; read: boolean}) {
  useI18n();
  if (!RECORD || thread.top.status !== 'open' || lastOf(thread).author === me.trim()) return null;
  const mark = (action: 'read' | 'unread') => noteAction({action, note: thread.top.id, reader: me.trim()});
  return read
    ? <><span className="read-tag" title={tr("notes.readBy", {value1: me})}>{tr("notes.read")}</span><button onClick={() => mark('unread')}>{tr("notes.markUnread")}</button></>
    : <button title={tr("notes.markReadHint")} onClick={() => mark('read')}>{tr("notes.read")}</button>;
}

function NoteCard({model, note, floors, top, number, waiting, thread, me, read}: {model: Model; note: Note; floors: Map<number, number>; top?: Note;
  number?: number; waiting?: boolean; thread?: Thread; me?: string; read?: boolean}) {
  useI18n();
  const [mode, setMode] = useState<'view' | 'edit' | 'reply' | 'delete' | 'retarget'>('view');
  const [draft, setDraft] = useState('');
  const isTop = !top;
  const open = (next: typeof mode) => { setMode(next); setDraft(next === 'edit' ? note.text : ''); };
  const save = async () => {
    const text = draft.trim();
    if (!text) return toast(mode === 'edit' ? tr("notes.bodyRequired") : tr("notes.writeFirst"));
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
          ? <label title={tr("notes.resolveHint")}><input type="checkbox" checked={note.status === 'done'} disabled={!RECORD}
              onChange={(e) => noteAction({action: e.target.checked ? 'done' : 'reopen', note: note.id})} />  {tr("notes.threadNumber", {number: number!})}</label>
          : <><span className="floor">{tr("notes.replyNumber", {number: floors.get(note.id)!})}</span>{note.replyTo !== top.id && floors.has(note.replyTo!) && <span className="reply-to">{tr("notes.reply")} #{floors.get(note.replyTo!)}</span>}</>}
        {note.author && <b>{note.author}</b>}<small>#{note.id}</small>{waiting && <span className="wait-tag">{tr("notes.awaitingYou")}</span>}<span className="grow" />
        {isTop && thread && me != null && <ReadButton thread={thread} me={me} read={!!read} />}
        {isTop && <button title={tr("notes.locateHint")} onClick={() => locateNote(note.id)}>{tr("notes.locate")}</button>}
        {isTop && <button title={tr("notes.followHint")} onClick={() => startWalk(`object:${note.id}`)}>{tr("relations.follow")}</button>}
        {RECORD && (mode === 'delete'
          ? <><span className="confirm">{tr("notes.deleteThis")}{isTop && floors.size > 1 ? tr("notes.repliesRemain") : ''}？</span>
              <button onClick={async () => { if (await noteAction({action: 'remove', note: note.id})) setMode('view'); }}>{tr("common.delete")}</button>
              <button onClick={() => setMode('view')}>{tr("common.cancel")}</button></>
          : <><button onClick={() => open('reply')}>{tr("notes.reply")}</button><button onClick={() => open('edit')}>{tr("common.edit")}</button>
              {isTop && <button title={tr("notes.retargetButtonHint")} onClick={() => open('retarget')}>{tr("notes.retarget")}</button>}
              <button onClick={() => open('delete')}>{tr("common.delete.variant")}</button></>)}
      </div>
      {mode === 'edit'
        ? <><textarea className="note-box" rows={3} autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={keys} />
            <div className="note-row"><span className="grow" /><button onClick={() => setMode('view')}>{tr("common.cancel")}</button><button onClick={save}>{tr("common.save")}</button></div></>
        : <div className="note-text">{note.text}</div>}
      {isTop && <div className="note-where">→ <Targets model={model} note={note} /></div>}
      {mode === 'retarget' && <Retarget note={note} onDone={() => setMode('view')} />}
      {mode === 'reply' && <div className="note-replybox">
        <textarea className="note-box" rows={2} autoFocus value={draft} placeholder={tr("notes.replyPlaceholder", {value1: isTop ? tr("notes.threadAuthor") : floors.get(note.id) + tr("notes.replyNumberSuffix")})}
                  onChange={(e) => setDraft(e.target.value)} onKeyDown={keys} />
        <div className="note-row"><span className="grow" /><button onClick={() => setMode('view')}>{tr("common.cancel")}</button><button onClick={save}>{tr("notes.send")}</button></div>
      </div>}
    </div>
  );
}

function ThreadView({model, thread, number, waiting, focused, me, read}: {model: Model; thread: Thread; number: number; waiting: boolean; focused: boolean;
  me: string; read: boolean}) {
  useI18n();
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
  useI18n();
  useStore(useShallow((s) => ({sel: s.sel, targetLayer: s.targetLayer, selected: s.selected, wholeProject: s.wholeProject})));
  const [text, setText] = useState('');
  const target = composeTarget();
  const rename = (name: string) => { setState({me: name}); writePreference('lw-author', name.trim()); };
  const add = async () => {
    const body: Record<string, unknown> = {action: 'add', text: text.trim(), author: me.trim()};
    if (!body.text) return toast(ui("notes.writeFirst"));
    Object.assign(body, targetBody(target));
    if (await noteAction(body)) { setText(''); setState({wholeProject: false}); }
  };
  return (
    <div className="compose">
      <textarea rows={3} value={text} placeholder={tr("notes.composePlaceholder")} onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) add(); }} />
      <div className="note-row">{tr("notes.targetLabel")}<b>{target.label}</b>
        {target.kind !== 'project' && <a href="#" onClick={(e) => { e.preventDefault(); setState({wholeProject: true}); }}>{tr("notes.targetProject")}</a>}</div>
      <div className="note-row"><label title={tr("notes.authorHint")}>{tr("notes.author")} <input size={8} value={me} onChange={(e) => rename(e.target.value)} /></label><span className="grow" /><button onClick={add}>{tr("notes.add")}</button></div>
      <p className="hint">{tr("notes.composeHint")}</p>
    </div>
  );
}

export function NotesPanel() {
  useI18n();
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
      <h2>{tr("notes.title")} <small>{tr("notes.counts", count)}</small></h2>
      {RECORD && <Compose me={me} />}
      <div className="note-row filters">
        {(['open', 'waiting', 'done'] as const).map((f) => <button key={f} className={filter === f ? 'on' : ''} onClick={() => setState({noteFilter: f})}
            title={{open: tr("notes.openHint"), waiting: tr("notes.waitingHint", {value1: me}), done: tr("notes.resolvedHint")}[f]}>
          {{open: tr("notes.openCount", {value1: count.open}), waiting: tr("notes.waitingCount", {value1: waiting.size}), done: tr("notes.resolvedCount", {value1: count.done})}[f]}</button>)}
        <span className="grow" />
        <label className="toggle" title={tr("notes.showLayerHint")}><input type="checkbox" checked={showHidden} onChange={(e) => setState({showHidden: e.target.checked})} />  {tr("notes.showLayer")}</label>
      </div>
      {shown.length ? shown.map((th) => <ThreadView key={th.top.id} model={model} thread={th} number={threads.indexOf(th) + 1}
                                                    waiting={waiting.has(th)} focused={focus === th.top.id} me={me} read={readBy(th, me, reads)} />)
        : <p className="hint">{threads.length ? {open: tr("notes.noOpen"), waiting: tr("notes.noWaiting"), done: tr("notes.noResolved")}[filter]
                                              : tr("notes.empty")}</p>}
    </section>
  );
}

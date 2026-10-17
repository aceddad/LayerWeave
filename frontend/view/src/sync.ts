import type {UiMessage} from './i18n/types';
import {ui, tr, useI18n, currentLocale} from './i18n';
// 和服务同步：读项目和排版、每 2 秒看有没有变化、保存排版、报告"正在看哪儿"、写批注
import {api} from './api';
import {visibleBoards, visibleRange} from './camera';
import {afterResize, placeAuto, separate, sizeOf} from './model/layoutOps';
import {adoptOrphans, keyOf, rootsOf} from './model/model';
import type {Note} from './model/notes';
import {withFolds, withNoteStatus, withRead} from './model/optimistic';
import {applyChanges} from './model/incremental';
import {SyncGate} from './model/syncGate';
import type {SyncToken} from './model/syncGate';
import type {Model} from './model/model';
import {CAPTURE, RECORD, VIEWER, numParam} from './params';
import {refreshPlugins} from './plugin/registry';
import {activeBoard, getState, modelOf, notesOf, setState} from './store';
import type {Board, FoldRow, Layout} from './types';

let toastTimer: ReturnType<typeof setTimeout> | undefined;
export function toast(text: string | UiMessage, ms = 2500) {
  setState({message: text});
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => setState({message: ''}), ms);
}

export async function loadProjects() {
  const [capabilities, projects] = await Promise.all([api.capabilities(), api.projects()]);
  setState({frames: capabilities.frames, projects});
  const want = numParam('project') ?? projects[0]?.id;
  if (!want) return setState({message: ui("app.noProjects")});
  await loadProject(want);
}

export async function loadProject(id: number) {
  const same = getState().project === id;
  gate.select(id);
  setState({project: id, cursor: null, ...(same ? {} : {data: null, reads: {}, boards: [], changeOps: [], walkResult: null})});
  await refreshProject(true);
}

const gate = new SyncGate();
let syncTail: Promise<void> = Promise.resolve();
const reloadAfterWrite = new Set<number>();

// 全量/增量共用单条请求队列；过期响应既不写数据，也不前移游标。
function refreshProject(force = false): Promise<void> {
  const token = gate.token();
  if (!token) return Promise.resolve();
  const task = syncTail.catch(() => {}).then(() => syncProject(token, force));
  syncTail = task;
  return task;
}

async function syncProject(token: SyncToken, force: boolean) {
  if (!gate.valid(token) || getState().dragging) return;
  force ||= reloadAfterWrite.has(token.project);
  let more = true, cursor = getState().cursor, data = getState().data, snapshot = false;
  // 多页先在本地合成再一次发布，避免追旧日志时短暂覆盖刚确认的乐观状态。
  while (more) {
    if (!gate.valid(token) || getState().dragging) return;
    const page = force || cursor == null ? await api.snapshot(token.project) : await api.delta(token.project, cursor);
    force = false;
    if (!gate.valid(token) || getState().dragging) return;
    if (page.mode === 'snapshot') { data = page.data ? adoptOrphans(page.data) : null; snapshot = true; }
    else if (data) data = applyChanges(data, page.changes);
    cursor = page.next_cursor;
    more = page.has_more;
  }
  const layout = snapshot && data ? await api.layout(token.project) : null;
  if (!gate.valid(token) || getState().dragging) return;
  const prev = getState(), oldModel = modelOf(prev), changed = data !== prev.data;
  const before = notesOf(prev)?.list, foldsBefore = prev.data?.folds ?? [];
  const visual = changed && (data?.layers !== prev.data?.layers || data?.roots !== prev.data?.roots || data?.folds !== prev.data?.folds);
  const heights = visual && oldModel ? new Map(prev.boards.map((b) => [keyOf(b), sizeOf(oldModel, b).h])) : null;
  if (changed) {
    setState({data, reads: data?.noteReads ?? {}});
    if (!data) setState({boards: [], active: null, selected: null, walkResult: null, changeOps: []});
    else {
      if (!announceNotes(before)) announceFolds(foldsBefore);
      if (layout) applyLayout(layout, heights);
      else if (visual) {
        const flowed = reflow(getState().boards, heights, modelOf(getState())!);
        if (flowed.changed) { setState({boards: flowed.boards}); saveLayout(); }
      }
      const now = getState(), model = modelOf(now)!;
      let active = now.active;
      if (now.selected != null && active == null) active = model.object(now.selected)?.layer.root ?? null;
      if (active == null || !model.boardOf(now.boards, active)) active = now.boards[0] ? keyOf(now.boards[0]) : null;
      setState({active});
    }
  }
  // 全部完整操作已应用；请求失败时数据和游标都未前移，下次从原位重试。
  setState({cursor});
  if (snapshot) reloadAfterWrite.delete(token.project);
  if (changed && gate.valid(token) && data) { await Promise.all([loadChanges(), loadWalk()]); report(); }
}

// 别人（比如 AI 用 view_note）写了新批注或回复：提示一下。自己写的不提示
function announceNotes(before: Note[] | undefined): boolean {
  const s = getState(), info = notesOf(s);
  if (!before || !info || CAPTURE) return false;
  const old = new Set(before.map((n) => n.id));
  const fresh = info.list.filter((n) => !old.has(n.id) && n.author !== s.me.trim());
  if (!fresh.length) return false;
  const n = fresh[fresh.length - 1], floor = info.threads.findIndex((t) => t.top.id === n.thread) + 1;
  notify({text: ui(n.replyTo != null ? 'notice.newReply' : 'notice.newNote', {
    author: n.author || '', number: floor, text: n.text.slice(0, 40), count: fresh.length,
  }), thread: n.thread});
  return true;
}

// 不是在这个页面上点的折叠变化（AI 展开了你折叠的层、或者 AI 自己折叠了什么）：提示一下
let quietFolds = false;
function announceFolds(before: FoldRow[] | undefined) {
  const s = getState(), model = modelOf(s);
  if (!before || !model || CAPTURE || quietFolds) return;
  const was = new Map(before.map((f) => [f.layer, f]));
  const name = (id: number) => model.layer(id)?.name || tr("common.layerId", {value1: id});
  for (const f of before) if (f.user && !s.data!.folds?.some((g) => g.layer === f.layer && g.user))
    return notify({text: ui("notice.unfolded", {value1: name(f.layer)}), layer: f.layer});
  for (const f of s.data!.folds ?? []) if (f.ai && !was.get(f.layer)?.ai)
    return notify({text: ui("notice.folded", {value1: f.ai, value2: name(f.layer), value3: f.ai_tips ? '：' + f.ai_tips : ''}), layer: f.layer});
}

function notify(notice: {text: string | UiMessage; thread?: number; layer?: number}) {
  setState({notice});
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => setState({notice: null}), 12000);
}
let noticeTimer: ReturnType<typeof setTimeout> | undefined;

function applyLayout(layout: Layout, heights: Map<number, number> | null = null) {
  const s = getState();
  let boards = layout.boards;
  if (s.data?.roots.some((r) => r.id === 0)) boards = [...boards, {rows: [[0]], x: null, y: null, pps: null}];
  const model = modelOf(s)!;
  const placed = placeAuto(boards, model);
  const flowed = reflow(placed.boards, heights, model);
  setState({boards: flowed.boards, serial: layout.serial});
  if (placed.changed || flowed.changed) saveLayout();
}

// 高度变了的画板（从上往下）：正下方的画板跟着推开或收拢；还压在一起的（页面没开着时 AI 折叠、展开了）往下挪开
function reflow(boards: Board[], heights: Map<number, number> | null, model: Model): {boards: Board[]; changed: boolean} {
  let changed = false;
  for (const key of [...boards].filter((b) => b.y != null).sort((p, q) => p.y! - q.y!).map(keyOf)) {
    const b = boards.find((x) => keyOf(x) === key)!, old = heights?.get(key), now = sizeOf(model, b).h;
    if (old != null && now && old !== now) { boards = afterResize(boards, key, old, model); changed = true; }
  }
  const apart = separate(boards, model);
  return {boards: apart.boards, changed: changed || apart.changed};
}

export async function reloadLayout() {
  const s = getState();
  if (s.project == null) return;
  const token = gate.token();
  if (!token) return;
  const layout = await api.layout(s.project);
  if (!gate.valid(token) || getState().dragging || !getState().data) return;
  applyLayout(layout);
  const now = getState(), model = modelOf(now)!;
  if (!model.boardOf(now.boards, now.active)) setState({active: now.boards[0] ? keyOf(now.boards[0]) : null});
}

// 沿读：侧栏开着「沿读」时按起点问服务端；项目重读后也重问一次（关联可能变了）
let walking: Promise<void> | null = null, walkSequence = 0, changesSequence = 0;
export const pendingWalk = () => walking;
export function loadWalk(): Promise<void> {
  const s = getState();
  if (s.side !== 'walk' || !s.walk || s.project == null) return Promise.resolve();
  const {from, direction, depth} = s.walk, project = s.project;
  const sequence = ++walkSequence, token = gate.token();
  walking = api.walk(project, from, direction, depth).then((walkResult) => {
    const now = getState();
    if (sequence === walkSequence && token && gate.valid(token) && now.side === 'walk' && now.project === project && now.walk?.from === from && now.walk.direction === direction && now.walk.depth === depth) setState({walkResult});
  }).catch((error) => { if (sequence === walkSequence && token && gate.valid(token)) { setState({walkResult: null}); toast(ui("relations.readFailed", undefined, (error as Error).message)); } });
  return walking;
}

export async function loadChanges() {
  const s = getState();
  const sequence = ++changesSequence, token = gate.token();
  if (s.side !== 'changes' || s.project == null) return setState({changeOps: []});
  try {
    const changeOps = await api.changes(s.project, s.changeLimit);
    if (sequence === changesSequence && token && gate.valid(token) && getState().side === 'changes') setState({changeOps});
  } catch { if (sequence === changesSequence && token && gate.valid(token)) toast(ui("changes.readFailed")); }
}

let polling: Promise<void> | null = null;
export function poll(): Promise<void> {
  if (!polling) polling = pollOnce().finally(() => { polling = null; });
  return polling;
}
async function pollOnce() {
  try {
    const v = await api.version();
    const s = getState();
    setState({live: true});
    // 插件清单被 view_plugin 命令（或另一个窗口）改了：重新对一遍，新开的载入、关掉的拿下来
    if (v.plugins != null && v.plugins !== s.pluginSerial) {
      setState({pluginSerial: v.plugins});
      if (s.pluginSerial != null) refreshPlugins();
    }
    if (s.dragging || s.project == null || gate.blocked()) return;
    const token = gate.token();
    // 总是从已应用游标继续，版本只是提示，避免首读与第一次轮询之间漏掉提交。
    await refreshProject();
    if (token && gate.valid(token)) {
      setState({version: v.version});
      if (getState().serial != null && v.layout !== getState().serial) await reloadLayout();
    }
  } catch { setState({live: false}); }
}

let saveTimer: ReturnType<typeof setTimeout> | undefined;
export function saveLayout(delay = 0) {
  if (!RECORD) return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveLayoutNow, delay);
}

// 马上存，存完才返回（折叠先挪了画板，要在重读排版之前存好，不然重读回来的是挪之前的位置）
export async function saveLayoutNow() {
  const project = getState().project;
  if (!RECORD || project == null) return;
  clearTimeout(saveTimer);
  const boards = getState().boards.filter((b) => rootsOf(b).every((r) => r > 0)).map(({rows, x, y, pps}) => ({rows, x, y, pps: pps ?? null}));
  const selection = gate.selection();
  try {
    const res = await api.saveLayout(project, boards);
    if (res.serial != null && gate.sameSelection(selection)) setState({serial: res.serial});
  } catch { /* 服务停了：下次轮询会显示断开 */ }
}

// 圈出的一段落在哪个根上：画板第一行在起点处的那一段，换成那个根自己的时间
export function selectionInfo() {
  const s = getState(), model = modelOf(s);
  if (!s.sel || !model) return null;
  const b = s.boards.find((x) => keyOf(x) === s.sel!.key);
  if (!b) return null;
  const seg = model.segmentAt(b.rows[0], s.sel.begin) ?? model.segments(b.rows[0])[0];
  return {root: seg.root, name: model.nameOf(seg.root, tr), begin: +(s.sel.begin - seg.offset).toFixed(3), end: +(s.sel.end - seg.offset).toFixed(3)};
}

let reportTimer: ReturnType<typeof setTimeout> | undefined;
export function report() {
  if (!RECORD || CAPTURE) return;
  clearTimeout(reportTimer);
  reportTimer = setTimeout(() => {
    const s = getState(), model = modelOf(s);
    if (!model) return;
    const act = activeBoard(s), canvas = s.view === 'canvas';
    const shown = canvas ? visibleBoards() : [];
    const sel = s.selected != null ? model.object(s.selected) : undefined;
    const at = s.playhead != null && act ? act.rows.map((row) => model.segmentAt(row, s.playhead!)).filter(Boolean)
      .map((seg) => ({root: seg!.root, name: model.nameOf(seg!.root, tr), local: +(s.playhead! - seg!.offset).toFixed(6)})) : undefined;
    api.state({
      project: s.project, view: s.view, lang: currentLocale(),
      board: act ? {rows: act.rows, names: act.rows.map((row) => row.map((r) => model.nameOf(r, tr))), unit: model.unitOfRoot(keyOf(act))} : undefined,
      range: canvas && act ? visibleRange(act) : undefined,
      playhead: s.playhead ?? undefined, playhead_at: at,
      selected: sel ? {id: sel.id, layer: sel.layer.id, name: sel.name} : undefined,
      selection: selectionInfo() ?? undefined,
      boards: canvas ? shown.map(rootsOf) : undefined,
      layers: (canvas ? shown : s.boards).flatMap((b) => b.rows.flatMap((row) => model.visibleTracks(row).filter((t) => model.foldOf(t) == null)
        .flatMap((t) => t.parts.map((p) => p.layer.id)))),
      folded: [...model.own.keys()].filter((id) => model.layer(id)),
    }).catch(() => {});
  }, 400);
}

// 视图的另一种写入：折叠（只写视图自己的表 view_layer）。网页是人这边：自己这边折叠、展开、写备注；AI 那边只能展开。
// 写完重读项目，画板高度变了下面的跟着挪
export async function foldAction(layers: number[], action: 'fold' | 'unfold' | 'tips', side: 'user' | 'ai' = 'user', tips?: string): Promise<boolean> {
  const s = getState();
  if (s.project == null || !layers.length) return false;
  if (VIEWER === 'ai') { toast(ui("fold.aiReadOnly")); return false; }
  // 先在本地折好、把下面的画板挪好，再写数据库
  const project = s.project, oldModel = modelOf(s), selection = gate.selection(), endWrite = gate.beginWrite(project);
  let saved = false;
  if (oldModel && s.data) {
    const heights = new Map(s.boards.map((b) => [keyOf(b), sizeOf(oldModel, b).h]));
    setState({data: {...s.data, folds: withFolds(s.data.folds ?? [], layers, side, action, s.me, tips)}});
    const flowed = reflow(getState().boards, heights, modelOf(getState())!);
    if (flowed.changed) setState({boards: flowed.boards});
  }
  const failed = (why: string) => { if (getState().project === project) toast(ui("fold.saveFailed", undefined, why)); return false; };
  try {
    const res = await api.fold(project, {action, side, layers, by: s.me.trim(), tips});
    if (res.error || res.recorded === false) return failed(res.error ?? tr("common.readOnly"));
    saved = true;
    if (gate.sameSelection(selection)) await saveLayoutNow();
    return true;
  } catch (error) { return failed((error as Error).message); }
  finally {
    quietFolds = true;
    try { await finishWrite(project, endWrite, !saved); } finally { quietFolds = false; }
  }
}

async function finishWrite(project: number, endWrite: () => void, reset: boolean) {
  if (reset) reloadAfterWrite.add(project);
  endWrite();
  if (getState().project !== project || gate.blocked(project)) return;
  const force = reloadAfterWrite.has(project);
  try {
    await refreshProject(force);
  } catch {
    // 写入可能已经提交；保留游标和待重读标记，轮询重试，不把网络刷新失败说成写入失败。
    reloadAfterWrite.add(project);
    setState({live: false});
  }
}

// 视图的写入之一：批注。写完重读项目；自己写的不用再被轮询重读一遍。
// 同样的请求还没回来时再点一次（双击"发送"、按钮和 Ctrl+回车一起）直接忽略，免得同一句话发两楼
const sending = new Set<string>();
export async function noteAction(body: Record<string, unknown>): Promise<boolean> {
  const s = getState();
  if (s.project == null) return false;
  const key = JSON.stringify([s.project, body]);
  if (sending.has(key)) return false;
  sending.add(key);
  try {
    return await sendNote(s.project, body);
  } finally {
    sending.delete(key);
  }
}

// 已读、标为未读、已处理、重新打开：先改画面（model/optimistic.ts），再写；写失败时重读项目改回去
function guess(body: Record<string, unknown>): boolean {
  const s = getState(), id = Number(body.note), action = body.action;
  if (!s.data || !Number.isFinite(id)) return false;
  if (action === 'read' || action === 'unread') {
    const thread = notesOf(s)?.threads.find((th) => th.top.id === id || th.replies.some((r) => r.id === id));
    if (!thread) return false;
    setState({reads: withRead(s.reads, thread, String(body.reader ?? ''), action === 'read')});
    return true;
  }
  if (action === 'done' || action === 'reopen') {
    setState({data: withNoteStatus(s.data, id, action === 'done' ? 'done' : 'open')});
    return true;
  }
  return false;
}

async function sendNote(project: number, body: Record<string, unknown>): Promise<boolean> {
  const endWrite = gate.beginWrite(project);
  guess(body);
  let saved = false;
  try {
    const res = await api.note(project, body);
    if (res.error || res.recorded === false) {
      if (getState().project === project) toast(ui("notes.saveFailed", undefined, (res.error ?? tr("common.readOnly"))));
      return false;
    }
    saved = true;
    return true;
  } catch (error) {
    if (getState().project === project) toast(ui("notes.saveFailed", undefined, (error as Error).message));
    return false;
  } finally { await finishWrite(project, endWrite, !saved); }
}

// 和服务同步：读项目和排版、每 2 秒看有没有变化、保存排版、报告"正在看哪儿"、写批注
import {api} from './api';
import {visibleBoards, visibleRange} from './camera';
import {afterResize, placeAuto, separate, sizeOf} from './model/layoutOps';
import {adoptOrphans, keyOf, rootsOf} from './model/model';
import type {Note} from './model/notes';
import {CAPTURE, RECORD, VIEWER, numParam} from './params';
import {activeBoard, getState, modelOf, notesOf, setState} from './store';
import type {FoldRow, Layout} from './types';

let toastTimer: ReturnType<typeof setTimeout> | undefined;
export function toast(text: string, ms = 2500) {
  setState({message: text});
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => setState({message: ''}), ms);
}

export async function loadProjects() {
  const [capabilities, projects] = await Promise.all([api.capabilities(), api.projects()]);
  setState({frames: capabilities.frames, projects});
  const want = numParam('project') ?? projects[0]?.id;
  if (!want) return setState({message: '数据库里还没有项目。'});
  await loadProject(want);
}

export async function loadProject(id: number) {
  const prev = getState(), same = prev.project === id, oldModel = same ? modelOf(prev) : null;
  const before = same ? notesOf(prev)?.list : undefined, foldsBefore = same ? prev.data?.folds ?? [] : undefined;
  // 记下重读之前每块画板的高度：折叠、加层以后画板变高变矮，下面的画板跟着挪
  const heights = oldModel ? new Map(prev.boards.map((b) => [keyOf(b), sizeOf(oldModel, b).h])) : null;
  const [data, layout] = await Promise.all([api.project(id), api.layout(id)]);
  setState({project: id, data: adoptOrphans(data)});
  if (!announceNotes(before)) announceFolds(foldsBefore);
  applyLayout(layout, heights);
  await loadChanges();
  const s = getState(), model = modelOf(s)!;
  let active = s.active;
  if (s.selected != null && active == null) active = model.object(s.selected)?.layer.root ?? null;
  if (active == null || !model.boardOf(s.boards, active)) active = s.boards[0] ? keyOf(s.boards[0]) : null;
  setState({active});
  report();
}

// 别人（比如 AI 用 view_note）写了新批注或回复：提示一下。自己写的不提示
function announceNotes(before: Note[] | undefined): boolean {
  const s = getState(), info = notesOf(s);
  if (!before || !info || CAPTURE) return false;
  const old = new Set(before.map((n) => n.id));
  const fresh = info.list.filter((n) => !old.has(n.id) && n.author !== s.me.trim());
  if (!fresh.length) return false;
  const n = fresh[fresh.length - 1], floor = info.threads.findIndex((t) => t.top.id === n.thread) + 1;
  const what = n.replyTo != null ? `回复了第 ${floor} 楼` : `写了新批注（第 ${floor} 楼）`;
  notify({text: `${n.author || '有人'}${what}：${n.text.slice(0, 40)}${fresh.length > 1 ? `（共 ${fresh.length} 条新的）` : ''}`, thread: n.thread});
  return true;
}

// 不是在这个页面上点的折叠变化（AI 展开了你折叠的层、或者 AI 自己折叠了什么）：提示一下
let quietFolds = false;
function announceFolds(before: FoldRow[] | undefined) {
  const s = getState(), model = modelOf(s);
  if (!before || !model || CAPTURE || quietFolds) return;
  const was = new Map(before.map((f) => [f.layer, f]));
  const name = (id: number) => model.layer(id)?.name || `层 ${id}`;
  for (const f of before) if (f.user && !s.data!.folds?.some((g) => g.layer === f.layer && g.user))
    return notify({text: `你折叠的「${name(f.layer)}」被展开了：AI 想给你看这里`, layer: f.layer});
  for (const f of s.data!.folds ?? []) if (f.ai && !was.get(f.layer)?.ai)
    return notify({text: `${f.ai} 折叠了「${name(f.layer)}」${f.ai_tips ? '：' + f.ai_tips : ''}`, layer: f.layer});
}

function notify(notice: {text: string; thread?: number; layer?: number}) {
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
  boards = placed.boards;
  let changed = placed.changed;
  // 高度变了的画板（从上往下）：正下方的画板跟着推开或收拢
  for (const key of [...boards].filter((b) => b.y != null).sort((p, q) => p.y! - q.y!).map(keyOf)) {
    const b = boards.find((x) => keyOf(x) === key)!, old = heights?.get(key), now = sizeOf(model, b).h;
    if (old != null && now && old !== now) { boards = afterResize(boards, key, old, model); changed = true; }
  }
  // 还压在一起的（页面没开着时 AI 折叠、展开了）：往下挪开
  const apart = separate(boards, model);
  setState({boards: apart.boards, serial: layout.serial});
  if (changed || apart.changed) saveLayout();
}

export async function reloadLayout() {
  const s = getState();
  if (s.project == null) return;
  applyLayout(await api.layout(s.project));
  const now = getState(), model = modelOf(now)!;
  if (!model.boardOf(now.boards, now.active)) setState({active: now.boards[0] ? keyOf(now.boards[0]) : null});
}

export async function loadChanges() {
  const s = getState();
  if (s.side !== 'changes' || s.project == null) return setState({changeOps: []});
  try { setState({changeOps: await api.changes(s.project, s.changeLimit)}); } catch { toast('读不到改动记录'); }
}

export async function poll() {
  try {
    const v = await api.version();
    const s = getState();
    setState({live: true});
    if (s.dragging || s.project == null) return;
    if (s.version != null && v.version !== s.version) { setState({version: v.version}); await loadProject(s.project); return; }
    setState({version: v.version});
    if (s.serial != null && v.layout !== s.serial) await reloadLayout();
  } catch { setState({live: false}); }
}

let saveTimer: ReturnType<typeof setTimeout> | undefined;
export function saveLayout(delay = 0) {
  if (!RECORD) return;
  const project = getState().project;
  if (project == null) return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    const boards = getState().boards.filter((b) => rootsOf(b).every((r) => r > 0)).map(({rows, x, y, pps}) => ({rows, x, y, pps: pps ?? null}));
    try {
      const res = await api.saveLayout(project, boards);
      if (res.serial != null && project === getState().project) setState({serial: res.serial});
    } catch { /* 服务停了：下次轮询会显示断开 */ }
  }, delay);
}

// 圈出的一段落在哪个根上：画板第一行在起点处的那一段，换成那个根自己的时间
export function selectionInfo() {
  const s = getState(), model = modelOf(s);
  if (!s.sel || !model) return null;
  const b = s.boards.find((x) => keyOf(x) === s.sel!.key);
  if (!b) return null;
  const seg = model.segmentAt(b.rows[0], s.sel.begin) ?? model.segments(b.rows[0])[0];
  return {root: seg.root, name: model.nameOf(seg.root), begin: +(s.sel.begin - seg.offset).toFixed(3), end: +(s.sel.end - seg.offset).toFixed(3)};
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
      .map((seg) => ({root: seg!.root, name: model.nameOf(seg!.root), local: +(s.playhead! - seg!.offset).toFixed(6)})) : undefined;
    api.state({
      project: s.project, view: s.view,
      board: act ? {rows: act.rows, names: act.rows.map((row) => row.map((r) => model.nameOf(r))), unit: model.unitOfRoot(keyOf(act))} : undefined,
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
  if (VIEWER === 'ai') { toast('这是 AI 那边的样子，只看不改折叠'); return false; }
  try {
    const res = await api.fold(s.project, {action, side, layers, by: s.me.trim(), tips});
    if (res.error || res.recorded === false) { toast('折叠没有存下来：' + (res.error ?? '这个页面只读')); return false; }
    quietFolds = true;
    try { await loadProject(s.project); } finally { quietFolds = false; }
    setState({version: (await api.version()).version});
    return true;
  } catch (error) { toast('折叠没有存下来：' + (error as Error).message); return false; }
}

// 视图的写入之一：批注。写完重读项目；自己写的不用再被轮询重读一遍
export async function noteAction(body: Record<string, unknown>): Promise<boolean> {
  const s = getState();
  if (s.project == null) return false;
  try {
    const res = await api.note(s.project, body);
    if (res.error || res.recorded === false) { toast('批注没有写进去：' + (res.error ?? '这个页面只读')); return false; }
    await loadProject(s.project);
    setState({version: (await api.version()).version});
    return true;
  } catch (error) { toast('批注没有写进去：' + (error as Error).message); return false; }
}

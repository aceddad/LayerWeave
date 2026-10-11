// 页面的全部状态放在一个 zustand store 里；画面模型、批注楼、改动标记都由状态算出来并缓存
import {create} from 'zustand';
import {changeMarks, noMarks} from './model/changes';
import type {ChangeMarks} from './model/changes';
import {Model} from './model/model';
import {noteIndex, noteList, noteThreads} from './model/notes';
import type {Note, Thread} from './model/notes';
import type {Drop} from './model/dropRule';
import {VIEWER, numParam, params} from './params';
import type {Board, ChangeOp, ProjectData, ProjectSummary, Side, View} from './types';

export type {Drop};

export interface State {
  projects: ProjectSummary[];
  project: number | null;
  data: ProjectData | null;
  boards: Board[];
  serial: number | null;
  version: number | null;
  frames: boolean;
  live: boolean;
  message: string;
  notice: {text: string; thread?: number; layer?: number} | null;   // 右下角的提示：别人写了新批注、展开了你折叠的层；点一下过去
  view: View;
  side: Side;
  active: number | null;                                  // 当前画板（用其中任一根层的编号表示）
  playhead: number | null;                                // 当前画板上的时间（左右接续时是连续时间）
  selected: number | null;
  only: Set<number> | null;
  showHidden: boolean;
  assetKind: string;
  changeLimit: number;
  changeOps: ChangeOp[];
  links: boolean;
  sel: {key: number; begin: number; end: number} | null;  // 在尺子上圈出的一段（画板时间）
  targetLayer: number | null;                             // 点层名选中的层：写批注时指向它
  wholeProject: boolean;
  noteFilter: 'all' | 'open' | 'done' | 'waiting';
  noteFocus: number | null;                               // 镜头对准的那条批注（地址参数 note、批注上的"定位"）：它的楼和目标高亮
  me: string;                                             // 本机署名：写批注用，也用来算"等我回复"的楼
  canvasW: number;
  canvasH: number;
  dragging: boolean;
  drop: Drop | null;
  autoFit: boolean;
  set: (patch: Partial<State> | ((s: State) => Partial<State>)) => void;
}

const viewParam = params.get('view');
export const useStore = create<State>((set) => ({
  projects: [], project: null, data: null, boards: [], serial: null, version: null,
  frames: false, live: false, message: '', notice: null,
  view: viewParam === 'assets' || viewParam === 'cuts' ? viewParam : 'canvas',
  side: params.get('side') === 'notes' || params.has('note') ? 'notes' : params.has('changes') ? 'changes' : 'now',
  active: numParam('board'), playhead: numParam('playhead'), selected: numParam('select'),
  only: params.has('layers') ? new Set(params.get('layers')!.split(',').map(Number)) : null,
  showHidden: false, assetKind: 'all',
  changeLimit: numParam('changes') || 10, changeOps: [],
  links: params.get('links') === '1',
  sel: null, targetLayer: null, wholeProject: false,
  noteFilter: 'all', noteFocus: numParam('note'), me: localStorage.getItem('lw-author') || '用户',
  canvasW: Math.max(600, window.innerWidth - 340), canvasH: Math.max(400, window.innerHeight - 50),
  dragging: false, drop: null, autoFit: true,
  set: (patch) => set(patch as any),
}));

export const getState = () => useStore.getState();
export const setState = (patch: Partial<State>) => useStore.getState().set(patch);

// ---------- 由状态算出来、按输入缓存的东西 ----------
let modelCache: {key: unknown[]; model: Model} | null = null;
export function modelOf(s: State): Model | null {
  if (!s.data) return null;
  const key = [s.data, s.only, s.showHidden, s.canvasW];
  if (modelCache && modelCache.key.every((v, i) => v === key[i])) return modelCache.model;
  modelCache = {key, model: new Model(s.data, {viewer: VIEWER, only: s.only, showHidden: s.showHidden, canvasWidth: s.canvasW})};
  return modelCache.model;
}
export const useModel = () => useStore(modelOf);

export interface NotesInfo { list: Note[]; threads: Thread[]; index: Map<string, Thread[]> }
let notesCache: {model: Model; value: NotesInfo} | null = null;
export function notesOf(s: State): NotesInfo | null {
  const model = modelOf(s);
  if (!model) return null;
  if (notesCache?.model !== model) {
    const list = noteList(model), threads = noteThreads(list);
    notesCache = {model, value: {list, threads, index: noteIndex(threads, model.project)}};
  }
  return notesCache.value;
}
export const useNotes = () => useStore(notesOf);

let marksCache: {model: Model; ops: ChangeOp[]; value: ChangeMarks} | null = null;
export function marksOf(s: State): ChangeMarks {
  const model = modelOf(s);
  if (!model || s.side !== 'changes') return noMarks;
  if (marksCache?.model !== model || marksCache.ops !== s.changeOps) marksCache = {model, ops: s.changeOps, value: changeMarks(s.changeOps, model)};
  return marksCache.value;
}
export const useMarks = () => useStore(marksOf);

export const activeBoard = (s: State): Board | undefined => modelOf(s)?.boardOf(s.boards, s.active) ?? s.boards[0];

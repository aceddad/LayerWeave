import {readPreference} from './preferences';
import type {UiMessage} from './i18n/types';
// 页面的全部状态放在一个 zustand store 里；画面模型、批注楼、改动标记都由状态算出来并缓存
import {create} from 'zustand';
import {changeMarks, noMarks} from './model/changes';
import type {ChangeMarks} from './model/changes';
import {Model} from './model/model';
import {noteIndex, noteList, noteThreads, waitingFor} from './model/notes';
import type {Note, NoteReads, Thread} from './model/notes';
import type {Drop} from './model/dropRule';
import type {LoadedPlugin} from './plugin/host';
import {CAPTURE, VIEWER, numParam, params} from './params';
import type {Board, ChangeOp, PluginList, ProjectData, ProjectSummary, Side, View, WalkDirection, WalkResult} from './types';

export type {Drop};

export interface State {
  projects: ProjectSummary[];
  project: number | null;
  data: ProjectData | null;
  boards: Board[];
  serial: number | null;
  version: number | null;
  cursor: number | null;                                  // 只有完整页应用成功才前移
  frames: boolean;
  live: boolean;
  message: string | UiMessage;
  notice: {text: string | UiMessage; thread?: number; layer?: number} | null;   // 右下角的提示：别人写了新批注、展开了你折叠的层；点一下过去
  view: View;
  side: Side;
  active: number | null;                                  // 当前画板（用其中任一根层的编号表示）
  playhead: number | null;                                // 当前画板上的时间（左右接续时是连续时间）
  selected: number | null;
  only: Set<number> | null;
  showHidden: boolean;
  changeLimit: number;
  changeOps: ChangeOp[];
  links: boolean;
  sel: {key: number; begin: number; end: number} | null;  // 在尺子上圈出的一段（画板时间）
  targetLayer: number | null;                             // 点层名选中的层：写批注时指向它
  picked: number[];                                       // 左边目录树里勾选的层（只是"选了一组"，不藏别的层；插件读得到）
  tree: boolean;                                          // 左边目录树开着吗（记在本机；截图默认关，tree=1 才开）
  wholeProject: boolean;
  noteFilter: 'open' | 'done' | 'waiting';               // 已处理的楼只在"已处理"里出现，默认看待处理的
  noteFocus: number | null;                               // 镜头对准的那条批注（地址参数 note、批注上的"定位"）：它的楼和目标高亮
  me: string;                                             // 本机署名：写批注用，也用来算"等我回复"的楼
  walk: {from: string; direction: WalkDirection; depth: number} | null;   // 沿读的起点（侧栏「沿读」）
  walkResult: WalkResult | null;
  reads: NoteReads;                                       // 批注的已读（读项目时从 data.noteReads 拿；点"已读"先改这里，不等服务端，也不重建画面模型）
  canvasW: number;
  canvasH: number;
  dragging: boolean;
  drop: Drop | null;
  autoFit: boolean;
  plugins: LoadedPlugin[];  // 载入了的插件，按清单的顺序（plugin/registry.ts）
  pluginList: PluginList | null;           // 本机插件清单（顶栏「插件」小窗列出来）
  pluginErrors: Record<string, string>;    // 开着但没载入上的插件：名字 → 原因
  pluginSerial: number | null;             // 清单文件的修改时间：命令改了清单，轮询时发现，页面跟着重新对一遍
  settledZoom: number;   // 镜头停下来时的缩放：格子按它决定画多细（缩放过程中不换，免得每跨一档几百个格子一起重画）
  set: (patch: Partial<State> | ((s: State) => Partial<State>)) => void;
}

const viewParam = params.get('view');
// 和 styles.css 里 .side、.tree 的 clamp 一致（加 1 像素边框）
const clamp = (min: number, v: number, max: number) => Math.min(max, Math.max(min, v));
const sideWidth = () => clamp(240, window.innerWidth * .28, 340) + 1;
const treeWidth = () => clamp(220, window.innerWidth * .2, 300) + 1;
// 地址里有 tree=0/1 就按它（截图 --tree、测试），否则截图默认关、网页按本机记的（默认开）
const treeOpen = params.has('tree') ? params.get('tree') === '1' : CAPTURE ? false : readPreference('lw-tree') !== '0';
export const useStore = create<State>((set) => ({
  projects: [], project: null, data: null, boards: [], serial: null, version: null, cursor: null,
  frames: false, live: false, message: '', notice: null,
  view: viewParam || 'canvas',                            // 插件的页面要等插件加载完才知道有没有；没有就回画布（registry.ts）
  side: params.has('walk') ? 'walk' : params.get('side') === 'notes' || params.has('note') ? 'notes' : params.has('changes') ? 'changes' : params.get('side') || 'now',   // 插件的侧栏：载入完才知道有没有，没有就回「此刻」
  walk: params.has('walk') ? {from: params.get('walk')!, direction: (params.get('walkdir') as WalkDirection) || 'both',
                               depth: Number(params.get('walkdepth') || 3)} : null,
  walkResult: null,
  active: numParam('board'), playhead: numParam('playhead'), selected: numParam('select'),
  only: params.has('layers') ? new Set(params.get('layers')!.split(',').map(Number)) : null,
  showHidden: false,
  changeLimit: numParam('changes') || 10, changeOps: [],
  links: params.get('links') === '1',
  sel: null, targetLayer: null, wholeProject: false, picked: [],
  tree: treeOpen,
  noteFilter: 'open', noteFocus: numParam('note'), me: readPreference('lw-author') || '用户', reads: {},
  canvasW: Math.max(600, window.innerWidth - sideWidth() - (treeOpen ? treeWidth() : 0)),   // 先按样式估准，画布量到的一样就不用再排一遍
  canvasH: Math.max(400, window.innerHeight - 50),
  dragging: false, drop: null, autoFit: true, settledZoom: 0, plugins: [], pluginList: null, pluginErrors: {}, pluginSerial: null,
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
  modelCache = {key, model: new Model(s.data, {viewer: VIEWER, only: s.only, showHidden: s.showHidden, canvasWidth: s.canvasW}, modelCache?.model)};
  return modelCache.model;
}
export const useModel = () => useStore(modelOf);

export interface NotesInfo { list: Note[]; threads: Thread[]; index: Map<string, Thread[]> }
let notesCache: {project: number; layers: ProjectData['layers']; binds: ProjectData['binds']; key: unknown[]; value: NotesInfo} | null = null;
export function notesOf(s: State): NotesInfo | null {
  const model = modelOf(s);
  if (!model) return null;
  if (notesCache?.project === model.project && notesCache.layers === model.data.layers && notesCache.binds === model.data.binds) return notesCache.value;
  const key = [model.project, model.data.binds, ...model.data.layers.filter((l) => l.role === 'note')];
  if (!notesCache || notesCache.key.length !== key.length || notesCache.key.some((v, i) => v !== key[i])) {
    const list = noteList(model), threads = noteThreads(list);
    notesCache = {project: model.project, layers: model.data.layers, binds: model.data.binds, key, value: {list, threads, index: noteIndex(threads, model.project)}};
  } else {
    notesCache.layers = model.data.layers;
    notesCache.binds = model.data.binds;
  }
  return notesCache.value;
}
export const useNotes = () => useStore(notesOf);
// 这一刻要画关系线的端点（"object:16"、"layer:5"）：只有它们挂 React Flow 的连接点。
// 每个对象都挂的话，5000 个对象就是一万个点，画板一动 React Flow 就要把它们的位置全量一遍（2026-10-14 量的：打开时最耗时的就是这个）
// 内容没变就还给原来那个 Set：选了一个没有关联的对象时，端点照旧是空的，画板不用重新量连接点
let handleCache: {key: unknown[]; value: Set<string>} | null = null;
export function handleKeysOf(s: State): Set<string> {
  const model = modelOf(s);
  const key = [model, s.links, s.selected];
  if (handleCache && handleCache.key.every((v, i) => v === key[i])) return handleCache.value;
  const value = new Set<string>();
  if (model) {
    const mine = (r: {kind: string; project: number; id: number}) => r.kind === 'object' && r.project === model.project && r.id === s.selected;
    for (const b of model.data.binds) {
      if (!s.links && !(s.selected != null && (mine(b.source) || mine(b.target)))) continue;
      if (b.source.project !== model.project || b.target.project !== model.project) continue;
      value.add(`${b.source.kind}:${b.source.id}`);
      value.add(`${b.target.kind}:${b.target.id}`);
    }
  }
  const old = handleCache?.value;
  handleCache = {key, value: old && old.size === value.size && [...value].every((k) => old.has(k)) ? old : value};
  return handleCache.value;
}

// 对准的那条批注（noteFocus）指着的对象和层（"object:16"、"layer:5"）：画布上高亮
const noHot = new Set<string>();
let hotCache: {key: unknown[]; value: Set<string>} | null = null;
export function hotOf(s: State): Set<string> {
  const notes = notesOf(s);
  const key = [notes, s.noteFocus, s.project];
  if (hotCache && hotCache.key.every((v, i) => v === key[i])) return hotCache.value;
  const top = s.noteFocus != null ? notes?.threads.find((t) => t.top.id === s.noteFocus)?.top : undefined;
  const value = top ? new Set(top.targets.filter((t) => t.project === s.project).map((t) => `${t.kind}:${t.id}`)) : noHot;
  hotCache = {key, value};
  return value;
}

// 在等本机署名的楼（没处理、最后一句不是我说的、我也没标已读）：标签上的数字、标题、"等我回复"都用它
export const waitingOf = (s: State) => waitingFor(notesOf(s)?.threads ?? [], s.me, s.reads);

let marksCache: {model: Model; ops: ChangeOp[]; value: ChangeMarks} | null = null;
export function marksOf(s: State): ChangeMarks {
  const model = modelOf(s);
  if (!model || s.side !== 'changes') return noMarks;
  if (marksCache?.model !== model || marksCache.ops !== s.changeOps) marksCache = {model, ops: s.changeOps, value: changeMarks(s.changeOps, model)};
  return marksCache.value;
}
export const useMarks = () => useStore(marksOf);

export const activeBoard = (s: State): Board | undefined => modelOf(s)?.boardOf(s.boards, s.active) ?? s.boards[0];

import {ui, tr, useI18n} from './i18n';
// 镜头：画布的平移、缩放由 React Flow 管；这里放"把镜头对准某处"的几种做法，面板和顶栏都从这里调
import type {ReactFlowInstance} from '@xyflow/react';
import {NAMES} from './model/model';
import {keyOf} from './model/model';
import {sizeOf} from './model/layoutOps';
import {setScale} from './model/boardStyle';
import {saveLayout} from './sync';
import {CAPTURE, params} from './params';
import {activeBoard, getState, modelOf, notesOf, setState} from './store';
import type {Board} from './types';
import {liveBoard} from './canvas/dragState';
export {liveBoard} from './canvas/dragState';

let flow: ReactFlowInstance | null = null;
let pane: HTMLElement | null = null;

export const TRACKS_X = 1 + NAMES;   // 轨道区在画板里的横向起点（左边框 1 像素 + 名字列）

export function attachCamera(instance: ReactFlowInstance, element: HTMLElement) { flow = instance; pane = element; }
export const viewport = () => flow?.getViewport() ?? {x: 0, y: 0, zoom: 1};
export const toFlow = (clientX: number, clientY: number) => flow?.screenToFlowPosition({x: clientX, y: clientY}) ?? {x: clientX, y: clientY};
const paneRect = () => pane?.getBoundingClientRect() ?? new DOMRect(0, 0, getState().canvasW, getState().canvasH);

function setView(x: number, y: number, zoom: number) {
  flow?.setViewport({x, y, zoom: Math.min(4, Math.max(0.05, zoom))});
  settleZoom();
}

// 镜头停下来以后才换格子的细节档（Flow 的 onMoveEnd 和程序里设镜头都走这里）
let settleTimer: ReturnType<typeof setTimeout> | undefined;
let zoomReady: Promise<void> = Promise.resolve(), finishZoom: (() => void) | null = null;
export const pendingZoom = () => zoomReady;
export function settleZoom(delay = CAPTURE ? 0 : 120) {   // 截图时镜头只设一次，马上换档，免得拍到旧清晰度
  clearTimeout(settleTimer);
  if (!finishZoom) zoomReady = new Promise<void>((resolve) => { finishZoom = resolve; });
  settleTimer = setTimeout(() => {
    const zoom = flow?.getViewport().zoom;
    if (zoom != null && zoom !== getState().settledZoom) setState({settledZoom: zoom});
    settleTimer = undefined;
    const done = finishZoom;
    finishZoom = null;
    done?.();
  }, delay);
}

// 画板时间 → 画布上的横坐标（世界坐标）
export function timeToX(b: Board, t: number) {
  b = liveBoard(b);
  const model = modelOf(getState())!;
  return (b.x ?? 0) + TRACKS_X + (t - model.extent(b)[0]) * model.pps(b);
}
export function xToTime(b: Board, worldX: number) {
  b = liveBoard(b);
  const model = modelOf(getState())!;
  return model.extent(b)[0] + (worldX - (b.x ?? 0) - TRACKS_X) / model.pps(b);
}

// 让这些画板正好放进画面（最多放大到 1 倍），左上对齐
export function fitBoards(keys?: number[]) {
  const s = getState(), model = modelOf(s);
  if (!model || !flow) return;
  const boards = s.boards.filter((b) => (!keys || keys.includes(keyOf(b))) && b.x != null && b.y != null && sizeOf(model, b).h);
  if (!boards.length) return;
  const rect = paneRect();
  if (rect.height < 50) return;                           // 页面还没有尺寸（比如在后台标签里打开）
  const x0 = Math.min(...boards.map((b) => b.x!)), y0 = Math.min(...boards.map((b) => b.y!));
  const x1 = Math.max(...boards.map((b) => b.x! + sizeOf(model, b).w)), y1 = Math.max(...boards.map((b) => b.y! + sizeOf(model, b).h));
  const pad = 24, z = Math.max(0.05, Math.min(1, (rect.width - 2 * pad) / (x1 - x0), (rect.height - 2 * pad - 20) / (y1 - y0)));
  setView(pad - x0 * z, pad - y0 * z, z);
}

export function zoomBy(f: number) {
  const {x, y, zoom} = viewport(), rect = paneRect(), cx = rect.width / 2, cy = rect.height / 2;
  const z = Math.min(4, Math.max(0.05, zoom * f)), k = z / zoom;
  setView(cx - (cx - x) * k, cy - (cy - y) * k, z);
}

// 让某块画板的 [begin, end] 正好铺满画面宽度（截图、外部链接用；不改存下来的缩放）
export function focusRange(key: number, begin: number, end: number) {
  const s = getState(), rect = paneRect();
  const boards = s.boards.map((b) => (keyOf(b) === key ? {...b, tempPps: Math.max(1e-6, rect.width - NAMES - 40) / Math.max(1e-6, end - begin)} : b));
  setState({boards});
  const b = boards.find((x) => keyOf(x) === key)!;
  setView(NAMES + 12 - timeToX(b, begin), 16 - (b.y ?? 0), 1);
}

// 页面刚打开：按地址参数对准（截图工具就是这样指定拍哪里的）。明确给了范围的按范围，其次对准批注，再其次某块画板
// 打开网页时：全部画板一起放得下、还看得清（缩放不小于 0.6）就全放；放不下时（画板上下排得很高），
// 先让当前画板横向铺满、顶端对齐，往下滚就是别的画板。顶栏「全部」照旧显示全部。截图不受影响，照旧拍全部
const READABLE = 0.6;
function fitReadable(): boolean {
  const s = getState(), model = modelOf(s), b = activeBoard(s);
  if (!model || !flow || !b || b.x == null || b.y == null) return false;
  const placed = s.boards.filter((x) => x.x != null && x.y != null && sizeOf(model, x).h);
  const rect = paneRect(), pad = 24;
  if (rect.height < 50 || !placed.length) return false;
  const x0 = Math.min(...placed.map((x) => x.x!)), y0 = Math.min(...placed.map((x) => x.y!));
  const x1 = Math.max(...placed.map((x) => x.x! + sizeOf(model, x).w)), y1 = Math.max(...placed.map((x) => x.y! + sizeOf(model, x).h));
  const all = Math.min(1, (rect.width - 2 * pad) / (x1 - x0), (rect.height - 2 * pad - 20) / (y1 - y0));
  if (all >= READABLE) return false;
  const z = Math.max(0.05, Math.min(1, (rect.width - 2 * pad) / sizeOf(model, b).w));
  setView(pad - b.x * z, pad - b.y * z, z);
  return true;
}
export function focusInitial() {
  const s = getState(), b = activeBoard(s);
  if (b && params.has('begin') && params.has('end')) focusRange(keyOf(b), Number(params.get('begin')), Number(params.get('end')));
  else if (params.has('note')) focusNote(Number(params.get('note')));
  else if (b && params.has('board')) fitBoards([keyOf(b)]);
  else if (CAPTURE || !fitReadable()) fitBoards();
  if (params.has('focus')) requestAnimationFrame(() => focusObject(Number(params.get('focus'))));
}

// 镜头移到某个对象（或删除前的虚线框）上，放在画面左上三分之一处
export function focusObject(id: number, ghost = false): boolean {
  const find = () => pane?.querySelector<HTMLElement>(ghost ? `.ghost[data-ghost="${id}"]` : `.obj[data-id="${id}"]`) ?? null;
  const node = find();
  if (!node) { setState({message: ui("navigation.objectHidden")}); setTimeout(() => setState({message: ''}), 2500); return false; }
  let {x, y, zoom} = viewport();
  if (zoom < 0.6) { const rect = paneRect(); const k = 0.8 / zoom; x = rect.width / 2 - (rect.width / 2 - x) * k; y = rect.height / 2 - (rect.height / 2 - y) * k; zoom = 0.8; }
  const r = node.getBoundingClientRect(), p = paneRect(), current = viewport(), k = zoom / current.zoom;
  // 换算到新缩放下对象的位置，再平移到画面左上三分之一
  const left = (r.left - p.left - current.x) * k + x, top = (r.top - p.top - current.y) * k + y;
  setView(x + p.width / 3 - left, y + p.height / 3 - top, zoom);
  setState({autoFit: false});
  return true;
}

// 镜头移到某块画板上的某个时刻（批注指向的一段时间）
export function focusTime(b: Board, t: number) {
  const rect = paneRect();
  let {zoom} = viewport();
  if (zoom < 0.6) zoom = 0.8;
  setView(rect.width / 3 - timeToX(b, t) * zoom, 40 - (b.y ?? 0) * zoom, zoom);
  setState({autoFit: false});
}

// 时间缩放：只改这块画板每单位的像素数，鼠标下的那一刻留在原处
export function timeZoom(key: number, factor: number | null, clientX?: number) {
  const s = getState(), model = modelOf(s);
  const b = s.boards.find((x) => keyOf(x) === key);
  if (!model || !b) return;
  const rect = paneRect(), cx = clientX ?? rect.left + rect.width / 2;
  const t = xToTime(b, toFlow(cx, 0).x), old = model.pps(b);
  const [a, e] = model.extent(b);
  const nb = setScale(b, factor == null ? Math.max(400, rect.width - NAMES - 90) / Math.max(1e-6, e - a) : Math.max(1e-6, old * factor));
  delete nb.tempPps;
  setState({boards: s.boards.map((x) => (x === b ? nb : x)), autoFit: false});
  saveLayout(300);
  if (factor != null) {
    const {x, y, zoom} = viewport();
    const nowX = rect.left + x + ((b.x ?? 0) + TRACKS_X + (t - model.extent(b)[0]) * old * factor) * zoom;
    setView(x + (cx - nowX), y, zoom);
  }
}

// 屏幕上看得见的画板，和当前画板上看得见的那段时间（报告"正在看哪儿"用）
export function visibleBoards(): Board[] {
  const s = getState(), model = modelOf(s);
  if (!model) return [];
  const {x, y, zoom} = viewport(), rect = paneRect();
  const l = -x / zoom, t = -y / zoom, r = (rect.width - x) / zoom, bottom = (rect.height - y) / zoom;
  return s.boards.filter((b) => {
    const {w, h} = sizeOf(model, b);
    return h && b.x != null && b.y != null && b.x < r && b.x + w > l && b.y < bottom && b.y + h > t;
  });
}
export function visibleRange(b: Board): [number, number] | undefined {
  const model = modelOf(getState());
  if (!model) return undefined;
  const {x, zoom} = viewport(), rect = paneRect(), [a, e] = model.extent(b), pps = model.pps(b);
  const left = -x / zoom, right = (rect.width - x) / zoom;
  const t0 = Math.max(a, a + Math.max(0, left - (b.x ?? 0)) / pps), t1 = Math.min(e, a + (right - (b.x ?? 0) - TRACKS_X) / pps);
  return t1 > t0 ? [+t0.toFixed(3), +t1.toFixed(3)] : undefined;
}

// 把画布上的一块区域（世界坐标）放进画面中间；放得下就不放大到超过 1 倍
function fitRect(x0: number, y0: number, x1: number, y1: number) {
  const rect = paneRect(), pad = 60;
  if (rect.height < 50) return;
  const z = Math.max(0.05, Math.min(1, (rect.width - 2 * pad) / Math.max(1, x1 - x0), (rect.height - 2 * pad) / Math.max(1, y1 - y0)));
  setView(rect.width / 2 - ((x0 + x1) / 2) * z, rect.height / 2 - ((y0 + y1) / 2) * z, z);
}

// 镜头对准一条批注（或它所在的楼）指的全部地方：对象、层（有时间段时只框那一段）。写给整个项目的批注显示全部画板
export function focusNote(id: number): boolean {
  const s = getState(), model = modelOf(s), notes = notesOf(s);
  const thread = notes?.threads.find((t) => t.top.id === id || t.replies.some((r) => r.id === id));
  if (!model || !thread || !pane) return false;
  setState({noteFocus: thread.top.id, autoFit: false});   // 批注列表会切到看得见这一楼的那一类（NotesPanel）
  const {top} = thread, targets = top.targets.filter((t) => t.project === s.project);
  if (!targets.length) { fitBoards(); return true; }
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  const add = (ax: number, ay: number, bx: number, by: number) => { x0 = Math.min(x0, ax); y0 = Math.min(y0, ay); x1 = Math.max(x1, bx); y1 = Math.max(y1, by); };
  const world = (r: DOMRect) => { const a = toFlow(r.left, r.top), b = toFlow(r.right, r.bottom); return [a.x, a.y, b.x, b.y] as const; };
  for (const t of targets) {
    if (t.kind === 'object') {
      pane.querySelectorAll(`.obj[data-id="${t.id}"]`).forEach((el) => add(...world(el.getBoundingClientRect())));
      continue;
    }
    const layer = model.layer(t.id), b = layer && model.boardOf(s.boards, layer.root);
    const row = [...pane.querySelectorAll<HTMLElement>('.lname')].find((el) => el.dataset.layers?.split(' ').includes(String(t.id)));
    if (!b || !row) continue;
    const [ax, ay, bx, by] = world(row.getBoundingClientRect());
    if (top.span) {
      const offset = model.offsetOf(s.boards, layer!.root!);
      add(timeToX(b, top.span.begin + offset), ay, timeToX(b, top.span.end + offset), by);
    } else add(ax, ay, Math.max(bx, (b.x ?? 0) + sizeOf(model, b).w), by);
  }
  if (!isFinite(x0)) {
    setState({message: ui("navigation.noteTargetHidden")});
    setTimeout(() => setState({message: ''}), 2500);
    fitBoards();
    return false;
  }
  fitRect(x0, y0, x1, y1);
  return true;
}

// 键盘跳转用：已经在画面里就不动镜头，出去了才平移（不改缩放）；左边留出贴住视口的名字列
// 镜头对准一层（左边目录树点层名）：这一行放在画面上三分之一处，画板左边（层名列）贴着画面左边；
// 缩放沿用现在的，只在这一行矮得看不清时放大到 22 像素高。层在折叠的层下面、或者被"只看"滤掉了，画布上没有这一行，返回 false
export function focusLayer(id: number): boolean {
  const s = getState(), model = modelOf(s), layer = model?.layer(id);
  const b = layer && model!.boardOf(s.boards, layer.root);
  const row = pane && [...pane.querySelectorAll<HTMLElement>('.lname')].find((el) => el.dataset.layers?.split(' ').includes(String(id)));
  if (!b || !row) return false;
  const r = row.getBoundingClientRect(), a = toFlow(r.left, r.top), c = toFlow(r.right, r.bottom);
  const z = Math.min(1, Math.max(viewport().zoom, 22 / Math.max(1, c.y - a.y)));
  setState({autoFit: false});
  setView(24 - a.x * z, paneRect().height / 3 - ((a.y + c.y) / 2) * z, z);
  return true;
}

function revealScreen(left: number, top: number, right: number, bottom: number) {
  const p = paneRect(), {x, y, zoom} = viewport(), m = 40, leftEdge = p.left + NAMES * zoom + m;
  let dx = 0, dy = 0;
  if (left < leftEdge || right - left > p.right - m - leftEdge) dx = leftEdge - left;
  else if (right > p.right - m) dx = p.right - m - right;
  if (top < p.top + m) dy = p.top + m - top;
  else if (bottom > p.bottom - m) dy = p.bottom - m - bottom;
  if (dx || dy) { setView(x + dx, y + dy, zoom); setState({autoFit: false}); }
}

export function revealObject(id: number) {
  const el = pane?.querySelector(`.obj[data-id="${id}"]`);
  if (!el) return;
  const r = el.getBoundingClientRect();
  revealScreen(r.left, r.top, r.right, r.bottom);
}

export function revealTime(b: Board, t: number) {
  const p = paneRect(), {x, zoom} = viewport(), sx = p.left + x + timeToX(b, t) * zoom;
  revealScreen(sx, p.top + p.height / 2, sx + 1, p.top + p.height / 2);
}

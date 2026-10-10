// 镜头：画布的平移、缩放由 React Flow 管；这里放"把镜头对准某处"的几种做法，面板和顶栏都从这里调
import type {ReactFlowInstance} from '@xyflow/react';
import {NAMES} from './model/model';
import {keyOf} from './model/model';
import {sizeOf} from './model/layoutOps';
import {params} from './params';
import {activeBoard, getState, modelOf, setState} from './store';
import type {Board} from './types';

let flow: ReactFlowInstance | null = null;
let pane: HTMLElement | null = null;

export const TRACKS_X = 1 + NAMES;   // 轨道区在画板里的横向起点（左边框 1 像素 + 名字列）

export function attachCamera(instance: ReactFlowInstance, element: HTMLElement) { flow = instance; pane = element; }
export const viewport = () => flow?.getViewport() ?? {x: 0, y: 0, zoom: 1};
export const toFlow = (clientX: number, clientY: number) => flow?.screenToFlowPosition({x: clientX, y: clientY}) ?? {x: clientX, y: clientY};
const paneRect = () => pane?.getBoundingClientRect() ?? new DOMRect(0, 0, getState().canvasW, getState().canvasH);

function setView(x: number, y: number, zoom: number) {
  flow?.setViewport({x, y, zoom: Math.min(4, Math.max(0.05, zoom))});
}

// 画板时间 → 画布上的横坐标（世界坐标）
export function timeToX(b: Board, t: number) {
  const model = modelOf(getState())!;
  return (b.x ?? 0) + TRACKS_X + (t - model.extent(b)[0]) * model.pps(b);
}
export function xToTime(b: Board, worldX: number) {
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

// 页面刚打开：按地址参数对准（截图工具就是这样指定拍哪里的）
export function focusInitial() {
  const s = getState(), b = activeBoard(s);
  if (b && params.has('begin') && params.has('end')) focusRange(keyOf(b), Number(params.get('begin')), Number(params.get('end')));
  else if (b && params.has('board')) fitBoards([keyOf(b)]);
  else fitBoards();
  if (params.has('focus')) requestAnimationFrame(() => focusObject(Number(params.get('focus'))));
}

// 镜头移到某个对象（或删除前的虚线框）上，放在画面左上三分之一处
export function focusObject(id: number, ghost = false): boolean {
  const find = () => pane?.querySelector<HTMLElement>(ghost ? `.ghost[data-ghost="${id}"]` : `.obj[data-id="${id}"]`) ?? null;
  const node = find();
  if (!node) { setState({message: '这个对象现在不在画布上：可能在折叠的层里，或者被只显示部分层过滤掉了'}); setTimeout(() => setState({message: ''}), 2500); return false; }
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
  const nb: Board = {...b, pps: factor == null ? null : Math.max(1e-6, old * factor)};
  delete nb.tempPps;
  setState({boards: s.boards.map((x) => (x === b ? nb : x)), autoFit: false});
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

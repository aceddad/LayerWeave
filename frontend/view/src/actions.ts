// 用户在画面上做的事：点选、放播放头、折叠（存进数据库）、拆出、点层名、跳到批注指的地方、切换面板、键盘跳转、复制链接
import {focusNote, focusObject, focusTime, revealObject, revealTime, visibleRange} from './camera';
import {sizeOf, split} from './model/layoutOps';
import {linkQuery} from './model/link';
import {keyOf} from './model/model';
import {editPoints, stepObject, stepTime, stepTrack} from './model/navigate';
import {jumpPoints} from './plugin/registry';
import {activeBoard, getState, modelOf, setState} from './store';
import {api} from './api';
import {foldAction, loadChanges, loadWalk, report, saveLayout, selectionInfo, toast} from './sync';
import type {Ref, Side, View, WalkDirection} from './types';

// 点画板：放播放头；点在色块上就选中它；点在尺子上只放播放头并取消圈出的一段
export function clickBoard(key: number, t: number, objectId: number | null, onRuler: boolean) {
  const s = getState();
  setState({
    active: key, playhead: +t.toFixed(3),
    selected: objectId ?? (onRuler ? s.selected : null),
    sel: onRuler ? null : s.sel, wholeProject: false, targetLayer: null, noteFocus: null,
  });
  report();
}

// 折叠 / 展开自己这边的一条轨道（它合起来的每一个层）：收起它和下面所有的层。存进数据库，AI 看得见；下面的画板跟着挪
export async function toggleFold(layers: number[], fold: boolean) {
  if (await foldAction(layers, fold ? 'fold' : 'unfold')) report();
}
// 展开 AI 折叠的层（让 AI 也看回来）
export async function unfoldForAI(layers: number[]) {
  if (await foldAction(layers, 'unfold', 'ai')) report();
}
export const setFoldTips = (layers: number[], tips: string) => foldAction(layers, 'tips', 'user', tips);

export function splitRoot(rootId: number) {
  const s = getState();
  setState({boards: split(s.boards, rootId, modelOf(s)!)});
  saveLayout();
  report();
}

// 点层名：把这个层设为批注目标（再点一次取消）
export function pickLayer(layerId: number) {
  const s = getState(), picked = s.targetLayer === layerId ? null : layerId;
  setState({targetLayer: picked, sel: picked != null ? null : s.sel, wholeProject: false});
}

export function selectObject(id: number, fly = true) {
  const s = getState(), model = modelOf(s), o = model?.object(id);
  if (!model || !o) return toast('目标已删除');
  setState({selected: id, active: o.layer.root, playhead: +(o.begin + model.offsetOf(s.boards, o.layer.root!)).toFixed(6), view: 'canvas'});
  if (fly) requestAnimationFrame(() => requestAnimationFrame(() => focusObject(id)));
  report();
}

// 镜头移到批注指的地方：对象就选中它；层上的一段就圈出那一段
export function goToTarget(ref: Ref, span: {begin: number; end: number} | null) {
  const s = getState(), model = modelOf(s);
  if (!model) return;
  if (ref.project !== s.project) return toast('这条批注指向别的项目');
  if (ref.kind === 'object') return selectObject(ref.id);
  const layer = model.layer(ref.id), b = layer && model.boardOf(s.boards, layer.root);
  if (!b || !sizeOf(model, b).h) return toast('目标已删除，或者在收起的层里');
  const offset = model.offsetOf(s.boards, layer!.root!);
  const begin = span ? span.begin + offset : model.extent(b)[0];
  setState({view: 'canvas', active: keyOf(b), sel: span ? {key: keyOf(b), begin, end: span.end + offset} : s.sel, playhead: span ? begin : s.playhead});
  requestAnimationFrame(() => focusTime(b, begin));
  report();
}

export async function setSide(side: Side) {
  setState({side});
  await Promise.all([loadChanges(), loadWalk()]);
}

// 沿读：从一个对象或层（"object:16"、"layer:5"）出发，侧栏切到「沿读」。方向、步数沿用上一次的
export function startWalk(from: string, change: {direction?: WalkDirection; depth?: number} = {}) {
  const s = getState();
  setState({walk: {from, direction: change.direction ?? s.walk?.direction ?? 'both', depth: change.depth ?? s.walk?.depth ?? 3}, side: 'walk',
            walkResult: s.walk?.from === from ? s.walkResult : null});
  loadWalk();
}

export function setView(view: View) {
  setState({view});
  report();
}

// 批注上的"定位"：镜头对准这一楼指的全部地方，楼和目标高亮
export function locateNote(id: number) {
  setState({view: 'canvas'});
  requestAnimationFrame(() => { focusNote(id); report(); });
}

// 键盘：←/→ 同一轨道的前后对象（没选中对象时在剪辑点之间跳），↑/↓ 上下轨道，[ ] 接缝。返回 true 表示处理了
export function keyStep(key: string): boolean {
  const s = getState(), model = modelOf(s), b = activeBoard(s);
  if (!model || !b || s.view !== 'canvas') return false;
  const sel = s.selected != null ? model.object(s.selected) : undefined;
  const onBoard = sel && model.boardOf(s.boards, sel.layer.root) === b;
  const dir = key === 'ArrowLeft' || key === 'ArrowUp' || key === '[' ? -1 : 1;
  const moveTo = (t: number | null) => {
    if (t == null) return toast(dir < 0 ? '前面没有了' : '后面没有了');
    setState({playhead: +t.toFixed(6), noteFocus: null});
    revealTime(b, t);
    report();
  };
  const pick = (item: ReturnType<typeof stepObject>, keepPlayhead: boolean) => {
    if (!item) return toast(dir < 0 ? '前面没有了' : '后面没有了');
    const t = s.playhead, inside = keepPlayhead && t != null && item.begin <= t && t < item.end;
    setState({selected: item.o.id, playhead: inside ? t : +item.begin.toFixed(6), noteFocus: null});
    requestAnimationFrame(() => requestAnimationFrame(() => revealObject(item.o.id)));
    report();
  };
  // [ ]：插件给的跳转点（接缝插件给接缝的时刻）；没有插件给就不跳
  if (key === '[' || key === ']') {
    if (!s.plugins.some((p) => p.jumpPoints)) { toast('[ ] 的跳转点由插件提供（比如接缝插件），现在没有装'); return true; }
    moveTo(stepTime(jumpPoints(model, b), s.playhead ?? -Infinity, dir));
    return true;
  }
  if (key === 'ArrowLeft' || key === 'ArrowRight') {
    if (onBoard) pick(stepObject(model, b, sel!.id, dir), false);
    else moveTo(stepTime(editPoints(model, b), s.playhead ?? -Infinity, dir));
    return true;
  }
  if ((key === 'ArrowUp' || key === 'ArrowDown') && onBoard) {
    const offset = model.offsetOf(s.boards, sel!.layer.root!);
    pick(stepTrack(model, b, sel!.id, s.playhead ?? sel!.begin + offset, dir), true);
    return true;
  }
  return false;
}

// 此刻面板的"复制文字版"：圈出了一段就读那一段，否则读播放头（每一行各一刻），和 AI 用的 view_at 同一份文字
export async function copyMoment() {
  const s = getState(), model = modelOf(s), b = activeBoard(s);
  if (!model || !b || s.project == null) return;
  const sel = selectionInfo();
  const spans = sel ? [`${sel.root}:${sel.begin}:${sel.end}`]
    : s.playhead == null ? [] : b.rows.map((row) => model.segmentAt(row, s.playhead!)).filter(Boolean)
      .map((seg) => { const t = +(s.playhead! - seg!.offset).toFixed(6); return `${seg!.root}:${t}:${t}`; });
  if (!spans.length) return toast('先在画板上点一下，放好播放头');
  try {
    const {text} = await api.at(s.project, spans);
    if (await writeClipboard(text)) toast('已复制这一刻的文字版：每层是什么、怎么连着、哪些批注指着它们。贴给 AI 就行');
    else { setState({message: text}); setTimeout(() => setState({message: ''}), 15000); }
  } catch (error) { toast('读不到这一刻：' + (error as Error).message); }
}

// 复制链接：现在看的位置（画板、看得见的范围、播放头、选中的对象、对准的批注）。贴给 AI，它用 view_screenshot --link 拍同一个画面
export async function copyLink() {
  const s = getState(), act = activeBoard(s);
  if (s.project == null) return;
  const query = linkQuery({project: s.project, view: s.view, side: s.side, board: act ? keyOf(act) : null,
                           range: s.view === 'canvas' && act ? visibleRange(act) : null, playhead: s.playhead, select: s.selected,
                           layers: s.only, note: s.noteFocus, changes: s.changeLimit, walk: s.walk});
  const url = `${location.origin}${location.pathname}?${query}`;
  if (await writeClipboard(url)) return toast('已复制链接。贴给 AI，它用 view_screenshot --link 就能拍到这个画面');
  setState({message: '浏览器不让复制，请手动复制：' + url});
  setTimeout(() => setState({message: ''}), 10000);
}

export async function writeClipboard(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true; } catch { /* 有的内嵌浏览器不给剪贴板接口，换老办法 */ }
  const box = document.createElement('textarea');
  box.value = text;
  box.style.cssText = 'position:fixed;opacity:0';
  document.body.appendChild(box);
  box.select();
  try { return document.execCommand('copy'); } catch { return false; } finally { box.remove(); }
}

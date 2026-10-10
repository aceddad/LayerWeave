// 用户在画面上做的事：点选、放播放头、折叠、拆出、点层名、跳到批注指的地方、切换面板
import {focusObject, focusTime} from './camera';
import {afterResize, sizeOf, split} from './model/layoutOps';
import {keyOf} from './model/model';
import {getState, modelOf, setState} from './store';
import {loadChanges, report, saveLayout, toast} from './sync';
import type {Ref, Side, View} from './types';

// 点画板：放播放头；点在色块上就选中它；点在尺子上只放播放头并取消圈出的一段
export function clickBoard(key: number, t: number, objectId: number | null, onRuler: boolean) {
  const s = getState();
  setState({
    active: key, playhead: +t.toFixed(3),
    selected: objectId ?? (onRuler ? s.selected : null),
    sel: onRuler ? null : s.sel, wholeProject: false, targetLayer: null,
  });
  report();
}

export function toggleCollapse(key: number, collapseKey: string) {
  const s = getState(), model = modelOf(s)!;
  const board = s.boards.find((b) => keyOf(b) === key)!;
  const oldH = sizeOf(model, board).h;
  const collapsed = new Set(s.collapsed);
  collapsed.has(collapseKey) ? collapsed.delete(collapseKey) : collapsed.add(collapseKey);
  setState({collapsed});
  const after = getState();
  setState({boards: afterResize(after.boards, key, oldH, modelOf(after)!)});
  saveLayout();
  report();
}

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
  await loadChanges();
}

export function setView(view: View) {
  setState({view});
  report();
}

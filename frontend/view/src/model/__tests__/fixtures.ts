// 测试用的小项目：手写，期望值都能心算出来
import type {Bind, Layer, Obj, ProjectData, Ref, Root} from '../../types';
import {Model} from '../model';
import type {ViewOptions} from '../model';

export function obj(id: number, begin: number, end: number, extra: Partial<Obj> = {}): Obj {
  return {id, name: `o${id}`, type: 'image', begin, end, tips: '', text: null,
          media: {kind: 'image', source: `${id}.png`, available: true, url: `/media/1/${id}`}, information: {}, ...extra};
}

export function layer(id: number, name: string, root: number, father: number | null, objects: Obj[] = [], extra: Partial<Layer> = {}): Layer {
  return {id, name, type: 'image', father, depth: null, root, axis: null, tips: '', objects, role: null, hidden: false, ...extra};
}

export function root(id: number, name: string, extent: [number, number], unit = '秒'): Root {
  return {id, name, axis: {unit}, unit, key: unit ? (unit === 's' ? '秒' : unit) : null, extent};
}

export const ref = (kind: Ref['kind'], id: number, project = 1): Ref => ({kind, project, id});
export const bind = (id: number, source: Ref, target: Ref, tips = ''): Bind => ({id, source, target, tips});

export function data(roots: Root[], layers: Layer[], binds: Bind[] = []): ProjectData {
  return {project: {id: 1, name: '测试', tips: ''}, roots, layers, binds};
}

// 画布宽 1290：自动缩放时 (1290 - 200 - 90) = 1000 像素铺满一块画板
export function model(d: ProjectData, opts: Partial<ViewOptions> = {}): Model {
  return new Model(d, {only: null, showHidden: false, canvasWidth: 1290, ...opts});
}

// 用户这边折叠这些层（数据库里视图的表 view_layer 读出来就是这个样子）；aiFolded：AI 那边
export const folded = (d: ProjectData, ...layers: number[]): ProjectData =>
  ({...d, folds: layers.map((layer) => ({layer, user: '用户', user_tips: '太乱', ai: '', ai_tips: ''}))});
export const aiFolded = (d: ProjectData, ...layers: number[]): ProjectData =>
  ({...d, folds: layers.map((layer) => ({layer, user: '', user_tips: '', ai: 'Claude', ai_tips: '先对字幕'}))});

// 两章接续用的项目：第一章 [0, 10] 有「画面」「字幕」，第二章 [0, 5] 有「字幕」，配乐 [0, 20] 单独一个根
export function chapters() {
  return data(
    [root(1, '第一章', [0, 10]), root(10, '第二章', [0, 5]), root(20, '配乐', [0, 20])],
    [
      layer(1, '第一章', 1, null),
      layer(2, '画面', 1, 1, [obj(3, 0, 4), obj(4, 4, 8), obj(5, 9, 10)]),
      layer(6, '字幕', 1, 1, [obj(7, 1, 3, {type: 'text', media: null, text: '你好'})]),
      layer(10, '第二章', 10, null),
      layer(11, '字幕', 10, 10, [obj(12, 0, 2, {type: 'text', media: null, text: '再见'})]),
      layer(13, '画面', 10, 10, [obj(14, 0, 5)]),
      layer(20, '配乐', 20, null),
      layer(21, '音乐', 20, 20, [obj(22, 0, 20, {type: 'audio', media: {kind: 'audio', source: 'a.wav', available: true, url: '/media/1/22'}})]),
    ],
  );
}

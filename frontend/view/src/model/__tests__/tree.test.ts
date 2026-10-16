// 左边目录树：层按 根 → 层 → 子层 排、数对象、谁折叠的、几楼批注没处理；勾选连同子树
import {describe, expect, it} from 'vitest';
import {Model} from '../model';
import {noteList, noteThreads} from '../notes';
import {layerTree, subtree, togglePick} from '../tree';
import type {Layer, Obj, ProjectData} from '../../types';

const obj = (id: number, patch: Partial<Obj> = {}): Obj => ({id, name: `o${id}`, type: 'Text', begin: 0, end: 1, tips: '', text: null, media: null, information: {}, ...patch});
const layer = (id: number, father: number | null, root: number, objects: Obj[] = [], patch: Partial<Layer> = {}): Layer =>
  ({id, name: `L${id}`, type: 'text', father, depth: null, root, axis: null, tips: '', objects, role: null, hidden: false, ...patch});

function project(): ProjectData {
  return {
    project: {id: 1, name: 'p', tips: ''},
    roots: [{id: 1, name: '成片', axis: {}, unit: '秒', key: null, extent: [0, 10]},
            {id: 9, name: '批注', axis: {}, unit: '秒', key: null, extent: [0, 10]},
            {id: 5, name: '分镜', axis: {}, unit: '秒', key: null, extent: [0, 10]}],
    layers: [
      layer(9, null, 9, [obj(90, {text: '看这里', information: {status: 'open'}})], {role: 'note'}),
      layer(1, null, 1),
      layer(2, 1, 1, [obj(20), obj(21)]),
      layer(3, 2, 1, [obj(30)]),
      layer(4, 1, 1, [obj(40)]),
      layer(5, null, 5, [obj(50)]),
    ],
    binds: [{id: 1, tips: '', source: {kind: 'object', project: 1, id: 90}, target: {kind: 'object', project: 1, id: 30}}],
    folds: [{layer: 2, user: '用户', user_tips: '先收起', ai: '', ai_tips: ''}, {layer: 4, user: '', user_tips: '', ai: 'Claude', ai_tips: ''}],
  };
}
const model = () => new Model(project(), {viewer: 'user', only: null, showHidden: false, canvasWidth: 1200});

describe('目录树', () => {
  it('根按项目次序、批注层最后；子层挂在父层下面，深度跟着走', () => {
    const tree = layerTree(model());
    expect(tree.top).toEqual([1, 5, 9]);
    expect(tree.nodes.get(1)!.children).toEqual([2, 4]);
    expect(tree.nodes.get(2)!.children).toEqual([3]);
    expect([1, 2, 3].map((id) => tree.nodes.get(id)!.depth)).toEqual([0, 1, 2]);
  });

  it('对象数：自己的和连同下面的；折叠分自己这边和对方', () => {
    const tree = layerTree(model());
    expect([tree.nodes.get(1)!.own, tree.nodes.get(1)!.total]).toEqual([0, 4]);
    expect([tree.nodes.get(2)!.own, tree.nodes.get(2)!.total]).toEqual([2, 3]);
    expect(tree.nodes.get(2)!.mine?.by).toBe('用户');
    expect(tree.nodes.get(4)!.theirs?.by).toBe('Claude');
    expect(tree.nodes.get(4)!.mine).toBeNull();
  });

  it('没处理的批注：指着对象的算到对象所在的层，也算到上面每一层', () => {
    const m = model(), threads = noteThreads(noteList(m));
    const tree = layerTree(m, threads);
    expect([3, 2, 1, 4, 5].map((id) => tree.nodes.get(id)!.notes)).toEqual([1, 1, 1, 0, 0]);
    const done = threads.map((t) => ({...t, top: {...t.top, status: 'done' as const}}));
    expect(layerTree(m, done).nodes.get(1)!.notes).toBe(0);
  });

  it('勾一层连同子树；取消也是', () => {
    const tree = layerTree(model());
    expect(subtree(tree, 2).sort()).toEqual([2, 3]);
    const on = togglePick([5], tree, 1, true);
    expect(on).toEqual([1, 2, 3, 4, 5]);
    expect(togglePick(on, tree, 2, false)).toEqual([1, 4, 5]);
  });
});

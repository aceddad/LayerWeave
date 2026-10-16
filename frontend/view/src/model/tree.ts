// 左边的目录树：项目的层按 根 → 层 → 子层 排好，每层数对象、看谁折叠的、有几楼批注没处理。纯计算，按画面模型和批注缓存
import type {FoldMark, Model} from './model';
import type {Thread} from './notes';
import type {Layer} from '../types';

export interface TreeNode {
  layer: Layer;
  depth: number;
  children: number[];
  own: number;            // 这一层自己的对象数
  total: number;          // 连同下面所有层
  notes: number;          // 指着这一层、它的对象或下面的层的楼（没处理的），按楼主数
  mine: FoldMark | null;  // 自己这边折叠的
  theirs: FoldMark | null;
}
export interface Tree { nodes: Map<number, TreeNode>; top: number[] }

// 批注层放最后；其余按根在项目里的次序，子层按库里的次序
export function layerTree(model: Model, threads: Thread[] = []): Tree {
  const layers = model.data.layers, nodes = new Map<number, TreeNode>(), byLayer = new Map<number, Set<number>>();
  const mark = (layer: number | undefined, top: number) => {
    if (layer == null) return;
    if (!byLayer.has(layer)) byLayer.set(layer, new Set());
    byLayer.get(layer)!.add(top);
  };
  for (const {top} of threads) {
    if (top.status !== 'open') continue;
    for (const t of top.targets) {
      if (t.project !== model.project) continue;
      mark(t.kind === 'layer' ? t.id : model.object(t.id)?.layer.id, top.id);
    }
  }
  for (const l of layers) nodes.set(l.id, {layer: l, depth: 0, children: [], own: l.objects.length, total: 0, notes: 0,
                                           mine: model.own.get(l.id) ?? null, theirs: model.other.get(l.id) ?? null});
  const top: number[] = [];
  for (const l of layers) {
    const parent = l.father != null ? nodes.get(l.father) : undefined;
    if (parent && l.id !== l.root) parent.children.push(l.id);
    else top.push(l.id);
  }
  const order = new Map(model.data.roots.map((r, i) => [r.id, i]));
  const rank = (id: number) => (nodes.get(id)!.layer.role === 'note' ? 1e9 : 0) + (order.get(id) ?? 1e6);
  top.sort((a, b) => rank(a) - rank(b));
  const visit = (id: number, depth: number): Set<number> => {
    const node = nodes.get(id)!, seen = new Set(byLayer.get(id) ?? []);
    node.depth = depth; node.total = node.own;
    for (const child of node.children) {
      for (const t of visit(child, depth + 1)) seen.add(t);
      node.total += nodes.get(child)!.total;
    }
    node.notes = seen.size;
    return seen;
  };
  for (const id of top) visit(id, 0);
  return {nodes, top};
}

// 这一层连同下面所有层的编号（勾选一层就勾上它整棵子树）
export function subtree(tree: Tree, id: number): number[] {
  const out: number[] = [], stack = [id];
  while (stack.length) {
    const next = stack.pop()!, node = tree.nodes.get(next);
    if (!node) continue;
    out.push(next);
    stack.push(...node.children);
  }
  return out;
}

// 勾 / 取消一层：整棵子树跟着；返回新的勾选（按编号排好，方便比较和写进链接）
export function togglePick(picked: number[], tree: Tree, id: number, on: boolean): number[] {
  const ids = new Set(subtree(tree, id)), next = new Set(picked);
  for (const x of ids) { if (on) next.add(x); else next.delete(x); }
  return [...next].sort((a, b) => a - b);
}

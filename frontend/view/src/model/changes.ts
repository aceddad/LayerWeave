// 改动：最近几次操作改了哪些对象、层；删除或移动的对象，留下"之前在哪儿"的虚线框
import type {ChangeOp, ChangeRecord} from '../types';
import type {Model} from './model';

export interface Mark { n: number; action: 'create' | 'update' | 'delete' }
export interface Ghost { id: number; action: 'move' | 'delete'; begin: number; end: number; label: string }
export interface ChangeMarks { changed: Map<number, Mark>; changedLayers: Map<number, Mark>; ghosts: Map<number, Ghost[]> }

export const noMarks: ChangeMarks = {changed: new Map(), changedLayers: new Map(), ghosts: new Map()};

export function changeMarks(ops: ChangeOp[], model: Model): ChangeMarks {
  const changed = new Map<number, Mark>(), changedLayers = new Map<number, Mark>(), before = new Map<number, ChangeRecord>();
  ops.forEach((op, i) => {
    for (const it of op.items) {
      if (it.kind === 'object') {
        if (it.action !== 'delete' && !changed.has(it.id)) changed.set(it.id, {n: i + 1, action: it.action});
        const moved = it.action === 'update' && it.before && it.after && (['layer', 'begin', 'end'] as const).some((f) => it.before![f] !== it.after![f]);
        if ((it.action === 'delete' || moved) && it.before) before.set(it.id, it.before);   // 从新往旧走，最后留下的是这几次操作之前的位置
      } else if (it.kind === 'layer' && !changedLayers.has(it.id)) changedLayers.set(it.id, {n: i + 1, action: it.action});
    }
  });
  const ghosts = new Map<number, Ghost[]>();
  for (const [id, was] of before) {
    const now = model.object(id);
    if (was.layer == null || !model.layer(was.layer)) continue;
    if (now && now.layer.id === was.layer && now.begin === was.begin && now.end === was.end) continue;
    const ghost: Ghost = {id, action: now ? 'move' : 'delete', begin: was.begin ?? 0, end: was.end ?? 0,
                          label: was.name || was.text || (was.source || '').split(/[\\/]/).pop() || ''};
    if (!ghosts.has(was.layer)) ghosts.set(was.layer, []);
    ghosts.get(was.layer)!.push(ghost);
  }
  return {changed, changedLayers, ghosts};
}

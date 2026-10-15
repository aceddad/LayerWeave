// 应用完整操作页，未变化层/对象保持引用；根范围从受影响根重新计算（删除极值也正确）。
import type {Obj, ProjectData, ViewChange} from '../types';

export function applyChanges(data: ProjectData, changes: ViewChange[]): ProjectData {
  let layers = data.layers, binds = data.binds, folds = data.folds, noteReads = data.noteReads, project = data.project;
  const affectedRoots = new Set<number>();
  const layerById = new Map(layers.map((l) => [l.id, l]));
  const objectsByLayer = new Map<number, Map<number, Obj>>();
  const objectsOf = (id: number | null) => {
    const layer = id == null ? null : layerById.get(id);
    if (!layer) return null;
    if (!objectsByLayer.has(layer.id)) objectsByLayer.set(layer.id, new Map(layer.objects.map((o) => [o.id, o])));
    return objectsByLayer.get(layer.id)!;
  };
  for (const c of changes) {
    if (c.kind === 'object') {
      objectsOf(c.before_layer)?.delete(c.id);
      if (c.after) objectsOf(c.after_layer)?.set(c.id, c.after);
    } else if (c.kind === 'bind') {
      binds = [...binds.filter((b) => b.id !== c.id), ...(c.after ? [c.after] : [])].sort((a, b) => a.id - b.id);
    } else if (c.kind === 'view_layer') {
      folds = [...(folds ?? []).filter((f) => f.layer !== c.id), ...(c.after ? [c.after] : [])].sort((a, b) => a.layer - b.layer);
    } else if (c.kind === 'view_note') {
      noteReads = {...noteReads};
      if (c.after) noteReads[String(c.id)] = c.after;
      else delete noteReads[String(c.id)];
    } else project = c.after;
  }
  if (objectsByLayer.size) layers = layers.map((layer) => {
    const changed = objectsByLayer.get(layer.id);
    if (!changed) return layer;
    if (layer.root != null) affectedRoots.add(layer.root);
    return {...layer, objects: [...changed.values()].sort((a, b) => a.begin - b.begin || a.end - b.end || a.id - b.id)};
  });
  const roots = data.roots.map((root) => {
    if (!affectedRoots.has(root.id)) return root;
    let begin = Infinity, end = -Infinity;
    for (const l of layers) if (l.root === root.id) for (const o of l.objects) {
      if (typeof o.begin === 'number' && typeof o.end === 'number') { begin = Math.min(begin, o.begin); end = Math.max(end, o.end); }
    }
    const b = Number.isFinite(begin) ? begin : 0, e = Number.isFinite(end) && end > b ? end : b + 10;
    return b === root.extent[0] && e === root.extent[1] ? root : {...root, extent: [b, e] as [number, number]};
  });
  if (!changes.length) return data;
  return {project, layers, binds, folds, noteReads, roots: roots.every((r, i) => r === data.roots[i]) ? data.roots : roots};
}

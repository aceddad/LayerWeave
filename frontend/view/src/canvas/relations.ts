// 端点属于布局/关系拓扑；画板的 x/y 改变由 React Flow 移动线，不重新扫描对象。
import {MarkerType} from '@xyflow/react';
import type {BoardLayout, Model} from '../model/model';
import type {Board, Bind} from '../types';
import type {RelationEdgeType} from './RelationEdge';
import {keyOf} from '../model/model';

type End = {node: string; source: string; target: string};
type Layout = {node: string; layout: BoardLayout};
const EMPTY: RelationEdgeType[] = [];

export function createRelationReader() {
  let previous: {project: number; binds: Bind[]; layouts: Layout[]; links: boolean; selected: number | null; edges: RelationEdgeType[]} | null = null;
  let ends: Map<string, End> | null = null;
  let endLayouts: Layout[] = [];
  const sameLayouts = (a: Layout[], b: Layout[]) => a.length === b.length && a.every((p, i) => p.node === b[i].node && p.layout === b[i].layout);

  return (model: Model | null, boards: Board[], links: boolean, selected: number | null): RelationEdgeType[] => {
    if (!model || (!links && selected == null)) return EMPTY;
    const mine = (r: Bind['source']) => r.kind === 'object' && r.project === model.project && r.id === selected;
    const relevant = model.data.binds.filter((b) => b.source.project === model.project && b.target.project === model.project
      && (links || (selected != null && (mine(b.source) || mine(b.target)))));
    if (!relevant.length) return EMPTY;
    const layouts = boards.flatMap((b) => {
      if (b.x == null || b.y == null) return [];
      const layout = model.boardLayout(b);
      return layout ? [{node: 'b' + keyOf(b), layout}] : [];
    });
    if (previous && previous.project === model.project && previous.binds === model.data.binds && previous.links === links
      && previous.selected === selected && sameLayouts(previous.layouts, layouts)) return previous.edges;
    if (!ends || !sameLayouts(endLayouts, layouts)) {
      ends = new Map();
      for (const {node, layout} of layouts) for (const section of layout.sections) for (const track of section.tracks) {
        for (const part of track.track.parts) ends.set('layer:' + part.layer.id, {node, source: 'ls' + part.layer.id, target: 'lt' + part.layer.id});
        for (const {o} of track.items) ends.set('object:' + o.id, {node, source: 'o' + o.id, target: 't' + o.id});
      }
      endLayouts = layouts;
    }
    const edges = relevant.flatMap((bind): RelationEdgeType[] => {
      const source = ends!.get(bind.source.kind + ':' + bind.source.id), target = ends!.get(bind.target.kind + ':' + bind.target.id);
      if (!source || !target) return [];
      const hot = selected != null && (mine(bind.source) || mine(bind.target));
      return [{id: 'r' + bind.id, type: 'relation', source: source.node, sourceHandle: source.source,
        target: target.node, targetHandle: target.target, zIndex: 1000,
        markerEnd: {type: MarkerType.ArrowClosed, width: 14, height: 14, color: hot ? '#4fb3ff' : '#6fa8d8'},
        data: {hot, tips: bind.tips, title: ''}}];
    });
    previous = {project: model.project, binds: model.data.binds, layouts, links, selected, edges};
    return edges;
  };
}

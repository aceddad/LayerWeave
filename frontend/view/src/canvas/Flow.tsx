// 画布：React Flow 负责平移、缩放、拖动节点、画连线、小地图；每块画板是一个节点，每条关联是一条连线
import {Background, BackgroundVariant, MarkerType, MiniMap, Panel, ReactFlow, applyNodeChanges, useNodesInitialized} from '@xyflow/react';
import type {Edge, NodeChange, ReactFlowInstance} from '@xyflow/react';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {attachCamera, focusInitial, settleZoom, viewport} from '../camera';
import {markReady} from '../capture';
import {merge, sizeOf, snap} from '../model/layoutOps';
import {keyOf} from '../model/model';
import type {Model} from '../model/model';
import {CAPTURE, SOLO} from '../params';
import {activeBoard, getState, modelOf, setState, useModel, useStore} from '../store';
import {report, saveLayout} from '../sync';
import type {Board} from '../types';
import {BoardNode} from './BoardNode';
import type {BoardNodeType} from './BoardNode';
import {dropTarget} from './drop';
import {RelationEdge} from './RelationEdge';
import type {RelationEdgeType} from './RelationEdge';

const nodeTypes = {board: BoardNode};
const edgeTypes = {relation: RelationEdge};
const nodeId = (b: Board) => `b${keyOf(b)}`;

function shownBoards(model: Model, boards: Board[]): Board[] {
  const solo = SOLO ? activeBoard(getState()) : undefined;
  return boards.filter((b) => b.x != null && b.y != null && model.boardLayout(b) && (!solo || b === solo));
}

// 关联的两头都在画面上时才画；平时只画选中对象的，勾上"关系线"画全部
function relationEdges(model: Model | null, boards: Board[], links: boolean, selected: number | null): RelationEdgeType[] {
  if (!model) return [];
  const ends = new Map<string, {node: string; source: string; target: string}>();
  for (const b of shownBoards(model, boards)) {
    const node = nodeId(b);
    for (const sec of model.boardLayout(b)!.sections) for (const t of sec.tracks) {
      for (const p of t.track.parts) ends.set(`layer:${p.layer.id}`, {node, source: `ls${p.layer.id}`, target: `lt${p.layer.id}`});
      for (const it of t.items) ends.set(`object:${it.o.id}`, {node, source: `o${it.o.id}`, target: `t${it.o.id}`});
    }
  }
  const mine = (r: {kind: string; project: number; id: number}) => r.kind === 'object' && r.project === model.project && r.id === selected;
  return model.data.binds.flatMap((b) => {
    const hot = selected != null && (mine(b.source) || mine(b.target));
    if (!links && !hot) return [];
    if (b.source.project !== model.project || b.target.project !== model.project) return [];
    const s = ends.get(`${b.source.kind}:${b.source.id}`), t = ends.get(`${b.target.kind}:${b.target.id}`);
    if (!s || !t) return [];
    return [{id: `r${b.id}`, type: 'relation' as const, source: s.node, sourceHandle: s.source, target: t.node, targetHandle: t.target, zIndex: 1000,
             markerEnd: {type: MarkerType.ArrowClosed, width: 14, height: 14, color: hot ? '#4fb3ff' : '#6fa8d8'},
             data: {hot, tips: b.tips, title: ''}}];
  });
}

export function Flow() {
  const model = useModel();
  const {boards, links, selected} = useStore(useShallow((s) => ({boards: s.boards, links: s.links, selected: s.selected})));
  const paneRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes] = useState<BoardNodeType[]>([]);
  const [instance, setInstance] = useState<ReactFlowInstance | null>(null);

  const built = useMemo<BoardNodeType[]>(() => (model ? shownBoards(model, boards).map((b) => {
    const {w, h} = sizeOf(model, b);
    return {id: nodeId(b), type: 'board', position: {x: b.x!, y: b.y!}, data: {key: keyOf(b)}, dragHandle: '.bhead',
            draggable: !CAPTURE && keyOf(b) !== 0, selectable: false, width: w, height: h};
  }) : []), [model, boards]);
  // 节点由排版算出来；React Flow 量出来的尺寸（measured）按编号留着
  useEffect(() => setNodes((prev) => {
    const old = new Map(prev.map((n) => [n.id, n]));
    return built.map((n) => (old.has(n.id) ? {...old.get(n.id)!, ...n, measured: old.get(n.id)!.measured} : n));
  }), [built]);

  const edges = useMemo<Edge[]>(() => relationEdges(model, boards, links, selected), [model, boards, links, selected]);

  // 拖画板：位置吸附到别的画板边缘，并写回排版
  const onNodesChange = useCallback((changes: NodeChange<BoardNodeType>[]) => {
    const s = getState(), m = modelOf(s);
    const keyById = new Map(s.boards.map((b) => [nodeId(b), keyOf(b)]));
    const fixed = changes.map((c) => (c.type === 'position' && c.position && c.dragging && m
      ? {...c, position: snap(c.position, keyById.get(c.id)!, s.boards, m, viewport().zoom)} : c));
    setNodes((nds) => applyNodeChanges(fixed, nds));
    const moves = new Map(fixed.flatMap((c) => (c.type === 'position' && c.position ? [[c.id, c.position] as const] : [])));
    if (moves.size) setState({boards: s.boards.map((b) => (moves.has(nodeId(b)) ? {...b, x: moves.get(nodeId(b))!.x, y: moves.get(nodeId(b))!.y} : b))});
  }, []);

  const dragStart = useRef<{key: number; gap: {x: number; y: number; w: number; h: number}} | null>(null);
  const onNodeDragStart = useCallback((_: unknown, node: BoardNodeType) => {
    const s = getState(), b = s.boards.find((x) => nodeId(x) === node.id)!, {w, h} = sizeOf(modelOf(s)!, b);
    dragStart.current = {key: keyOf(b), gap: {x: b.x!, y: b.y!, w, h}};
    setState({dragging: true});
  }, []);
  const onNodeDrag = useCallback((event: MouseEvent | TouchEvent, node: BoardNodeType) => {
    const s = getState(), b = s.boards.find((x) => nodeId(x) === node.id);
    const point = 'touches' in event ? event.touches[0] : event;
    if (b && point) setState({drop: dropTarget(point.clientX, point.clientY, b, s.boards, modelOf(s)!)});
  }, []);
  const onNodeDragStop = useCallback(() => {
    const s = getState(), drop = s.drop, start = dragStart.current;
    setState({dragging: false, drop: null});
    if (drop?.ok && start) setState({boards: merge(s.boards, start.key, drop.targetKey, drop.root, drop.side, start.gap, modelOf(s)!)});
    saveLayout();
    report();
  }, []);

  // 画板都量好尺寸以后，按地址参数对准一次；截图页面等图都加载完再举手
  const initialized = useNodesInitialized();
  const focused = useRef(false);
  useEffect(() => {
    if (!instance || focused.current || !initialized || !nodes.length) return;
    focused.current = true;
    requestAnimationFrame(() => { focusInitial(); markReady(); });
  }, [instance, initialized, nodes.length]);

  // 画布尺寸变化：自动宽度的画板跟着变；用户还没动过镜头就重新铺满
  useEffect(() => {
    const el = paneRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      const w = el.clientWidth, h = el.clientHeight, s = getState();
      if (w < 50 || h < 50 || (Math.abs(w - s.canvasW) <= 1 && Math.abs(h - s.canvasH) <= 1)) return;
      setState({canvasW: w, canvasH: h});
      if (getState().autoFit && focused.current) requestAnimationFrame(() => focusInitial());
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="flow" ref={paneRef}>
      <ReactFlow<BoardNodeType, Edge>
        nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        onNodesChange={onNodesChange} onNodeDragStart={onNodeDragStart} onNodeDrag={onNodeDrag} onNodeDragStop={onNodeDragStop}
        onInit={(rf) => { attachCamera(rf as unknown as ReactFlowInstance, paneRef.current!); setInstance(rf as unknown as ReactFlowInstance); }}
        onMoveStart={(event) => { if (event) setState({autoFit: false}); }}
        onMoveEnd={() => { report(); settleZoom(); }}
        colorMode="dark" minZoom={0.05} maxZoom={4} defaultViewport={{x: 24, y: 24, zoom: 1}}
        nodesConnectable={false} elementsSelectable={false} nodesFocusable={false} edgesFocusable={false}
        nodesDraggable={!CAPTURE} zoomOnDoubleClick={false}>
        <Background variant={BackgroundVariant.Dots} gap={24} size={1.2} color="#2b3140" />
        {!CAPTURE && <MiniMap position="top-right" pannable zoomable nodeColor="#2a3346" nodeStrokeColor="#44536e" maskColor="rgba(10, 12, 16, .6)" />}
        {!CAPTURE && <Panel position="bottom-left" className="help">
          拖空白处平移（按住空格可在画板上拖）· 滚轮缩放 · Alt+滚轮：这块画板的时间 · 拖画板标题移动；拖到同单位画板的一行中间上下拼，拖到一段开头或结尾左右接 · 在尺子上拖：圈一段 · ←/→ 前后对象（没选中时跳剪辑点）· ↑/↓ 上下轨道 · [ ] 接缝
        </Panel>}
      </ReactFlow>
    </div>
  );
}

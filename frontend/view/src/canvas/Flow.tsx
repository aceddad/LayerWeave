// 画布：React Flow 负责平移、缩放、拖动节点、画连线、小地图；每块画板是一个节点，每条关联是一条连线
import {Background, BackgroundVariant, MiniMap, Panel, ReactFlow, applyNodeChanges, useNodesInitialized} from '@xyflow/react';
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
import {createRelationReader} from './relations';
import {dragPosition, moveBoard, sameDrop, setLivePosition} from './dragState';
import type {Point} from './dragState';

const nodeTypes = {board: BoardNode};
const edgeTypes = {relation: RelationEdge};
const nodeId = (b: Board) => `b${keyOf(b)}`;

function shownBoards(model: Model, boards: Board[]): Board[] {
  const solo = SOLO ? activeBoard(getState()) : undefined;
  return boards.filter((b) => b.x != null && b.y != null && model.boardLayout(b) && (!solo || b === solo));
}

export function Flow() {
  const model = useModel();
  const {boards, links, selected} = useStore(useShallow((s) => ({boards: s.boards, links: s.links, selected: s.selected})));
  const paneRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes] = useState<BoardNodeType[]>([]);
  const [instance, setInstance] = useState<ReactFlowInstance | null>(null);
  const readRelations = useRef(createRelationReader()).current;
  const drag = useRef<{project: number; key: number; id: string; position: Point | null;
    gap: {x: number; y: number; w: number; h: number}; origin: {left: number; top: number}} | null>(null);
  const suppressed = useRef(false);

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

  const edges = useMemo<Edge[]>(() => readRelations(model, model ? shownBoards(model, boards) : [], links, selected), [model, boards, links, selected]);

  // 高频位置只交给 React Flow；保持内容和布局引用，避免广播几千个对象的订阅。
  const onNodesChange = useCallback((changes: NodeChange<BoardNodeType>[]) => {
    const s = getState(), m = modelOf(s), current = drag.current;
    const fixed = changes.flatMap((change): NodeChange<BoardNodeType>[] => {
      if (change.type !== 'position' || !change.position) return [change];
      if (suppressed.current) return [];
      if (!current || change.id !== current.id || !m) return [change];
      const position = dragPosition(change.position, current.position, change.dragging === false,
        (p) => snap(p, current.key, s.boards, m, viewport().zoom));
      current.position = position;
      setLivePosition(current.key, position);
      return [{...change, position}];
    });
    if (fixed.length) setNodes((nds) => applyNodeChanges(fixed, nds));
  }, []);

  const finishDrag = useCallback((commit: boolean) => {
    const current = drag.current;
    if (!current) return;
    drag.current = null;
    setLivePosition(current.key, null);
    const s = getState(), m = modelOf(s);
    if (!commit || s.project !== current.project || !m) {
      suppressed.current = true;
      setState({dragging: false, drop: null});
      setNodes((nds) => nds.map((n) => n.id === current.id
        ? {...n, dragging: false, position: {x: current.gap.x, y: current.gap.y}} : n));
      return;
    }
    let next = current.position ? moveBoard(s.boards, current.key, current.position) : s.boards;
    if (s.drop?.ok) next = merge(next, current.key, s.drop.targetKey, s.drop.root, s.drop.side, current.gap, m);
    setState({boards: next, dragging: false, drop: null});
    saveLayout();
    report();
  }, []);

  const onNodeDragStart = useCallback((_: unknown, node: BoardNodeType) => {
    const s = getState(), b = s.boards.find((x) => nodeId(x) === node.id), m = modelOf(s);
    if (!b || !m || s.project == null) return;
    const {w, h} = sizeOf(m, b), r = paneRef.current!.getBoundingClientRect();
    suppressed.current = false;
    drag.current = {project: s.project, key: keyOf(b), id: node.id, position: null,
      gap: {x: b.x!, y: b.y!, w, h}, origin: {left: r.left, top: r.top}};
    setState({dragging: true});
  }, []);
  const onNodeDrag = useCallback((event: MouseEvent | TouchEvent, node: BoardNodeType) => {
    const current = drag.current, s = getState(), m = modelOf(s);
    if (!current || current.project !== s.project || !m) return;
    const b = s.boards.find((x) => nodeId(x) === node.id);
    const point = 'touches' in event ? event.touches[0] : event;
    if (b && point) {
      const drop = dropTarget(point.clientX, point.clientY, current.origin, b, s.boards, m);
      if (!sameDrop(s.drop, drop)) setState({drop});
    }
  }, []);
  const onNodeDragStop = useCallback((event: MouseEvent | TouchEvent) => {
    finishDrag(!event.type.endsWith('cancel'));
    suppressed.current = false;
  }, [finishDrag]);

  // 丢失指针/窗口焦点时取消；后续拖动事件不能重新把取消的位置写回。
  useEffect(() => {
    const cancel = () => finishDrag(false);
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape' && drag.current) cancel(); };
    window.addEventListener('blur', cancel);
    window.addEventListener('pointercancel', cancel);
    window.addEventListener('touchcancel', cancel);
    window.addEventListener('keydown', key);
    return () => {
      window.removeEventListener('blur', cancel);
      window.removeEventListener('pointercancel', cancel);
      window.removeEventListener('touchcancel', cancel);
      window.removeEventListener('keydown', key);
      const current = drag.current;
      if (current) { drag.current = null; setLivePosition(current.key, null); setState({dragging: false, drop: null}); }
    };
  }, [finishDrag]);
  useEffect(() => { if (drag.current && drag.current.project !== model?.project) finishDrag(false); }, [model?.project, finishDrag]);

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

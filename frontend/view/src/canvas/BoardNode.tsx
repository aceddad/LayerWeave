// 画板：React Flow 的一个自定义节点。里面是这块画板的时间轴：标题、尺子、一行行轨道，播放头、圈出的一段、拼接提示。
// 拖动只能抓标题（dragHandle = .bhead）；尺子上拖是圈一段；Alt+滚轮缩放这块画板的时间。
import {Handle, Position, useStore as useFlowStore, useUpdateNodeInternals} from '@xyflow/react';
import type {Node, NodeProps} from '@xyflow/react';
import {memo, useEffect, useLayoutEffect, useMemo, useRef} from 'react';
import type {RefObject} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {clickBoard, pickLayer, splitRoot, toggleCollapse} from '../actions';
import {timeZoom, toFlow, xToTime} from '../camera';
import {decimalsOf, fmtLength} from '../model/gaps';
import {externalLabels} from '../model/labels';
import type {BoardLayout, SectionLayout} from '../model/model';
import {LANE, NAMES, PAD, keyOf, rootsOf} from '../model/model';
import {fmt, ticks} from '../model/units';
import {activeBoard, setState, useMarks, useModel, useNotes, useStore} from '../store';
import {report} from '../sync';
import type {Board} from '../types';
import {ObjectBlock} from './ObjectBlock';

export type BoardNodeType = Node<{key: number}, 'board'>;

// 画板左边移出视口时，名字列、刻度角、标题跟着往右挪
function Sticky({target, x, width}: {target: RefObject<HTMLDivElement | null>; x: number; width: number}) {
  const stick = useFlowStore((s) => {
    const [tx, , z] = s.transform;
    return Math.round(Math.max(0, Math.min(-(tx + x * z) / z, width - NAMES - 60)));
  });
  useLayoutEffect(() => { target.current?.style.setProperty('--stick', `${stick}px`); }, [stick, target]);
  return null;
}

function Ruler({board, layout}: {board: Board; layout: BoardLayout}) {
  const bucket = useFlowStore((s) => Math.round(Math.log(s.transform[2]) * 5));   // 缩放变化够大才重排刻度
  const marks = useMemo(() => ticks(layout.a, layout.e, layout.pps, Math.exp(bucket / 5), layout.unit), [layout, bucket]);
  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    const el = e.currentTarget, x0 = e.clientX, key = keyOf(board);
    const t0 = xToTime(board, toFlow(e.clientX, e.clientY).x);
    let moved = false;
    try { el.setPointerCapture(e.pointerId); } catch { /* 拿不到指针时照样圈，只是拖出画板外会断 */ }
    const move = (ev: PointerEvent) => {
      if (!moved && Math.abs(ev.clientX - x0) < 4) return;
      moved = true;
      const t1 = xToTime(board, toFlow(ev.clientX, ev.clientY).x);
      setState({sel: {key, begin: +Math.min(t0, t1).toFixed(3), end: +Math.max(t0, t1).toFixed(3)}, wholeProject: false, targetLayer: null});
    };
    const up = () => {
      el.removeEventListener('pointermove', move);
      if (moved) report(); else clickBoard(key, t0, null, true);   // 只是点一下：放播放头，取消圈出的一段
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up, {once: true});
  };
  return (
    <div className="ruler nodrag nopan" style={{width: layout.tracksWidth}} onPointerDown={onPointerDown}>
      {marks.map((m) => <span key={m.t} className="tick" style={{left: m.x}}>{m.label}</span>)}
    </div>
  );
}

// 轨道里的空当：|— 3.000 —|，位数按轴的精度。屏幕上放得下数字才写数字，太窄只画两头的竖线，再窄就不画
function Gaps({gaps, a, pps, decimals, unit}: {gaps: {from: number; to: number}[]; a: number; pps: number; decimals: number | null; unit: string}) {
  const zoom = useFlowStore((s) => Math.exp(Math.round(Math.log(s.transform[2]) * 10) / 10));
  return <>{gaps.map(({from, to}) => {
    const w = (to - from) * pps, label = fmtLength(to - from, decimals), screen = w * zoom;
    if (screen < 6) return null;
    return <div key={from} className="gap" style={{left: (from - a) * pps, width: w}}
                title={`空着 ${label}${unit ? ' ' + unit : ''}（${fmt(from, unit)} – ${fmt(to, unit)}）`}>
      {screen >= label.length * 6.5 + 18 && <span>{label}</span>}
    </div>;
  })}</>;
}

function Section({board, layout, sec}: {board: Board; layout: BoardLayout; sec: SectionLayout}) {
  const model = useModel()!;
  const {selected, collapsed, targetLayer, frames, project, noteFocus} = useStore(useShallow((s) => ({
    selected: s.selected, collapsed: s.collapsed, targetLayer: s.targetLayer, frames: s.frames, project: s.project!, noteFocus: s.noteFocus,
  })));
  const marks = useMarks(), notes = useNotes();
  // 对准的那条批注指着的对象和层：高亮
  const focusTop = noteFocus != null ? notes?.threads.find((t) => t.top.id === noteFocus)?.top : undefined;
  const hot = useMemo(() => new Set((focusTop?.targets ?? []).filter((t) => t.project === project).map((t) => `${t.kind}:${t.id}`)), [focusTop, project]);
  // 层上的黄色带子：待处理的、指向一段时间的批注；对准的那条即使已处理也画出来
  const bandsOf = (layerId: number) => {
    const tops = (notes?.index.get(`layer:${layerId}`) ?? []).map((t) => t.top).filter((top) => top.span);
    if (focusTop?.span && !tops.includes(focusTop) && hot.has(`layer:${layerId}`)) tops.push(focusTop);
    return tops;
  };
  const external = useMemo(() => externalLabels(model), [model]);
  const key = keyOf(board), many = rootsOf(board).length > 1, {a, pps, unit} = layout;
  const decimals = decimalsOf(model.precisionOf(sec.row[0]));

  const onTracksClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.closest('.seg-chip')) return;
    const band = target.closest<HTMLElement>('.noteband');
    if (band) setState({side: 'notes'});
    const obj = target.closest<HTMLElement>('.obj');
    clickBoard(key, xToTime(board, toFlow(e.clientX, e.clientY).x), obj ? Number(obj.dataset.id) : null, false);
  };

  return (
    <div className="sec" data-row={sec.index}>
      <div className="names stick">
        {sec.strip && <div className="lname strip" style={{height: 24}}><span className="nm">左右接续 {sec.segments.length} 段</span></div>}
        {sec.tracks.map(({track, collapseKey, height}) => {
          const ids = track.parts.map((p) => p.layer.id), isRoot = track.key === '';
          const label = isRoot ? sec.row.map((r) => model.nameOf(r)).join(' → ') : (track.name || track.type);
          const said = ids.flatMap((id) => notes?.index.get(`layer:${id}`) ?? []);
          const changed = ids.map((id) => marks.changedLayers.get(id)).filter(Boolean);
          return (
            <div key={track.key} className={`lname${isRoot ? ' root' : ''}${targetLayer != null && ids.includes(targetLayer) ? ' picked' : ''}${ids.some((id) => hot.has(`layer:${id}`)) ? ' hot' : ''}`}
                 data-layers={ids.join(' ')} title={track.tips || label}
                 style={{height, paddingLeft: 8 + 14 * track.depth}}
                 onClick={(e) => { if (!(e.target as HTMLElement).closest('.tog, button')) pickLayer(ids[0]); }}>
              {track.hasChildren
                ? <span className="tog" onClick={() => toggleCollapse(key, collapseKey)}>{collapsed.has(collapseKey) ? '▸' : '▾'}</span>
                : <span className="tog" />}
              <span className="lt">{track.type}</span>
              <span className="nm">{label}</span>
              {said.length > 0 && <i className="note-dot" title={said.map(({top}) => `#${top.id} ${top.text}`).join('\n')}>💬{said.length}</i>}
              {changed.length > 0 && <i className="chg-dot" title="这个层最近被改过">{Math.min(...changed.map((m) => m!.n))}</i>}
              {isRoot && many && !sec.strip && <button className="split nodrag" title="把这个根拆出去，单独成一块画板" onClick={() => splitRoot(sec.row[0])}>拆出</button>}
              {ids.map((id) => <span key={id}>
                <Handle type="source" position={Position.Left} id={`ls${id}`} className="rel-handle" isConnectable={false} />
                <Handle type="target" position={Position.Left} id={`lt${id}`} className="rel-handle" isConnectable={false} />
              </span>)}
            </div>
          );
        })}
      </div>
      <div className="tracks" style={{width: layout.tracksWidth}} onClick={onTracksClick}>
        {sec.strip && <div className="segstrip" style={{height: 24}}>
          {sec.segments.map((s) => <span key={s.root} className="seg-chip" style={{left: (s.offset - a) * pps}}>
            ▶ {model.nameOf(s.root)}<small>{fmt(s.offset, unit)} 起</small>
            {many && <button className="split nodrag" title="把这一段拆出去，单独成一块画板" onClick={() => splitRoot(s.root)}>拆出</button>}
          </span>)}
        </div>}
        {sec.tracks.map(({track, height, items, gaps}) => (
          <div key={track.key} className="track" style={{height}}>
            <Gaps gaps={gaps} a={a} pps={pps} decimals={decimals} unit={unit} />
            {items.map((it) => <ObjectBlock key={it.o.id} item={it} a={a} pps={pps} unit={unit} project={project} frames={frames}
              selected={it.o.id === selected} hot={hot.has(`object:${it.o.id}`)} mark={marks.changed.get(it.o.id)} notes={notes?.index.get(`object:${it.o.id}`)}
              external={external.get(it.o.id)} />)}
            {track.parts.flatMap(({layer, seg}) => (marks.ghosts.get(layer.id) ?? []).map((g) => (
              <div key={`g${g.id}`} className={`ghost ${g.action}`} data-ghost={g.id}
                   style={{left: (g.begin + seg.offset - a) * pps, width: Math.max(6, (g.end - g.begin) * pps), top: PAD, height: LANE - 4}}
                   title={`#${g.id} ${g.label}：${g.action === 'delete' ? '删除前' : '移动前'}在这里（${fmt(g.begin, unit)} – ${fmt(g.end, unit)}）`}>
                <span>{g.action === 'delete' ? '删除前' : '移动前'} #{g.id} {g.label}</span>
              </div>)))}
            {track.parts.flatMap(({layer, seg}) => bandsOf(layer.id).map((top) => (
              <div key={`n${top.id}`} className={`noteband${top.id === noteFocus ? ' hot' : ''}`} data-note={top.id} title={`批注 #${top.id}：${top.text}`}
                   style={{left: (top.span!.begin + seg.offset - a) * pps, width: Math.max(4, (top.span!.end - top.span!.begin) * pps)}}>
                <span>💬 {top.text}</span>
              </div>)))}
          </div>
        ))}
        {sec.segments.slice(1).map((s) => <div key={s.root} className="seam" style={{left: (s.offset - a) * pps}} />)}
      </div>
    </div>
  );
}

export const BoardNode = memo(function BoardNode({id, data, positionAbsoluteX}: NodeProps<BoardNodeType>) {
  const key = data.key;
  const model = useModel();
  const board = useStore((s) => s.boards.find((b) => keyOf(b) === key));
  const layout = useMemo(() => (model && board ? model.boardLayout(board) : null), [model, board]);
  const {isActive, playhead, sel, drop} = useStore(useShallow((s) => {
    const act = activeBoard(s);
    return {isActive: !!act && keyOf(act) === key, playhead: s.playhead, sel: s.sel, drop: s.drop};
  }));
  const rootRef = useRef<HTMLDivElement>(null);
  const updateNodeInternals = useUpdateNodeInternals();
  useEffect(() => { updateNodeInternals(id); }, [layout, id, updateNodeInternals]);   // 关系线的端点跟着对象走
  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {                  // Alt+滚轮：只缩放这块画板的时间，不缩放画布
      if (!e.altKey) return;
      e.preventDefault();
      e.stopPropagation();
      timeZoom(key, Math.exp(-e.deltaY * 0.002), e.clientX);
    };
    el.addEventListener('wheel', onWheel, {passive: false});
    return () => el.removeEventListener('wheel', onWheel);
  }, [key]);
  if (!layout || !board || !model) return null;
  const {a, pps, unit} = layout;
  const title = board.rows.map((row) => row.map((r) => model.nameOf(r)).join(' → ')).join(' ＋ ');
  const dropHere = drop && drop.targetKey === key ? drop : null;
  const dropSec = dropHere ? layout.sections.find((s) => s.index === dropHere.rowIndex) : undefined;
  return (
    <div ref={rootRef} className={`board${isActive ? ' active' : ''}${dropHere ? (dropHere.ok ? ' canmerge' : ' nomerge') : ''}`}
         data-key={key} style={{width: layout.width, height: layout.height}}>
      <Sticky target={rootRef} x={positionAbsoluteX} width={layout.width} />
      <div className="bhead">
        <div className="stick">
          <span className="grip">⠿</span><b>{title}</b><span className="unit">{unit || '没有单位'}</span>
          <button className="nodrag" title="时间缩小" onClick={() => timeZoom(key, 1 / 1.6)}>−</button>
          <button className="nodrag" title="时间恢复成铺满画布" onClick={() => timeZoom(key, null)}>适应</button>
          <button className="nodrag" title="时间放大" onClick={() => timeZoom(key, 1.6)}>＋</button>
        </div>
      </div>
      <div className="rrow"><div className="corner stick">{unit}</div><Ruler board={board} layout={layout} /></div>
      {layout.sections.map((sec) => <Section key={sec.index} board={board} layout={layout} sec={sec} />)}
      {isActive && playhead != null && <div className="playhead" style={{left: NAMES + (playhead - a) * pps}} />}
      {sel && sel.key === key && <div className="selband" style={{left: NAMES + (sel.begin - a) * pps, width: Math.max(2, (sel.end - sel.begin) * pps)}} />}
      {dropHere && !dropHere.ok && <div className="dropnote">{dropHere.reason}</div>}
      {dropHere && dropHere.ok && dropSec && (dropHere.side === 'left' || dropHere.side === 'right'
        ? <div className="dropmark v" style={{left: NAMES + (dropHere.at! - a) * pps, top: dropSec.top, height: dropSec.height}}>{dropHere.side === 'left' ? '接在这一段前面' : '接在这一段后面'}</div>
        : <div className="dropmark" style={{top: dropSec.top + (dropHere.side === 'below' ? dropSec.height : 0)}} />)}
    </div>
  );
});

import {tr, useI18n} from '../i18n';
// 画板：React Flow 的一个自定义节点。里面是这块画板的时间轴：标题、尺子、一行行轨道，播放头、圈出的一段、拼接提示。
// 拖动只能抓标题（dragHandle = .bhead）；尺子上拖是圈一段；Alt+滚轮缩放这块画板的时间。
import {Handle, Position, useStore as useFlowStore, useUpdateNodeInternals} from '@xyflow/react';
import type {Node, NodeProps} from '@xyflow/react';
import {memo, useEffect, useLayoutEffect, useMemo, useRef, useState} from 'react';
import type {RefObject} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {clickBoard, pickLayer, setFoldTips, splitRoot, toggleFold, unfoldForAI} from '../actions';
import {timeZoom, toFlow, xToTime} from '../camera';
import {decimalsOf, fmtLength} from '../model/gaps';
import {externalLabels} from '../model/labels';
import type {BoardLayout, FoldInfo, FoldMark, SectionLayout} from '../model/model';
import {RECORD, VIEWER} from '../params';
import {LANE, NAMES, PAD, keyOf, rootsOf} from '../model/model';
import {fmt, ticks} from '../model/units';
import {activeBoard, getState, handleKeysOf, hotOf, setState, useMarks, useModel, useNotes, useStore} from '../store';
import {report} from '../sync';
import type {Board} from '../types';
import {ObjectBlock} from './ObjectBlock';
import {MediaTrack} from './TrackMedia';

export type BoardNodeType = Node<{key: number}, 'board'>;

// 画板左边移出视口时，名字列、刻度角、标题跟着往右挪。
// 直接改这几个元素自己的 transform。原来是在画板根上设 CSS 变量 --stick，变量会往下继承，放大以后平移，
// 每一帧都要把整块画板两千多个元素的样式重算一遍（放大后平移卡顿的主因，2026-10-14 量的）
function Sticky({target, x, width, layout}: {target: RefObject<HTMLDivElement | null>; x: number; width: number; layout: BoardLayout}) {
  const stick = useFlowStore((s) => {
    const [tx, , z] = s.transform;
    return Math.round(Math.max(0, Math.min(-(tx + x * z) / z, width - NAMES - 60)));
  });
  useLayoutEffect(() => {
    target.current?.querySelectorAll<HTMLElement>('.stick').forEach((el) => { el.style.transform = stick ? `translateX(${stick}px)` : ''; });
  }, [stick, target, layout]);   // layout 变了（折叠、加层）会有新的名字列，也要挪
  return null;
}

function Ruler({board, layout}: {board: Board; layout: BoardLayout}) {
  useI18n();
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
  useI18n();
  const zoom = useFlowStore((s) => Math.exp(Math.round(Math.log(s.transform[2]) * 10) / 10));
  return <>{gaps.map(({from, to}) => {
    const w = (to - from) * pps, label = fmtLength(to - from, decimals), screen = w * zoom;
    if (screen < 6) return null;
    return <div key={from} className="gap" style={{left: (from - a) * pps, width: w}}
                title={tr("board.gap", {value1: label, value2: unit ? ' ' + unit : '', value3: fmt(from, unit), value4: fmt(to, unit)})}>
      {screen >= label.length * 6.5 + 18 && <span>{label}</span>}
    </div>;
  })}</>;
}

const otherRole = () => VIEWER === 'user' ? 'AI' : tr('common.user');           // 对方
const MINE = VIEWER === 'user';                           // 网页（人这边）才能改折叠

// 自己这边折叠的轨道：一条带边框的细条，写明收了什么、谁收的、为什么；网页上可以写备注、点一下展开
function FoldBar({fold, notes, layers}: {fold: FoldInfo; notes: number; layers: number[]}) {
  useI18n();
  const [draft, setDraft] = useState<string | null>(null);
  const save = async () => { if (draft != null && await setFoldTips(layers, draft)) setDraft(null); };
  return (
    <div className="foldbar" title={MINE ? tr("board.expandHint") : tr("board.foldedBy", {value1: fold.by})}
         onClick={(e) => { e.stopPropagation(); if (MINE && draft == null) toggleFold(layers, false); }}>

      {tr("board.foldedLabel")}{fold.below ? tr("board.descendants", {value1: fold.below}) : ''} · {fold.objects}  {tr("board.objectsSuffix")}{notes > 0 && tr("board.openNotes", {value1: notes})}
      <small>（{fold.by}  {tr("board.foldedSuffix")}{fold.tips && draft == null ? '：' + fold.tips : ''}）</small>
      {MINE && RECORD && (draft == null
        ? <a className="foldtips" onClick={(e) => { e.stopPropagation(); setDraft(fold.tips); }}>{fold.tips ? tr("board.editNote") : tr("board.writeNote")}</a>
        : <input className="foldtips-box nodrag" autoFocus value={draft} placeholder={tr("board.foldReason")}
                 onClick={(e) => e.stopPropagation()} onChange={(e) => setDraft(e.target.value)}
                 onKeyDown={(e) => { e.stopPropagation(); if (e.key === 'Enter') save(); if (e.key === 'Escape') setDraft(null); }} />)}
    </div>
  );
}

// 对方折叠的轨道：照常画，名字旁贴标签；网页上点 × 让 AI 也展开
function OtherChip({mark, layers}: {mark: FoldMark; layers: number[]}) {
  useI18n();
  const why = mark.tips ? '：' + mark.tips : '';
  const hint = MINE ? tr("board.expandAIHint") : tr("board.userNotFocused");
  return (
    <i className="otherfold-chip" title={tr("board.foldedTree", {value1: mark.by, value2: why, value3: hint})}>
      {otherRole()}{tr("common.collapsed")}{MINE && RECORD && <b onClick={(e) => { e.stopPropagation(); unfoldForAI(layers); }}>×</b>}
    </i>
  );
}

// 一行（一段或左右接续的几段）的轨道和对象。memo：拖画板时画板每一帧都重画（标题要跟着吸附），这一行的数据没变就不跟着重画，
// 否则 5000 个对象时每移一下都要把几千个格子重新比一遍，拖画板只剩每秒 1 帧（2026-10-14 量的）
// 选中的对象不在这里订阅：格子自己订阅（ObjectBlock），点一下对象这一行不用重画
const Section = memo(function Section({boardKey, layout, sec}: {boardKey: number; layout: BoardLayout; sec: SectionLayout}) {
  useI18n();
  const model = useModel()!;
  const {targetLayer, frames, project, noteFocus} = useStore(useShallow((s) => ({
    targetLayer: s.targetLayer, frames: s.frames, project: s.project!, noteFocus: s.noteFocus,
  })));
  const marks = useMarks(), notes = useNotes(), hot = useStore(hotOf);
  // 对准的那条批注：它指着的层名高亮、它圈的那一段画出来
  const focusTop = noteFocus != null ? notes?.threads.find((t) => t.top.id === noteFocus)?.top : undefined;
  // 层上的黄色带子：待处理的、指向一段时间的批注；对准的那条即使已处理也画出来
  const bandsOf = (layerId: number) => {
    const tops = (notes?.index.get(`layer:${layerId}`) ?? []).map((t) => t.top).filter((top) => top.span);
    if (focusTop?.span && !tops.includes(focusTop) && hot.has(`layer:${layerId}`)) tops.push(focusTop);
    return tops;
  };
  const {locale} = useI18n();
  const external = useMemo(() => externalLabels(model, tr), [model, locale]);
  // 折叠的轨道里收着几楼待处理的批注（指向收起的层或对象）：写在细条上，免得 AI 漏看
  const notesIn = (fold: FoldInfo) => {
    const tops = new Set<number>();
    for (const id of fold.layers) {
      for (const th of notes?.index.get(`layer:${id}`) ?? []) tops.add(th.top.id);
      for (const o of model.layer(id)?.objects ?? []) for (const th of notes?.index.get(`object:${o.id}`) ?? []) tops.add(th.top.id);
    }
    return tops.size;
  };
  const board = getState().boards.find((b) => keyOf(b) === boardKey);
  if (!board) return null;
  const key = boardKey, many = rootsOf(board).length > 1, {a, pps, unit} = layout;
  const decimals = decimalsOf(model.precisionOf(sec.row[0]));

  const onTracksClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.closest('.seg-chip')) return;
    const band = target.closest<HTMLElement>('.noteband');
    if (band) { setState({side: 'notes', noteFocus: Number(band.dataset.note)}); return; }
    const obj = target.closest<HTMLElement>('.obj');
    const current = getState().boards.find((b) => keyOf(b) === key);
    if (current) clickBoard(key, xToTime(current, toFlow(e.clientX, e.clientY).x), obj ? Number(obj.dataset.id) : null, false);
  };

  return (
    <div className="sec" data-row={sec.index}>
      <div className="names stick">
        {sec.strip && <div className="lname strip" style={{height: 24}}><span className="nm">{tr("board.sequentialCount", {count: sec.segments.length})}</span></div>}
        {sec.tracks.map(({track, height, fold, other}) => {
          const ids = track.parts.map((p) => p.layer.id), isRoot = track.key === '';
          const label = isRoot ? sec.row.map((r) => model.nameOf(r, tr)).join(' → ') : (track.name || track.type);
          const said = ids.flatMap((id) => notes?.index.get(`layer:${id}`) ?? []);
          const changed = ids.map((id) => marks.changedLayers.get(id)).filter(Boolean);
          return (
            <div key={track.key} className={`lname${isRoot ? ' root' : ''}${fold ? ' folded' : ''}${targetLayer != null && ids.includes(targetLayer) ? ' picked' : ''}${ids.some((id) => hot.has(`layer:${id}`)) ? ' hot' : ''}`}
                 data-layers={ids.join(' ')} title={track.tips || label}
                 style={{height, paddingLeft: 8 + 14 * track.depth}}
                 onClick={(e) => { if (!(e.target as HTMLElement).closest('.tog, button')) pickLayer(ids[0]); }}>
              <span className={`tog${MINE ? '' : ' off'}`}
                    title={MINE ? (fold ? tr("common.expand") : tr("board.collapseHint")) : tr("board.aiReadOnly")}
                    onClick={() => MINE && toggleFold(ids, !fold)}>{fold ? '▸' : '▾'}</span>
              <span className="lt">{track.type}</span>
              <span className="nm">{label}</span>
              {said.length > 0 && <i className="note-dot" title={said.map(({top}) => `#${top.id} ${top.text}`).join('\n')}>💬{said.length}</i>}
              {changed.length > 0 && <i className="chg-dot" title={tr("board.layerChanged")}>{Math.min(...changed.map((m) => m!.n))}</i>}
              {other && <OtherChip mark={other} layers={ids} />}
              {isRoot && many && !sec.strip && <button className="split nodrag" title={tr("board.detachRootHint")} onClick={() => splitRoot(sec.row[0])}>{tr("board.detach")}</button>}
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
            ▶ {model.nameOf(s.root, tr)}<small>{tr("board.startAt", {position: fmt(s.offset, unit)})}</small>
            {many && <button className="split nodrag" title={tr("board.detachSegmentHint")} onClick={() => splitRoot(s.root)}>{tr("board.detach")}</button>}
          </span>)}
        </div>}
        {sec.tracks.map(({track, height, items, gaps, fold, other}) => (fold
          ? <div key={track.key} className="track folded" style={{height}}>
              <FoldBar fold={fold} notes={notesIn(fold)} layers={track.parts.map((p) => p.layer.id)} />
            </div>
          : <MediaTrack key={track.key} className={`track${other ? ' otherfold' : ''}`} height={height} width={layout.tracksWidth}>
            {other && <span className="otherfold-label">{tr('board.otherCollapsed', {author: other.by, reason: other.tips ? ': ' + other.tips : ''})}</span>}
            <Gaps gaps={gaps} a={a} pps={pps} decimals={decimals} unit={unit} />
            {items.map((it) => <ObjectBlock key={it.o.id} item={it} a={a} pps={pps} unit={unit} project={project} frames={frames}
              mark={marks.changed.get(it.o.id)} notes={notes?.index.get(`object:${it.o.id}`)} external={external.get(it.o.id)} />)}
            {track.parts.flatMap(({layer, seg}) => (marks.ghosts.get(layer.id) ?? []).map((g) => (
              <div key={`g${g.id}`} className={`ghost ${g.action}`} data-ghost={g.id}
                   style={{left: (g.begin + seg.offset - a) * pps, width: Math.max(6, (g.end - g.begin) * pps), top: PAD, height: LANE - 4}}
                   title={tr("board.ghost", {value1: g.id, value2: g.label, value3: g.action === 'delete' ? tr("changes.beforeDelete") : tr("changes.beforeMove"), value4: fmt(g.begin, unit), value5: fmt(g.end, unit)})}>
                <span>{g.action === 'delete' ? tr("changes.beforeDelete") : tr("changes.beforeMove")} #{g.id} {g.label}</span>
              </div>)))}
            {track.parts.flatMap(({layer, seg}) => bandsOf(layer.id).map((top) => (
              <div key={`n${top.id}`} className={`noteband${top.id === noteFocus ? ' hot' : ''}`} data-note={top.id} title={tr("board.note", {value1: top.id, value2: top.text})}
                   style={{left: (top.span!.begin + seg.offset - a) * pps, width: Math.max(4, (top.span!.end - top.span!.begin) * pps)}}>
                <span>💬 {top.text}</span>
              </div>)))}
          </MediaTrack>
        ))}
        {sec.segments.slice(1).map((s) => <div key={s.root} className="seam" style={{left: (s.offset - a) * pps}} />)}
      </div>
    </div>
  );
});

export const BoardNode = memo(function BoardNode({id, data, positionAbsoluteX}: NodeProps<BoardNodeType>) {
  useI18n();
  const key = data.key;
  const model = useModel();
  const board = useStore((s) => s.boards.find((b) => keyOf(b) === key));
  const layout = useMemo(() => (model && board ? model.boardLayout(board) : null), [model, board]);
  // 只取和这块画板有关的：播放头、圈出的一段、拼接提示不在这块上时是 null，别的画板上点来点去这块不重画
  const {isActive, playhead, sel, drop} = useStore(useShallow((s) => {
    const act = activeBoard(s), isActive = !!act && keyOf(act) === key;
    return {isActive, playhead: isActive ? s.playhead : null, sel: s.sel && s.sel.key === key ? s.sel : null,
            drop: s.drop && s.drop.targetKey === key ? s.drop : null};
  }));
  const rootRef = useRef<HTMLDivElement>(null);
  const updateNodeInternals = useUpdateNodeInternals();
  // 这块画板上要挂连接点的对象（写成一串字）：变了才重新量端点。选了别的对象、开关关系线时，不相干的画板不用量
  const ids = useMemo(() => new Set(layout?.sections.flatMap((s) => s.tracks.flatMap((t) => t.items.map((it) => it.o.id))) ?? []), [layout]);
  const handles = useStore((s) => [...handleKeysOf(s)].filter((k) => k.startsWith('object:') && ids.has(Number(k.slice(7)))).sort().join(' '));
  useEffect(() => { updateNodeInternals(id); }, [layout, id, updateNodeInternals, handles]);   // 关系线的端点跟着对象走
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
  const folded = layout.sections.reduce((n, sec) => n + sec.tracks.filter((t) => t.fold).length, 0);
  const title = board.rows.map((row) => row.map((r) => model.nameOf(r, tr)).join(' → ')).join(' ＋ ');
  const dropHere = drop;
  const dropSec = dropHere ? layout.sections.find((s) => s.index === dropHere.rowIndex) : undefined;
  return (
    <div ref={rootRef} className={`board${isActive ? ' active' : ''}${dropHere ? (dropHere.ok ? ' canmerge' : ' nomerge') : ''}`}
         data-key={key} style={{width: layout.width, height: layout.height}}>
      <Sticky target={rootRef} x={positionAbsoluteX} width={layout.width} layout={layout} />
      <div className="bhead">
        <div className="stick">
          <span className="grip">⠿</span><b>{title}</b><span className="unit">{unit || tr("common.noUnit")}</span>
          {folded > 0 && <span className="foldchip" title={tr("board.foldedTracksHint")}>{tr("board.collapsedTracks", {count: folded})}</span>}
          <button className="nodrag" title={tr("board.timeZoomOut")} onClick={() => timeZoom(key, 1 / 1.6)}>−</button>
          <button className="nodrag" title={tr("board.fitTimeHint")} onClick={() => timeZoom(key, null)}>{tr("board.fitTime")}</button>
          <button className="nodrag" title={tr("board.timeZoomIn")} onClick={() => timeZoom(key, 1.6)}>＋</button>
        </div>
      </div>
      <div className="rrow"><div className="corner stick">{unit}</div><Ruler board={board} layout={layout} /></div>
      {layout.sections.map((sec) => <Section key={sec.index} boardKey={key} layout={layout} sec={sec} />)}
      {isActive && playhead != null && <div className="playhead" style={{left: NAMES + (playhead - a) * pps}} />}
      {sel && <div className="selband" style={{left: NAMES + (sel.begin - a) * pps, width: Math.max(2, (sel.end - sel.begin) * pps)}} />}
      {dropHere && !dropHere.ok && <div className="dropnote">{dropHere.reason}</div>}
      {dropHere && dropHere.ok && dropSec && (dropHere.side === 'left' || dropHere.side === 'right'
        ? <div className="dropmark v" style={{left: NAMES + (dropHere.at! - a) * pps, top: dropSec.top, height: dropSec.height}}>{dropHere.side === 'left' ? tr("board.joinBefore") : tr("board.joinAfter")}</div>
        : <div className="dropmark" style={{top: dropSec.top + (dropHere.side === 'below' ? dropSec.height : 0)}} />)}
    </div>
  );
});

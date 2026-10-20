import {NodeResizer} from '@xyflow/react';
import {useEffect, useRef} from 'react';
import type {Board} from '../types';
import type {BoardLayout, Model} from '../model/model';
import {MIN_LANE, NAMES, PAD, LANE, keyOf, rootsOf} from '../model/model';
import {heightFactor, rememberStyles, rootStyle, scaleRows, setRowHeight, setScale} from '../model/boardStyle';
import {afterResize} from '../model/layoutOps';
import {getState, setState} from '../store';
import {report, saveLayout} from '../sync';
import {RECORD} from '../params';
import {tr, useI18n} from '../i18n';

function dimensions(layout: BoardLayout) {
  const tracks = layout.sections.flatMap((s) => s.tracks).filter((t) => !t.fold);
  const variable = tracks.reduce((n, t) => n + t.height - 2 * PAD, 0);
  const lanes = tracks.reduce((n, t) => n + (t.height - 2 * PAD) / t.laneHeight, 0);
  return {variable, fixed: layout.height - variable, lanes,
    tracks: tracks.map((t) => ({laneHeight: t.laneHeight, count: (t.height - 2 * PAD) / t.laneHeight}))};
}

export function BoardSizing({board, layout, model, active}: {board: Board; layout: BoardLayout; model: Model; active: boolean}) {
  useI18n();
  const saved = useRef<{board: Board; layout: BoardLayout; project: number | null; size: {width: number; height: number}} | null>(null);
  const key = keyOf(board), d = dimensions(layout);
  useEffect(() => () => {
    if (saved.current) { saved.current = null; setState({dragging: false}); }
  }, []);
  if (!RECORD || key === 0) return null;
  return <NodeResizer isVisible={active} minWidth={NAMES + 100}
    minHeight={d.fixed + d.lanes * MIN_LANE}
    lineStyle={{borderColor: 'var(--accent)'}} handleStyle={{width: 9, height: 9, background: 'var(--accent)'}}
    onResizeStart={(_, size) => {
      saved.current = {board: rememberStyles(board), layout, project: getState().project, size};
      setState({dragging: true, active: key, autoFit: false});
    }}
    onResize={(_, size) => {
      const start = saved.current, s = getState();
      if (!start || start.project !== s.project) return;
      const origin = dimensions(start.layout);
      const dw = size.width - start.size.width, dh = size.height - start.size.height;
      const pps = Math.max(1e-6, (start.layout.width + dw - NAMES - 42) / (start.layout.e - start.layout.a));
      let next = Math.abs(dw) > 1e-6 ? setScale(start.board, pps) : rememberStyles(start.board);
      if (Math.abs(dh) > 1e-6) {
        const ratio = heightFactor(origin.tracks, Math.max(0, start.layout.height + dh - origin.fixed));
        next = scaleRows(next, ratio);
      }
      next.x = size.x; next.y = size.y;
      setState({boards: s.boards.map((b) => keyOf(b) === key ? next : b)});
    }}
    onResizeEnd={() => {
      const start = saved.current, s = getState();
      saved.current = null;
      if (!start || start.project !== s.project) { setState({dragging: false}); return; }
      setState({boards: afterResize(s.boards, key, start.layout.height, model), dragging: false});
      saveLayout(); report();
    }}
  />;
}

export function RowHeightControl({board, layout, model}: {board: Board; layout: BoardLayout; model: Model}) {
  useI18n();
  if (!RECORD || keyOf(board) === 0) return null;
  const height = rootStyle(board, rootsOf(board)[0]).lane_height ?? LANE;
  const choices = [40, 96, 180, 320];
  return <select className="nodrag nopan" aria-label={tr('board.rowHeight')} title={tr('board.rowHeightHint')}
    value={height} onChange={(e) => {
      const s = getState(), key = keyOf(board);
      const boards = s.boards.map((b) => keyOf(b) === key ? setRowHeight(b, Number(e.target.value)) : b);
      setState({boards: afterResize(boards, key, layout.height, model), autoFit: false});
      saveLayout(); report();
    }}>
    {!choices.includes(height) && <option value={height}>{tr('board.customRowHeight', {height: Math.round(height)})}</option>}
    {choices.map((h, i) => <option key={h} value={h}>{tr(['board.compactRows', 'board.normalRows', 'board.readingRows', 'board.imageRows'][i])}</option>)}
  </select>;
}

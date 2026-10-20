import type {Board, RootStyle} from '../types';
import defaults from '../../../../src/layerweave/tool/builtin/view/layout-defaults.json';

export const rootStyle = (b: Board, root: number): RootStyle =>
  b.styles?.[root] ?? {pps: b.pps, lane_height: null};

export function rememberStyles(board: Board): Board {
  const styles = Object.fromEntries(board.rows.flat().map((r) => [r, {...rootStyle(board, r)}]));
  if (board.rows[0]?.[0] != null) styles[board.rows[0][0]].pps = board.pps;
  return {...board, styles};
}

export function leaderStyle(board: Board): Board {
  return {...board, pps: board.styles?.[board.rows[0]?.[0]]?.pps ?? null};
}

export function setScale(board: Board, pps: number | null): Board {
  const b = rememberStyles(board);
  b.pps = pps;
  b.styles![b.rows[0][0]].pps = pps;
  delete b.tempPps;
  return b;
}

export function setRowHeight(board: Board, height: number): Board {
  const b = rememberStyles(board);
  for (const s of Object.values(b.styles!)) s.lane_height = Math.max(defaults.MIN_LANE, height);
  return b;
}

export function scaleRows(board: Board, factor: number): Board {
  const b = rememberStyles(board);
  for (const s of Object.values(b.styles!)) s.lane_height = Math.max(defaults.MIN_LANE, (s.lane_height ?? defaults.LANE) * factor);
  return b;
}

export function heightFactor(tracks: {laneHeight: number; count: number}[], available: number): number {
  const original = tracks.reduce((sum, t) => sum + t.laneHeight * t.count, 0);
  if (!original) return 1;
  let lo = 0, hi = Math.max(1, available / original);
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    const height = tracks.reduce((sum, t) => sum + t.count * Math.max(defaults.MIN_LANE, t.laneHeight * mid), 0);
    if (height < available) lo = mid; else hi = mid;
  }
  return (lo + hi) / 2;
}

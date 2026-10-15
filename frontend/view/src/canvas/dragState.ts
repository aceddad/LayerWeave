// 只保存拖动中的位置，不广播给内容订阅者；松手时才写回业务排版。
import type {Board} from '../types';
import type {Drop} from '../model/dropRule';
import {keyOf} from '../model/model';

export type Point = {x: number; y: number};
const positions = new Map<number, Point>();

export function liveBoard(board: Board): Board {
  const position = positions.get(keyOf(board));
  return position ? {...board, ...position} : board;
}

export function setLivePosition(key: number, position: Point | null) {
  if (position) positions.set(key, position);
  else positions.delete(key);
}

// React Flow 的结束回调可能带未吸附的原始位置，保留最后实际应用的位置。
export function dragPosition(requested: Point, previous: Point | null, ending: boolean,
                             constrain: (position: Point) => Point): Point {
  return ending && previous ? previous : constrain(requested);
}

export function moveBoard(boards: Board[], key: number, position: Point): Board[] {
  const board = boards.find((b) => keyOf(b) === key);
  if (!board || (board.x === position.x && board.y === position.y)) return boards;
  return boards.map((b) => b === board ? {...b, ...position} : b);
}

export function sameDrop(a: Drop | null, b: Drop | null): boolean {
  return a === b || !!(a && b && a.targetKey === b.targetKey && a.root === b.root && a.side === b.side
    && a.ok === b.ok && a.reason === b.reason && a.rowIndex === b.rowIndex && a.at === b.at);
}

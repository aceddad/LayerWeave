// 拖着画板经过另一块画板时，按鼠标位置决定怎么拼：
// 落在某一段的开头或结尾附近 → 左右接续；落在一行的中间 → 拼在这一行的上方或下方（同时）
import {toFlow, viewport, xToTime} from '../camera';
import {keyOf} from '../model/model';
import type {Model} from '../model/model';
import type {Drop} from '../store';
import type {Board} from '../types';

export function dropTarget(clientX: number, clientY: number, moving: Board, boards: Board[], model: Model): Drop | null {
  const movingNode = `b${keyOf(moving)}`;
  const hit = document.elementsFromPoint(clientX, clientY).find((el) => {
    const node = el.closest('.react-flow__node');
    return node && node.getAttribute('data-id') !== movingNode;
  }) as HTMLElement | undefined;
  const boardEl = hit?.closest<HTMLElement>('.board');
  if (!hit || !boardEl) return null;
  const target = boards.find((b) => keyOf(b) === Number(boardEl.dataset.key));
  if (!target || target === moving || keyOf(target) === 0) return null;
  const secs = [...boardEl.querySelectorAll<HTMLElement>('.sec')];
  if (!secs.length) return null;
  const sec = hit.closest<HTMLElement>('.sec') ?? (clientY < secs[0].getBoundingClientRect().top ? secs[0] : secs[secs.length - 1]);
  const rowIndex = Number(sec.dataset.row), row = target.rows[rowIndex], segs = model.segments(row);
  const t = xToTime(target, toFlow(clientX, clientY).x), pps = model.pps(target), zoom = viewport().zoom;
  const edge = (s: {begin: number; end: number}) => Math.max((s.end - s.begin) * 0.15, 36 / pps / zoom);   // 至少 36 屏幕像素宽的接续区
  let side: Drop['side'] | null = null, root = row[0], at: number | null = null;
  const first = segs[0], last = segs[segs.length - 1];
  if (hit.closest('.tracks')) {
    if (t < first.begin + edge(first)) { side = 'left'; root = first.root; at = first.offset; }
    else if (t > last.end - edge(last)) { side = 'right'; root = last.root; at = last.end; }
    else for (const s of segs.slice(0, -1)) if (Math.abs(t - s.end) < edge(s)) { side = 'right'; root = s.root; at = s.end; break; }
  }
  if (!side) { const r = sec.getBoundingClientRect(); side = clientY < r.top + r.height / 2 ? 'above' : 'below'; }
  const ka = model.root(keyOf(moving))?.key, kb = model.root(keyOf(target))?.key;
  const unitA = model.unitOfRoot(keyOf(moving)) || '没有单位', unitB = model.unitOfRoot(keyOf(target)) || '没有单位';
  let reason = '';
  if (ka == null || ka !== kb) reason = `单位不同（${unitA} / ${unitB}），不能拼在一起；松手只是摆在这里`;
  else if ((side === 'left' || side === 'right') && moving.rows.length > 1) reason = '这块画板有好几行，不知道接哪一行：先把要接的根拆出来再接；松手只是摆在这里';
  return {targetKey: keyOf(target), root, side, ok: !reason, reason, rowIndex, at};
}

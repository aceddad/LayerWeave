// 拖着画板经过另一块画板时：从页面上找出鼠标落在哪块画板、哪一行、哪个时刻，再交给 model/dropRule 决定怎么拼
import {toFlow, viewport, xToTime} from '../camera';
import {decideDrop} from '../model/dropRule';
import type {Drop} from '../model/dropRule';
import {keyOf} from '../model/model';
import type {Model} from '../model/model';
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
  const r = sec.getBoundingClientRect();
  return decideDrop(model, moving, target, Number(sec.dataset.row), xToTime(target, toFlow(clientX, clientY).x),
                    !!hit.closest('.tracks'), clientY < r.top + r.height / 2, viewport().zoom);
}

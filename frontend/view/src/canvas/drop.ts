import {tr} from '../i18n';
// 拖着画板经过另一块画板时：按排版数据算出鼠标落在哪块画板、哪一行、哪个时刻，再交给 model/dropRule 决定怎么拼。
// 原来用 elementsFromPoint 问页面，每移一下都逼浏览器把整页重新排版（拖画板时最耗时的一项，2026-10-14 量的）
import {viewport, xToTime} from '../camera';
import {decideDrop} from '../model/dropRule';
import type {Drop} from '../model/dropRule';
import {sizeOf} from '../model/layoutOps';
import {NAMES, keyOf} from '../model/model';
import type {Model} from '../model/model';
import type {Board} from '../types';

// origin：画布在页面上的左上角（开始拖时量一次）
export function dropTarget(clientX: number, clientY: number, origin: {left: number; top: number}, moving: Board, boards: Board[], model: Model): Drop | null {
  const vp = viewport(), px = (clientX - origin.left - vp.x) / vp.zoom, py = (clientY - origin.top - vp.y) / vp.zoom;
  let target: Board | undefined;
  for (const b of boards) {
    if (b === moving || keyOf(b) === keyOf(moving) || keyOf(b) === 0 || b.x == null || b.y == null) continue;
    const {w, h} = sizeOf(model, b);
    if (h && px >= b.x && px <= b.x + w && py >= b.y && py <= b.y + h) target = b;   // 叠在一起时取后画的（在上面的）
  }
  const layout = target && model.boardLayout(target);
  if (!target || !layout?.sections.length) return null;
  const x = px - target.x! - 1, y = py - target.y! - 1, secs = layout.sections;   // 减去画板 1px 的边框：排版里的位置从边框里面算起
  const sec = secs.find((s) => y >= s.top && y < s.top + s.height) ?? (y < secs[0].top ? secs[0] : secs[secs.length - 1]);
  // 名字列在画板左边移出画面时跟着往右挪（BoardNode 的 Sticky），挪到哪儿就挡住哪儿的轨道
  const stick = Math.max(0, Math.min(-(vp.x + target.x! * vp.zoom) / vp.zoom, layout.width - NAMES - 60));
  const onTracks = y >= sec.top && y < sec.top + sec.height && x >= NAMES && !(x >= stick && x < stick + NAMES);
  return decideDrop(model, moving, target, sec.index, xToTime(target, px), onTracks, y < sec.top + sec.height / 2, vp.zoom, tr);
}

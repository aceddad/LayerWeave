import {tr, useI18n} from '../i18n';
// 轨道上的一个对象：色块 + 缩略图 / 视频首尾帧 / 波形 / 文字，角上是改动、批注、跨项目关系的标记。
// 缩得很小时只画色块：格子在屏幕上只有十几像素高时，几百张缩略图每一帧都要重画，平移画布只剩每秒 11 帧（藏掉图片是 33 帧，2026-10-14 量的）。
// 截图时照旧全画，AI 截全图也看得到缩略图
import {Handle, Position} from '@xyflow/react';
import {memo, useMemo, useRef} from 'react';
import {CAPTURE} from '../params';
import {handleKeysOf, hotOf, useStore} from '../store';
import {kindOf, lastAt} from '../model/kinds';
import type {Mark} from '../model/changes';
import type {Item} from '../model/model';
import {LANE, PAD} from '../model/model';
import type {Thread} from '../model/notes';
import {fmt, isSec} from '../model/units';
import {BlockFrame, BlockThumb} from './Media';
import {Waveform} from './Waveform';
import {SHARED_MEDIA, useSharedMedia} from './TrackMedia';
import type {MediaSpec} from './TrackMedia';
import {detailAt} from './mediaQueue';
import {mediaUrl} from './mediaUrl';

interface Props {
  item: Item; a: number; pps: number; unit: string; project: number; frames: boolean;
  mark?: Mark; notes?: Thread[]; external?: string[];
}

// 选中、高亮、挂不挂连接点：每个格子自己订阅自己那一位。原来由整行传下来，点一下对象，所有轨道连同几百个格子都要重新过一遍
// （手书 800 个对象：点选一次 250–420 毫秒，2026-10-14 量的）
export const ObjectBlock = memo(function ObjectBlock({item, a, pps, unit, project, frames, mark, notes, external}: Props) {
  useI18n();
  const o = item.o, k = kindOf(o), instant = o.end <= o.begin;
  const laneHeight = item.laneHeight ?? LANE;
  const selected = useStore((s) => s.selected === o.id);
  const hot = useStore((s) => hotOf(s).has(`object:${o.id}`));
  const handles = useStore((s) => handleKeysOf(s).has(`object:${o.id}`));   // 这一刻有关系线连到它：才挂连接点
  const left = (item.begin - a) * pps, w = Math.max(instant ? 8 : 3, (o.end - o.begin) * pps);
  const missing = !!o.media && !o.media.available;
  // 画得多细：按镜头停下来时格子在屏幕上的高度分三档（缩放过程中不换，停下来才一起换）。0 只画色块，1 用 160 宽的缩略图，2 用 320 宽的
  const ref = useRef<HTMLDivElement>(null);
  const shared = SHARED_MEDIA && !missing && !!(o.media?.url && (k === 'image' || k === 'audio' || (k === 'video' && frames)));
  const detail = useLegacyDetail(w, laneHeight - 4, !shared);
  const media = useMemo<MediaSpec | null>(() => shared ? {
    o, layer: item.layer, kind: k, project, frames, unit,
    rect: {x: left, y: PAD + item.lane * laneHeight, w, h: laneHeight - 4}, last: lastAt(o, isSec(unit)),
  } : null, [shared, o, item.layer, item.lane, laneHeight, k, project, frames, unit, left, w]);
  useSharedMedia(media, ref);
  let inner = null;
  if (shared) {
    // 媒体交给轨道表面；对象本身和所有交互仍在这里。
  } else if (!missing && o.media?.url && (detail > 0 || k === 'audio')) {
    if (k === 'image') inner = <BlockThumb project={project} o={o} width={detail === 1 ? 160 : 320} frames={frames} />;
    else if (k === 'video') inner = frames && w >= 150
      ? <span className="ends"><BlockFrame project={project} o={o} at={0.05} frames /><BlockFrame project={project} o={o} at={lastAt(o, isSec(unit))} frames /></span>
      : <BlockFrame project={project} o={o} at={0.1} frames={frames} />;
    else if (k === 'audio') inner = <Waveform url={mediaUrl(o.media.url, o.media.source)} />;
  }
  const board = item.offset ? tr("object.boardSpan", {value1: fmt(item.begin, unit), value2: fmt(item.end, unit)}) : '';
  const title = tr("object.summary", {value1: o.id, value2: o.name || '', value3: o.type, value4: fmt(o.begin, unit), value5: fmt(o.end, unit), value6: board, value7: missing ? tr("media.missingLine") + o.media!.source : ''});
  const classes = ['obj', k, laneHeight >= 80 && 'expanded', instant && 'instant', missing && 'missing', selected && 'sel', hot && 'hot', mark && `chg chg-${mark.action}`].filter(Boolean).join(' ');
  return (
    <div ref={ref} className={classes} data-id={o.id} title={title}
         style={{left, width: w, top: PAD + item.lane * laneHeight, height: laneHeight - 4}}>
      {inner}
      <span className="lab">{k === 'text' && laneHeight >= 80 && o.name && <strong className="obj-title">{o.name}</strong>}{o.text ?? o.name ?? o.type}</span>
      {mark && <i className="chg-n" title={tr("object.changed", {value1: mark.n === 1 ? tr("changes.latest") : tr("changes.nthLatest", {value1: mark.n}), value2: mark.action === 'create' ? tr("changes.created") : tr("changes.updated")})}>{mark.n}</i>}
      {notes && notes.length > 0 && <i className="note-n" title={notes.map(({top, replies}) => tr("object.noteSummary", {value1: top.id, value2: top.text, value3: replies.length ? tr("notes.repliesParen", {value1: replies.length}) : ''})).join('\n')}>💬{notes.length}</i>}
      {external && external.length > 0 && <i className="ext" title={external.join('\n')}>↗ {external.length}</i>}
      {handles && <Handle type="source" position={Position.Right} id={`o${o.id}`} className="rel-handle" isConnectable={false} />}
      {handles && <Handle type="target" position={Position.Left} id={`t${o.id}`} className="rel-handle" isConnectable={false} />}
    </div>
  );
});

function useLegacyDetail(width: number, height: number, needed: boolean) {
  // 共享模式的选择结果固定，不因缩放触发 React 重渲染；原生视频仍沿用原来的档位。
  return useStore((s) => needed ? detailAt(s.settledZoom, width, height, CAPTURE) : 2);
}

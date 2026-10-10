// 轨道上的一个对象：色块 + 缩略图 / 视频首尾帧 / 波形 / 文字，角上是改动、批注、跨项目关系的标记
import {Handle, Position} from '@xyflow/react';
import {memo} from 'react';
import {kindOf, lastAt} from '../model/kinds';
import type {Mark} from '../model/changes';
import type {Item} from '../model/model';
import {LANE, PAD} from '../model/model';
import type {Thread} from '../model/notes';
import {fmt, isSec} from '../model/units';
import {Frame, Img} from './Media';
import {Waveform} from './Waveform';

interface Props {
  item: Item; a: number; pps: number; unit: string; project: number; frames: boolean;
  selected: boolean; hot?: boolean; mark?: Mark; notes?: Thread[]; external?: string[];
}

export const ObjectBlock = memo(function ObjectBlock({item, a, pps, unit, project, frames, selected, hot, mark, notes, external}: Props) {
  const o = item.o, k = kindOf(o), instant = o.end <= o.begin;
  const left = (item.begin - a) * pps, w = Math.max(instant ? 8 : 3, (o.end - o.begin) * pps);
  const missing = !!o.media && !o.media.available;
  let inner = null;
  if (!missing && o.media?.url) {
    if (k === 'image') inner = <Img src={o.media.url} />;
    else if (k === 'video') inner = frames && w >= 150
      ? <span className="ends"><Frame project={project} o={o} at={0.05} frames /><Frame project={project} o={o} at={lastAt(o, isSec(unit))} frames /></span>
      : <Frame project={project} o={o} at={0.1} frames={frames} />;
    else if (k === 'audio') inner = <Waveform url={o.media.url} />;
  }
  const board = item.offset ? `（画板上 ${fmt(item.begin, unit)} – ${fmt(item.end, unit)}）` : '';
  const title = `#${o.id} ${o.name || ''}（${o.type}）\n${fmt(o.begin, unit)} – ${fmt(o.end, unit)}${board}${missing ? '\n文件不存在：' + o.media!.source : ''}`;
  const classes = ['obj', k, instant && 'instant', missing && 'missing', selected && 'sel', hot && 'hot', mark && `chg chg-${mark.action}`].filter(Boolean).join(' ');
  return (
    <div className={classes} data-id={o.id} title={title}
         style={{left, width: w, top: PAD + item.lane * LANE, height: LANE - 4}}>
      {inner}
      <span className="lab">{o.text ?? o.name ?? o.type}</span>
      {mark && <i className="chg-n" title={`${mark.n === 1 ? '最近一次' : `倒数第 ${mark.n} 次`}操作${mark.action === 'create' ? '新建' : '修改'}`}>{mark.n}</i>}
      {notes && notes.length > 0 && <i className="note-n" title={notes.map(({top, replies}) => `#${top.id} ${top.text}${replies.length ? `（${replies.length} 条回复）` : ''}`).join('\n')}>💬{notes.length}</i>}
      {external && external.length > 0 && <i className="ext" title={external.join('\n')}>↗ {external.length}</i>}
      <Handle type="source" position={Position.Right} id={`o${o.id}`} className="rel-handle" isConnectable={false} />
      <Handle type="target" position={Position.Left} id={`t${o.id}`} className="rel-handle" isConnectable={false} />
    </div>
  );
});

// 轨道上的一个对象：色块 + 缩略图 / 视频首尾帧 / 波形 / 文字，角上是改动、批注、跨项目关系的标记。
// 缩得很小时只画色块：格子在屏幕上只有十几像素高时，几百张缩略图每一帧都要重画，平移画布只剩每秒 11 帧（藏掉图片是 33 帧，2026-10-14 量的）。
// 截图时照旧全画，AI 截全图也看得到缩略图
import {Handle, Position} from '@xyflow/react';
import {memo} from 'react';
import {CAPTURE} from '../params';
import {handleKeysOf, hotOf, useStore} from '../store';
import {kindOf, lastAt} from '../model/kinds';
import type {Mark} from '../model/changes';
import type {Item} from '../model/model';
import {LANE, PAD} from '../model/model';
import type {Thread} from '../model/notes';
import {fmt, isSec} from '../model/units';
import {Frame, Thumb} from './Media';
import {Waveform} from './Waveform';

interface Props {
  item: Item; a: number; pps: number; unit: string; project: number; frames: boolean;
  mark?: Mark; notes?: Thread[]; external?: string[];
}

// 选中、高亮、挂不挂连接点：每个格子自己订阅自己那一位。原来由整行传下来，点一下对象，所有轨道连同几百个格子都要重新过一遍
// （手书 800 个对象：点选一次 250–420 毫秒，2026-10-14 量的）
export const ObjectBlock = memo(function ObjectBlock({item, a, pps, unit, project, frames, mark, notes, external}: Props) {
  const o = item.o, k = kindOf(o), instant = o.end <= o.begin;
  const selected = useStore((s) => s.selected === o.id);
  const hot = useStore((s) => hotOf(s).has(`object:${o.id}`));
  const handles = useStore((s) => handleKeysOf(s).has(`object:${o.id}`));   // 这一刻有关系线连到它：才挂连接点
  const left = (item.begin - a) * pps, w = Math.max(instant ? 8 : 3, (o.end - o.begin) * pps);
  const missing = !!o.media && !o.media.available;
  // 画得多细：按镜头停下来时格子在屏幕上的高度分三档（缩放过程中不换，停下来才一起换）。0 只画色块，1 用 160 宽的缩略图，2 用 320 宽的
  const detail = useStore((s) => {
    if (CAPTURE) return 2;
    const h = (LANE - 4) * s.settledZoom;
    return h < 16 || w * s.settledZoom < 6 ? 0 : h < 60 ? 1 : 2;
  });
  let inner = null;
  if (!missing && o.media?.url && (detail > 0 || k === 'audio')) {
    if (k === 'image') inner = <Thumb project={project} o={o} width={detail === 1 ? 160 : 320} frames={frames} />;
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
      {handles && <Handle type="source" position={Position.Right} id={`o${o.id}`} className="rel-handle" isConnectable={false} />}
      {handles && <Handle type="target" position={Position.Left} id={`t${o.id}`} className="rel-handle" isConnectable={false} />}
    </div>
  );
});

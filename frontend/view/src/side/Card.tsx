// 对象卡片：此刻面板、选中对象的详情都用它；选中对象的详情里有插件给的段落（objectDetail）
import {createElement} from 'react';
import {frameUrl} from '../api';
import {goToTarget, selectObject, startWalk} from '../actions';
import {Img, Thumb} from '../canvas/Media';
import {WaveMark, Waveform} from '../canvas/Waveform';
import {kindOf} from '../model/kinds';
import {refLabel, relationsOf} from '../model/labels';
import type {ObjWithLayer} from '../model/model';
import {fmt, isSec} from '../model/units';
import {CAPTURE} from '../params';
import {useShallow} from 'zustand/react/shallow';
import {PluginBoundary} from '../plugin/slots';
import {activeBoard, setState, useModel, useNotes, useStore} from '../store';

export function Card({o, full = false, local = null}: {o: ObjWithLayer; full?: boolean; local?: number | null}) {
  const model = useModel()!;
  const notes = useNotes();
  const {project, frames, selected, playhead, onActive, offset, plugins} = useStore(useShallow((s) => {
    const act = activeBoard(s);
    return {project: s.project!, frames: s.frames, selected: s.selected, playhead: s.playhead, plugins: s.plugins,
            onActive: !!act && act.rows.flat().includes(o.layer.root!), offset: model.offsetOf(s.boards, o.layer.root!)};
  }));
  const unit = model.unitOfRoot(o.layer.root);
  const here = local ?? (playhead != null && onActive ? playhead - offset : null);
  const onClip = here != null && isSec(unit), at = onClip ? Math.max(0, here! - o.begin) : 0;
  const k = kindOf(o), missing = !!o.media && !o.media.available;
  let body = null;
  if (missing) body = <p className="hint">文件不存在：{o.media!.source}</p>;
  // 卡片里用 640 宽的缩略图（侧栏才 340 宽）：原来放原图，点一下画板，此刻面板要解码好几张几百万像素的图。点图看原图
  else if (k === 'image') body = <a href={o.media!.url!} target="_blank" rel="noreferrer" title="点开看原图"><Thumb project={project} o={o} width={640} frames={frames} /></a>;
  else if (k === 'video') body = frames
    ? <>
        <Img src={frameUrl(project, o.id, at)} />
        {!CAPTURE && <video muted controls preload="none" src={o.media!.url!} style={{marginTop: 4}}
                            onLoadedMetadata={(e) => { const v = e.currentTarget; v.currentTime = Math.min(at, Math.max(0, v.duration - 0.05)); }} />}
      </>
    : <video muted controls preload="metadata" src={o.media!.url!}
             onLoadedMetadata={(e) => { const v = e.currentTarget; v.currentTime = Math.min(at, Math.max(0, v.duration - 0.05)); }} />;
  else if (k === 'audio') body = <>
    <div className="wave-box"><Waveform url={o.media!.url!} /><WaveMark at={onClip && o.end > o.begin ? at / (o.end - o.begin) : null} /></div>
    <audio controls preload="none" src={o.media!.url!} style={{width: '100%'}} />
  </>;
  const said = full ? (notes?.threads ?? []).filter(({top}) => top.targets.some((t) => t.kind === 'object' && t.id === o.id && t.project === project)) : [];
  const relations = full ? relationsOf(model, 'object', o.id) : [];
  return (
    <div className={`card${o.id === selected ? ' sel' : ''}`}>
      <div className="meta">{`#${o.id} ${o.name} · ${o.type} · ${fmt(o.begin, unit)} – ${fmt(o.end, unit)}`}
        {full && <button className="walk-btn" title="从这个对象出发，顺着关联往外读：挂在上面的批注、连着的对象、再往外一步……（侧栏「沿着读」）"
                         onClick={() => startWalk(`object:${o.id}`)}>沿着读</button>}</div>
      {body}
      {o.text != null && <div className="txt">{o.text}</div>}
      {said.length > 0 && <div className="rels"><div className="rels-head">批注</div>
        {said.map(({top, replies}) => <div key={top.id} className="rel goto" onClick={() => setState({side: 'notes'})}>
          💬 {top.text}<small>{top.status === 'done' ? '已处理' : '待处理'}{top.author ? ' · ' + top.author : ''}{replies.length ? ` · ${replies.length} 条回复` : ''}</small>
        </div>)}
      </div>}
      {relations.length > 0 && <div className="rels"><div className="rels-head">关系</div>
        {relations.map(({dir, ref, tips}, i) => {
          const can = ref.project === project && (ref.kind === 'layer' ? !!model.layer(ref.id) : !!model.object(ref.id));
          return <div key={i} className={`rel${can ? ' goto' : ''}`} onClick={() => can && (ref.kind === 'object' ? selectObject(ref.id) : goToTarget(ref, null))}>
            <b>{dir}</b> {refLabel(model, ref)}{tips && <small>{tips}</small>}
          </div>;
        })}
      </div>}
      {full && plugins.filter((p) => p.objectDetail && (!p.handles?.length || p.handles.includes(k))).map((p) =>
        <div key={p.name} className="plugin-detail" data-plugin={p.name}>
          <PluginBoundary name={p.name}>{createElement(p.objectDetail!, {object: o, model})}</PluginBoundary>
        </div>)}
      {full && <pre>{JSON.stringify(o.information, null, 1)}</pre>}
      {full && o.tips && <pre>备注：{o.tips}</pre>}
    </div>
  );
}

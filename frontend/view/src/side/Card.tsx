// 对象卡片：此刻面板、选中对象的详情都用它
import {frameUrl} from '../api';
import {goToTarget, selectObject} from '../actions';
import {Waveform} from '../canvas/Waveform';
import {kindOf} from '../model/kinds';
import {refLabel, relationsOf} from '../model/labels';
import type {ObjWithLayer} from '../model/model';
import {fmt, isSec} from '../model/units';
import {CAPTURE} from '../params';
import {useShallow} from 'zustand/react/shallow';
import {activeBoard, setState, useModel, useNotes, useStore} from '../store';

export function Card({o, full = false, local = null}: {o: ObjWithLayer; full?: boolean; local?: number | null}) {
  const model = useModel()!;
  const notes = useNotes();
  const {project, frames, selected, playhead, onActive, offset} = useStore(useShallow((s) => {
    const act = activeBoard(s);
    return {project: s.project!, frames: s.frames, selected: s.selected, playhead: s.playhead,
            onActive: !!act && act.rows.flat().includes(o.layer.root!), offset: model.offsetOf(s.boards, o.layer.root!)};
  }));
  const unit = model.unitOfRoot(o.layer.root);
  const here = local ?? (playhead != null && onActive ? playhead - offset : null);
  const onClip = here != null && isSec(unit), at = onClip ? Math.max(0, here! - o.begin) : 0;
  const k = kindOf(o), missing = !!o.media && !o.media.available;
  let body = null;
  if (missing) body = <p className="hint">文件不存在：{o.media!.source}</p>;
  else if (k === 'image') body = <img src={o.media!.url!} alt="" />;
  else if (k === 'video') body = frames
    ? <>
        <img src={frameUrl(project, o.id, at)} alt="" />
        {!CAPTURE && <video muted controls preload="none" src={o.media!.url!} style={{marginTop: 4}}
                            onLoadedMetadata={(e) => { const v = e.currentTarget; v.currentTime = Math.min(at, Math.max(0, v.duration - 0.05)); }} />}
      </>
    : <video muted controls preload="metadata" src={o.media!.url!}
             onLoadedMetadata={(e) => { const v = e.currentTarget; v.currentTime = Math.min(at, Math.max(0, v.duration - 0.05)); }} />;
  else if (k === 'audio') body = <>
    <Waveform url={o.media!.url!} mark={onClip && o.end > o.begin ? at / (o.end - o.begin) : null} />
    <audio controls preload="none" src={o.media!.url!} style={{width: '100%'}} />
  </>;
  const said = full ? (notes?.threads ?? []).filter(({top}) => top.targets.some((t) => t.kind === 'object' && t.id === o.id && t.project === project)) : [];
  const relations = full ? relationsOf(model, 'object', o.id) : [];
  return (
    <div className={`card${o.id === selected ? ' sel' : ''}`}>
      <div className="meta">#{o.id} {o.name} · {o.type} · {fmt(o.begin, unit)} – {fmt(o.end, unit)}</div>
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
      {full && <pre>{JSON.stringify(o.information, null, 1)}</pre>}
      {full && o.tips && <pre>备注：{o.tips}</pre>}
    </div>
  );
}

// 素材页：像资源管理器一样，用网格显示图片、视频封面、音频波形和文字；点一下回到画布上的对应位置
import {useEffect} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {selectObject} from '../actions';
import {Frame, Thumb} from '../canvas/Media';
import {Waveform} from '../canvas/Waveform';
import {markReady} from '../capture';
import {KIND_LABEL, kindOf} from '../model/kinds';
import {fmt} from '../model/units';
import {setState, useModel, useStore} from '../store';

const FILTERS = ['all', 'image', 'video', 'audio', 'text'];
const COLOR: Record<string, string> = {image: 'var(--image)', video: 'var(--video)', audio: 'var(--audio)', text: 'var(--text-c)'};

export function AssetsView() {
  const model = useModel();
  const {kind, project, frames} = useStore(useShallow((s) => ({kind: s.assetKind, project: s.project!, frames: s.frames})));
  useEffect(() => { if (model) markReady(); }, [model]);
  if (!model) return null;
  const items = model.allObjects().filter((o) => o.layer.role !== 'note' && (kind === 'all' ? kindOf(o) !== 'other' : kindOf(o) === kind));
  return (
    <main className="assets-view">
      <div className="filters">
        {FILTERS.map((f) => <button key={f} className={kind === f ? 'on' : ''} onClick={() => setState({assetKind: f})}>{f === 'all' ? '全部' : KIND_LABEL[f]}</button>)}
      </div>
      <div className="grid">
        {!items.length && <p className="hint">没有这类素材。</p>}
        {items.map((o) => {
          const k = kindOf(o), missing = !!o.media && !o.media.available, unit = model.unitOfRoot(o.layer.root);
          return (
            <div key={o.id} className="tile" title={o.media?.source ?? ''} onClick={() => selectObject(o.id)}>
              <div className="thumb">
                {missing ? '文件不存在'
                  : k === 'image' ? <Thumb project={project} o={o} width={320} frames={frames} />
                  : k === 'video' ? <Frame project={project} o={o} at={0.1} frames={frames} />
                  : k === 'audio' ? <Waveform url={o.media!.url!} className="tile-wave" />
                  : k === 'text' ? <div className="txt">{o.text}</div> : null}
                <span className="badge" style={{background: COLOR[k] ?? 'var(--other)'}}>{KIND_LABEL[k] ?? k}</span>
              </div>
              <div className="info">
                <div className="nm">{o.name || (o.media?.source || '').split(/[\\/]/).pop() || `对象 ${o.id}`}</div>
                <div className="meta">{o.layer.name || `层 ${o.layer.id}`} · {fmt(o.begin, unit)} – {fmt(o.end, unit)}</div>
              </div>
            </div>
          );
        })}
      </div>
    </main>
  );
}

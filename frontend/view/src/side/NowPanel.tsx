// 此刻：播放头所在这一刻，当前画板每层都有什么；接续的行写出是哪一段的第几秒
import {useShallow} from 'zustand/react/shallow';
import {fmt} from '../model/units';
import {activeBoard, useModel, useStore} from '../store';
import {Card} from './Card';

export function NowPanel() {
  const model = useModel();
  const {act, playhead, selected} = useStore(useShallow((s) => ({act: activeBoard(s), playhead: s.playhead, selected: s.selected})));
  if (!model) return null;
  const sel = selected != null ? model.object(selected) : undefined;
  const unit = act ? model.unitOfRoot(act.rows[0][0]) : '';
  const blocks = [];
  if (playhead != null && act) {
    const near = 4 / model.pps(act);
    for (const row of act.rows) {
      const seg = model.segmentAt(row, playhead);
      if (!seg) continue;
      const local = playhead - seg.offset;
      if (row.length > 1) blocks.push(<h3 key={`s${seg.root}`} className="seg">▶ {model.nameOf(seg.root)} 的 {fmt(local, model.unitOfRoot(seg.root))}</h3>);
      for (const track of model.visibleTracks(row)) for (const {layer} of track.parts.filter((p) => p.seg.root === seg.root)) {
        const here = layer.objects.filter((o) => (o.begin <= local && local < o.end) || (o.begin === o.end && Math.abs(o.begin - local) < near));
        if (!here.length) continue;
        blocks.push(<div key={`l${layer.id}`}>
          <h3>{layer.name || `层 ${layer.id}`} · {layer.type}</h3>
          {here.map((o) => <Card key={o.id} o={{...o, layer}} local={local} />)}
        </div>);
      }
    }
  }
  return (
    <section>
      <h2>此刻 <span>{playhead != null && act ? `${fmt(playhead, unit)} · ${act.rows.map((row) => row.map((r) => model.nameOf(r)).join(' → ')).join(' ＋ ')}` : ''}</span></h2>
      {sel && <><h3>选中的对象</h3><Card o={sel} full /></>}
      {blocks}
      {playhead != null && !blocks.length && <p className="hint">这一刻没有对象。</p>}
      {playhead == null && !sel && <p className="hint">点画板上的任意位置，查看那一刻这块画板每层都有什么；点色块查看对象详情。</p>}
    </section>
  );
}

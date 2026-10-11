// 此刻：播放头所在这一刻，当前画板每层都有什么；接续的行写出是哪一段的第几秒。
// 这一刻没有对象的层写一行是哪种空：两个对象之间空着（从哪到哪、多长）、还没开始、已经结束
import {useShallow} from 'zustand/react/shallow';
import {gapAt} from '../model/gaps';
import type {Gap} from '../model/gaps';
import {fmt, fmtSpan} from '../model/units';
import {activeBoard, useModel, useStore} from '../store';
import {Card} from './Card';

function gapText(gap: Gap, unit: string): string {
  if (gap.kind === 'between') return `空着：${fmt(gap.from, unit)} – ${fmt(gap.to, unit)}（${fmtSpan(gap.to - gap.from, unit)}）`;
  if (gap.kind === 'before') return `还没开始：${fmt(gap.next, unit)} 才有`;
  return `已经结束：最后一个在 ${fmt(gap.last, unit)} 结束`;
}

export function NowPanel() {
  const model = useModel();
  const {act, playhead, selected} = useStore(useShallow((s) => ({act: activeBoard(s), playhead: s.playhead, selected: s.selected})));
  if (!model) return null;
  const sel = selected != null ? model.object(selected) : undefined;
  const unit = act ? model.unitOfRoot(act.rows[0][0]) : '';
  const blocks = [];
  let cards = 0;
  if (playhead != null && act) {
    const near = 4 / model.pps(act);
    for (const row of act.rows) {
      const seg = model.segmentAt(row, playhead);
      if (!seg) continue;
      const local = playhead - seg.offset;
      if (row.length > 1) blocks.push(<h3 key={`s${seg.root}`} className="seg">▶ {model.nameOf(seg.root)} 的 {fmt(local, model.unitOfRoot(seg.root))}</h3>);
      for (const track of model.visibleTracks(row)) {
        if (model.foldOf(track) != null) {                  // 折叠的轨道：只写一行，不列里面的对象
          if (track.parts.some((p) => p.seg.root === seg.root))
            blocks.push(<div key={`f${track.key}`} className="gap-line folded"><b>{track.name || (track.key === '' ? model.nameOf(seg.root) : track.type)}</b> 已折叠（连同下面的层）</div>);
          continue;
        }
        for (const {layer} of track.parts.filter((p) => p.seg.root === seg.root)) {
        const here = layer.objects.filter((o) => (o.begin <= local && local < o.end) || (o.begin === o.end && Math.abs(o.begin - local) < near));
        if (!here.length) {
          const gap = gapAt(layer.objects, local, near), segUnit = model.unitOfRoot(seg.root);
          if (gap) blocks.push(<div key={`l${layer.id}`} className={`gap-line ${gap.kind}`}><b>{layer.name || `层 ${layer.id}`}</b> {gapText(gap, segUnit)}</div>);
          continue;
        }
        cards += here.length;
        blocks.push(<div key={`l${layer.id}`}>
          <h3>{layer.name || `层 ${layer.id}`} · {layer.type}</h3>
          {here.map((o) => <Card key={o.id} o={{...o, layer}} local={local} />)}
        </div>);
        }
      }
    }
  }
  return (
    <section>
      <h2>此刻 <span>{playhead != null && act ? `${fmt(playhead, unit)} · ${act.rows.map((row) => row.map((r) => model.nameOf(r)).join(' → ')).join(' ＋ ')}` : ''}</span></h2>
      {sel && <><h3>选中的对象</h3><Card o={sel} full /></>}
      {blocks}
      {playhead != null && !cards && <p className="hint">这一刻没有对象。</p>}
      {playhead == null && !sel && <p className="hint">点画板上的任意位置，查看那一刻这块画板每层都有什么；点色块查看对象详情。</p>}
    </section>
  );
}

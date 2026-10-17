import {tr, useI18n} from '../i18n';
// 此刻：播放头所在这一刻，当前画板每层都有什么；接续的行写出是哪一段的第几秒。
// 这一刻没有对象的层写一行是哪种空：两个对象之间空着（从哪到哪、多长）、还没开始、已经结束
import {useShallow} from 'zustand/react/shallow';
import {gapAt} from '../model/gaps';
import type {Gap} from '../model/gaps';
import {fmt, fmtSpan} from '../model/units';
import {copyMoment} from '../actions';
import {activeBoard, useModel, useStore} from '../store';
import {Card} from './Card';

function gapText(gap: Gap, unit: string): string {
  if (gap.kind === 'between') return tr("now.gap", {value1: fmt(gap.from, unit), value2: fmt(gap.to, unit), value3: fmtSpan(gap.to - gap.from, unit, tr)});
  if (gap.kind === 'before') return tr("now.notStarted", {value1: fmt(gap.next, unit)});
  return tr("now.ended", {value1: fmt(gap.last, unit)});
}

export function NowPanel() {
  useI18n();
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
      if (row.length > 1) blocks.push(<h3 key={`s${seg.root}`} className="seg">▶ {model.nameOf(seg.root, tr)}  {tr("now.of")} {fmt(local, model.unitOfRoot(seg.root))}</h3>);
      for (const track of model.visibleTracks(row)) {
        if (model.foldOf(track) != null) {                  // 折叠的轨道：只写一行，不列里面的对象
          if (track.parts.some((p) => p.seg.root === seg.root))
            blocks.push(<div key={`f${track.key}`} className="gap-line folded"><b>{track.name || (track.key === '' ? model.nameOf(seg.root, tr) : track.type)}</b>  {tr("now.collapsed")}</div>);
          continue;
        }
        for (const {layer} of track.parts.filter((p) => p.seg.root === seg.root)) {
        const here = layer.objects.filter((o) => (o.begin <= local && local < o.end) || (o.begin === o.end && Math.abs(o.begin - local) < near));
        if (!here.length) {
          const gap = gapAt(layer.objects, local, near), segUnit = model.unitOfRoot(seg.root);
          if (gap) blocks.push(<div key={`l${layer.id}`} className={`gap-line ${gap.kind}`}><b>{layer.name || tr("common.layerId", {value1: layer.id})}</b> {gapText(gap, segUnit)}</div>);
          continue;
        }
        cards += here.length;
        blocks.push(<div key={`l${layer.id}`}>
          <h3>{layer.name || tr("common.layerId", {value1: layer.id})} · {layer.type}</h3>
          {here.map((o) => <Card key={o.id} o={{...o, layer}} local={local} />)}
        </div>);
        }
      }
    }
  }
  return (
    <section>
      <h2>{tr("now.title")} <span>{playhead != null && act ? `${fmt(playhead, unit)} · ${act.rows.map((row) => row.map((r) => model.nameOf(r, tr)).join(' → ')).join(' ＋ ')}` : ''}</span>
        {playhead != null && act && <button className="walk-btn" title={tr("now.copyHint")}
                                            onClick={copyMoment}>{tr("now.copy")}</button>}</h2>
      {sel && <><h3>{tr("now.selected")}</h3><Card o={sel} full /></>}
      {blocks}
      {playhead != null && !cards && <p className="hint">{tr("now.empty")}</p>}
      {playhead == null && !sel && <p className="hint">{tr("now.hint")}</p>}
    </section>
  );
}

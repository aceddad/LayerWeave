import {AbsoluteFill, staticFile, useCurrentFrame} from 'remotion';
import {Audio} from '@remotion/media';
import {FPS, MUSIC, beat, beatPos} from './time';
import {Subtitles, SubtitleMode} from './ui/Subtitles';
import {Intro} from './scenes/Intro';
import {Dots} from './scenes/Dots';

// 段落表：每段从第几秒开始、用哪个组件。每段拿到的都是全局秒数 t。
type Seg = {from: number; name: string; C?: React.FC<{t: number}>};
export const SEGS: Seg[] = [
  {from: 0, name: '① 开场', C: Intro},
  {from: beat(16), name: '② 点阵', C: Dots},
  {from: beat(28), name: '③ 待做'},
];

export const segAt = (t: number) => {
  let k = 0;
  for (let i = 0; i < SEGS.length; i++) if (t >= SEGS[i].from) k = i;
  return SEGS[k];
};

const Todo: React.FC<{name: string}> = ({name}) => (
  <AbsoluteFill style={{background: '#111', alignItems: 'center', justifyContent: 'center', color: '#666', fontSize: 44}}>
    {name} · TODO
  </AbsoluteFill>
);

export const Film: React.FC<{music?: boolean; timecode?: boolean; subtitles?: SubtitleMode}> = ({
  music = true, timecode = false, subtitles = 'off',
}) => {
  const t = useCurrentFrame() / FPS;
  const s = segAt(t);
  return (
    <AbsoluteFill style={{background: '#111'}}>
      {s.C ? <s.C t={t}/> : <Todo name={s.name}/>}
      <Subtitles t={t} mode={subtitles}/>
      {timecode && (
        <div style={{position: 'absolute', left: 16, bottom: 12, font: '20px monospace', color: '#ff0', background: 'rgba(0,0,0,.6)', padding: '2px 8px'}}>
          {t.toFixed(2)}s · 第 {beatPos(t).toFixed(1)} 拍 · {s.name}
        </div>
      )}
      {music && MUSIC && <Audio src={staticFile(MUSIC)}/>}
    </AbsoluteFill>
  );
};

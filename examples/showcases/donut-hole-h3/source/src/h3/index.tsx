// H3 演示：分镜 v6（60 个镜头的动态 SVG）当母版，每个镜头换成 H3 首尾帧补出来的视频（关键帧来自 astra 的交付），
// 镜头运动、字和少数纯代码镜头由这里的代码完成。地址 ?v=h3。镜头表见 generation/镜头表.py。
import React, {useEffect, useLayoutEffect, useRef, useState} from 'react';
import type {CSSProperties, ReactNode} from 'react';
import {useT} from '../core/clock';
import {BEAT, E, KICKS, pulse} from '../core/time';
import {CREAM, Fill, Flash, KText, L, T0, T1, Vignette, clamp, ease, io, rnd, seg, src, useLyrics} from '../v10/kit';
import SHOTS from '../data/h3_shots.json';

type Shot = {id: number; t0: number; t1: number; sec: string};
const LIST = SHOTS as Shot[];
const shotAt = (t: number) => LIST.find((s) => t >= s.t0 - E && t < s.t1 - E) ?? LIST[LIST.length - 1];
const clip = (n: number) => `/h3/视频/镜${String(n).padStart(2, '0')}.mp4`;
export const H3_VIDEOS = Array.from(new Set([2, 3, 10, 4, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 28, 29, 31, 32, 34, 38, 40, 42, 43, 44, 45, 47, 48, 49, 54, 56, 57, 58, 59])).map(clip);

// ---------------------------------------------------------------- 视频：时间由 t 决定（逐帧截图时也一样）
// fit：整段视频压进镜头时长（首尾帧那种，首帧对镜头开头、尾帧对镜头结尾）；natural：原速，从 offset 秒开始
const Clip: React.FC<{n: number; a: number; b: number; mode?: 'fit' | 'natural'; offset?: number; freeze?: number; style?: CSSProperties}> =
  ({n, a, b, mode = 'natural', offset = 0, freeze, style}) => {
    const t = useT();
    const ref = useRef<HTMLVideoElement>(null);
    const [dur, setDur] = useState(4);
    useLayoutEffect(() => {
      const v = ref.current;
      if (!v) return;
      const D = v.duration || dur;
      const want = freeze !== undefined ? Math.min(freeze, D - 0.05) : mode === 'fit' ? seg(t, a, b) * (D - 0.05) : clamp(offset + (t - a), 0, D - 0.05);
      if (Math.abs(v.currentTime - want) > 0.001) v.currentTime = want;
    });
    return <video ref={ref} src={clip(n)} muted playsInline preload="auto" onLoadedMetadata={(e) => setDur(e.currentTarget.duration)}
                  style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, objectFit: 'cover', ...style}} />;
  };

// 镜头运动：push（推到 k 倍）/ pan（横移画面宽度的 d）/ rotate（转到 deg）/ shake（每拍一震）
type Cam = ['push', number] | ['pan', number] | ['rotate', number] | ['shake', number];
const camStyle = (t: number, a: number, b: number, cam?: Cam): CSSProperties => {
  if (!cam) return {};
  const k = io(seg(t, a, b));
  if (cam[0] === 'push') return {transform: `scale(${1 + (cam[1] - 1) * k + (cam[1] < 1 ? 1 - cam[1] : 0)})`};
  if (cam[0] === 'pan') return {transform: `scale(1.08) translateX(${cam[1] * 1920 * (k - 0.5)}px)`};
  if (cam[0] === 'rotate') return {transform: `rotate(${cam[1] * k}deg) scale(${1.1 + Math.abs(cam[1]) / 100})`};
  const p = pulse(KICKS, t, 0.08) * cam[1];
  const i = Math.floor(t * 24);
  return {transform: `translate(${(rnd(i) - 0.5) * p}px, ${(rnd(i + 3) - 0.5) * p}px) scale(1.04)`};
};
const Shot: React.FC<{s: Shot; cam?: Cam; children: ReactNode; fade?: number}> = ({s, cam, children, fade}) => {
  const t = useT();
  const out = fade ? 1 - seg(t, s.t1 - fade, s.t1) : 1;
  return <Fill style={{overflow: 'hidden', background: '#000'}}><Fill style={{...camStyle(t, s.t0, s.t1, cam), opacity: out}}>{children}</Fill></Fill>;
};

// 纯代码镜头：分镜 v6 的动态 SVG，按 t 拨到对应时刻
const Svg: React.FC<{n: number; a: number}> = ({n, a}) => {
  const t = useT();
  const ref = useRef<HTMLDivElement>(null);
  const [code, setCode] = useState('');
  useEffect(() => { fetch(`/h3/svg/${String(n).padStart(2, '0')}.svg`).then((r) => r.text()).then(setCode); }, [n]);
  useLayoutEffect(() => {
    const svg = ref.current?.querySelector('svg') as SVGSVGElement | null;
    if (!svg) return;
    svg.setAttribute('width', '1920'); svg.setAttribute('height', '1080');
    svg.pauseAnimations(); svg.setCurrentTime(Math.max(0, t - a));
  });
  return <div ref={ref} style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080}} dangerouslySetInnerHTML={{__html: code}} />;
};
const Still: React.FC<{id: number | string; style?: CSSProperties}> = ({id, style}) =>
  <img src={src(id)} style={{position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, objectFit: 'cover', ...style}} />;

// ---------------------------------------------------------------- 每个镜头
const FIT = new Set([6, 9, 11, 12, 17, 19, 20, 22, 28, 29, 38, 40, 42, 43, 47, 54, 58]);
const CAM: Record<number, Cam> = {2: ['pan', -0.12], 10: ['push', 0.9], 3: ['push', 1.05], 4: ['push', 1.08], 7: ['push', 1.04], 8: ['pan', -0.04], 14: ['push', 1.06], 19: ['push', 1.35],
  21: ['pan', -0.05], 23: ['push', 0.85], 34: ['push', 1.1], 42: ['rotate', 12], 43: ['shake', 10], 25: ['rotate', 6], 26: ['shake', 6], 27: ['rotate', -4],
  36: ['push', 1.08], 37: ['pan', 0.06], 39: ['push', 0.85], 52: ['push', 1.3], 53: ['push', 1.15], 33: ['push', 1.12], 35: ['push', 0.88]};

const View: React.FC<{s: Shot}> = ({s}) => {
  const t = useT();
  const {id, t0: a, t1: b} = s;
  const cam = CAM[id];
  switch (id) {
    case 1: case 41: case 46: case 50:
      return <Shot s={s}><Svg n={id} a={a} /></Shot>;
    case 5:
      return <Shot s={s}><Still id={t < (a + b) / 2 ? 6 : 7} /></Shot>;
    case 13: {
      const parts = [34, 33, 31, 32];
      return <Shot s={s}><Still id={parts[clamp(Math.floor((t - a + E) / BEAT), 0, 7) % 4]} style={{transform: `scale(${1.06 - 0.03 * (((t - a) % BEAT) / BEAT)})`}} /></Shot>;
    }
    case 25: return <Shot s={s} cam={cam}><Clip n={2} a={a} b={b} offset={2} /><Clip n={2} a={a} b={b} offset={2.3} style={{opacity: 0.35, mixBlendMode: 'screen', transform: 'translateX(14px)'}} /></Shot>;
    case 26: return <Shot s={s} cam={cam}><Clip n={3} a={a} b={b} offset={1.5} /></Shot>;
    case 27: return <Shot s={s} cam={cam}><Clip n={4} a={a} b={b} offset={0.5} /></Shot>;
    case 30: {
      const r = 300 + 20 * Math.sin((t - a) * 1.7);
      return (
        <Shot s={s}>
          <Fill style={{background: `radial-gradient(circle at 960px 540px, transparent ${r}px, #2a1209 ${r + 6}px, #5a2a14 ${r + 90}px, #3a1a0c ${r + 330}px, #160904 ${r + 700}px)`, zIndex: 2}} />
          <Fill style={{clipPath: `circle(${r}px at 960px 540px)`}}><Clip n={23} a={a} b={b} offset={0.5} style={{transform: `scale(1.15) translateX(${30 * Math.sin(t)}px)`, filter: 'brightness(1.2) saturate(1.2)'}} /></Fill>
        </Shot>
      );
    }
    case 33: return <Shot s={s} cam={cam}><Clip n={32} a={a} b={b} offset={1} /></Shot>;
    case 35: {
      const k = ease(seg(t, a + 1, b));
      return <Shot s={s} cam={cam}><Clip n={32} a={a} b={b} offset={2} /><Fill style={{background: `radial-gradient(circle ${150 + 900 * k}px at 960px 540px, rgba(255,230,190,${0.9 * k}), transparent)`, mixBlendMode: 'screen'}} /></Shot>;
    }
    case 36: return <Shot s={s} cam={cam}><Clip n={20} a={a} b={b} mode="fit" /></Shot>;
    case 37: return <Shot s={s} cam={cam}><Clip n={21} a={a} b={b} offset={0.3} /></Shot>;
    case 39: return <Shot s={s} cam={cam}><Clip n={23} a={a} b={b} offset={0.5} /></Shot>;
    case 45: {
      const half = Math.floor((t - a + E) / (BEAT / 2));
      return <Shot s={s}>{half % 2 === 0 ? <Clip n={45} a={a} b={b} offset={0.3} /> : <Clip n={44} a={a} b={b} offset={1} />}<Flash at={[a + BEAT * 2, a + BEAT * 4]} frames={1} /></Shot>;
    }
    case 51: {
      // 心が千切れそう：画面被切成竖条，一条条错开
      const k = ease(seg(t, a + 0.8, b));
      return (
        <Shot s={s}>
          {Array.from({length: 8}, (_, j) => (
            <Fill key={j} style={{clipPath: `inset(0 ${1920 - (j + 1) * 240}px 0 ${j * 240}px)`, transform: `translateY(${(j % 2 ? -1 : 1) * 140 * k}px)`}}>
              <Clip n={49} a={a} b={b} offset={1} />
            </Fill>
          ))}
        </Shot>
      );
    }
    case 55: {
      // 不唱了，热烧到最满：过曝，只剩她的剪影，火星往上烧
      const k = io(seg(t, a, b));
      return (
        <Shot s={s}>
          <Fill style={{background: 'radial-gradient(ellipse at 50% 55%, #ffffff 0%, #fff1d8 40%, #ffb766 100%)'}} />
          <img src={src(47)} style={{position: 'absolute', left: 960 - 230 * (1 + 0.1 * k), top: 70, height: 1010 * (1 + 0.1 * k), filter: 'brightness(0)', opacity: 0.88}} />
          <Fill style={{background: '#fff', opacity: 0.55 * Math.pow(seg(t, b - 0.6, b), 2)}} />
        </Shot>
      );
    }
    case 52: return <Shot s={s} cam={cam}><Clip n={20} a={a} b={b} mode="fit" /></Shot>;
    case 53: return <Shot s={s} cam={cam}><Clip n={21} a={a} b={b} offset={0.8} /></Shot>;
    case 60: return <Shot s={s}><Clip n={59} a={a} b={b} freeze={3.95} /></Shot>;
    default:
      return <Shot s={s} cam={cam} fade={id === 24 ? 0.45 : id === 40 ? 1.2 : undefined}><Clip n={id} a={a} b={b} mode={FIT.has(id) ? 'fit' : 'natural'} /></Shot>;
  }
};

// ---------------------------------------------------------------- 字：每句一行，竖排，左右交替；纯字镜头（50）不叠
const Lyric: React.FC = () => {
  const t = useT();
  useLyrics();
  const s = shotAt(t);
  if (s.id === 50) return null;
  const i = Array.from({length: 41}, (_, k) => k + 1).find((k) => t >= T0(k) - E && t < T1(k) + 0.3);
  if (!i) return null;
  const right = i % 2 === 1;
  return <KText text={L(i)} t0={T0(i)} t1={T1(i)} x={right ? 1740 : 110} y={110} size={48} vertical enter="type" step={0.07} drift={[0, -4]} weight={600}
                color={CREAM} shadow="0 0 14px rgba(0,0,0,.85), 0 2px 4px rgba(0,0,0,.9)" />;
};

export const H3Film: React.FC = () => {
  const t = useT();
  const s = shotAt(t);
  return (
    <Fill style={{background: '#000'}}>
      <View key={s.id} s={s} />
      <Lyric />
      <Flash at={[64.27, 123.35, 174.75]} frames={2} />
      <Vignette k={0.4} />
    </Fill>
  );
};
void rnd;

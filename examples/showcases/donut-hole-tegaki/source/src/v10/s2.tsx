// v9 · B1、副歌一、间奏一（0:47–1:31）
import React from 'react';
import {useT} from '../core/clock';
import {KICKS, SNARES, pulse} from '../core/time';
import {A, BEAT, CREAM, Cam, Chroma, Cut, Dots, E, Fill, Flash, Field, Glitch, Glow, Grade, Hole, Horizon, KText, L, Letterbox, Motes, Plane, Rays, Ribbon,
  Scene3D, Slit, T0, T1, Vignette, charT, clamp, ease, io, lerp, near, on12, rnd, seg, shake, stem, useLyrics} from './kit';
import {GlyphWord, Panes, impact} from './GlyphWord';
import {SING_34, SING_FACE, SING_FRONT, Sing, breath} from './parts';
import BOLD from '../data/glyph_bold.json';
import LIGHT from '../data/glyph_light.json';
import HT54 from '../data/ht_0054.json';

type GData = Parameters<typeof GlyphWord>[0]['data'];
const GB = BOLD as unknown as GData, GL = LIGHT as unknown as GData;

// ================================================================ B1 0:47.21–1:04.35（信息量降下来：夜、慢、空白多）
export const B1_9: React.FC = () => {
  const t = useT();
  useLyrics();
  const HY = 540;
  const slit = lerp(170, 300, io(seg(t, 47.21, 51.46)));
  const lights = [63.0, 63.3, 63.55, 63.8, 64.05];
  return (
    <Fill style={{background: '#000'}}>
      {/* ⑨ 锁着的门：只从一条窄缝里看见 */}
      <Cut a={47.21} b={51.46}>
        <Field temp="night" k={0.4} />
        <Motes n={50} color="#cfd9ec" size={2} up={false} op={0.35} seed={21} speed={0.35} />
        <Slit y={HY} h={slit}><Grade mode="night"><Cam s={1.0 + 0.1 * seg(t, 47.21, 51.46)} x={-90 + 180 * seg(t, 47.21, 51.46)} y={-20}><A id={36} /></Cam></Grade><Sweep t={t} at={48.6} dur={2.2} /></Slit>
        <Horizon y={HY - slit / 2} k={0.7} color="#c9d3e6" width={1.5} />
        <Horizon y={HY + slit / 2} k={0.7} color="#c9d3e6" width={1.5} />
        <KText text={L(9)} t0={T0(9)} t1={T1(9) - 0.15} x={700} y={HY + slit / 2 + 60} size={34} weight={400} drift={[-4, 0]} color="#dfe5f0" spacing={0.3} />
      </Cut>
      {/* ⑩ 手搭在栏杆上：焦点从虚到实 */}
      <Cut a={51.46} b={54.88}>
        <Grade mode="night" extra="brightness(1.1)">
          <Cam s={1.04 + 0.05 * seg(t, 51.46, 54.88)} x={-20 * seg(t, 51.46, 54.88)}><A id={37} style={{filter: `blur(${7 * (1 - ease(seg(t, 51.46, 52.6)))}px)`}} /></Cam>
        </Grade>
        <BarShadow t={t} a={51.46} speed={45} />
        <Sweep t={t} at={52.9} dur={1.8} />
        <KText text={L(10)} t0={T0(10)} t1={T1(10) - 0.15} x={1660} y={160} size={40} vertical weight={400} drift={[0, -5]} color="#e6ebf3" spacing={0.25} />
      </Cut>
      {/* ⑪ 靠着门坐下：站 → 撑地 → 抱膝，每次落在拍上，中间有下沉 */}
      <Cut a={54.88} b={58.72}><SitDown t={t} /></Cut>
      {/* ⑫ 想笑的侧脸 */}
      <Cut a={58.72} b={62.6}>
        <Grade mode="night" extra="brightness(1.05)">
          <Cam s={1.06 + 0.04 * seg(t, 58.72, 62.6)} x={25 * seg(t, 58.72, 62.6)}><A id={43} /></Cam>
        </Grade>
        <BarShadow t={t} a={58.72} speed={-38} k={0.45} />
        <Sweep t={t} at={60.4} dur={2.0} />
        <Glow x={1700} y={300} r={700} color="150,175,230" k={0.25} />
        <KText text={L(12)} t0={T0(12)} t1={62.35} x={480} y={170} size={44} vertical weight={400} drift={[0, -5]} spacing={0.25} />
      </Cut>
      {/* 1:02.6–1:04.35：隔着栏杆，舞台的灯一盏一盏亮，推进越来越快 */}
      <Cut a={62.6} b={64.35}>
        <Cam s={1 + 0.6 * Math.pow(seg(t, 62.6, 64.35), 2.3)} oy={520}>
          <Grade mode="night" extra={`brightness(${1 + 0.6 * seg(t, 63.5, 64.3)})`}>
            <A id={44} />
            <A id={45} style={{opacity: t >= 63.55 - E ? 1 : 0}} />
          </Grade>
          {lights.map((l, i) => t >= l - E && <Glow key={i} x={700 + i * 130} y={430 + (i % 2) * 20} r={180 + 60 * Math.exp(-(t - l) / 0.15)} color="255,200,130" k={0.8} />)}
        </Cam>
        <Glow x={960} y={480} r={1300} color="255,170,90" k={ease(seg(t, 63.3, 64.3))} />
      </Cut>
      <Flash at={[64.27]} frames={2} />
      <Vignette k={0.7} />
    </Fill>
  );
};

const SitDown: React.FC<{t: number}> = ({t}) => {
  const a = 54.88, k1 = T0(11) + BEAT * 2, k2 = k1 + BEAT * 3;
  const id = t < k1 - E ? 38 : t < k2 - E ? 39 : 40;
  const since = t - (id === 38 ? a : id === 39 ? k1 : k2);
  const drop = id === 38 ? 0 : -18 * Math.exp(-since / 0.09);        // 换姿势那一下往下一沉再落定
  return (
    <Fill>
      <Grade mode="night">
        <Fill style={{background: 'linear-gradient(180deg, #0c1222 0%, #18223a 70%, #0b0f1a 100%)'}} />
        <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
          {Array.from({length: 17}, (_, i) => <rect key={i} x={40 + i * 116} y={0} width={18} height={1080} fill="#070a12" />)}
          <rect x={0} y={150} width={1920} height={16} fill="#070a12" /><rect x={0} y={880} width={1920} height={16} fill="#070a12" />
        </svg>
        <Fill style={{transform: `translateY(${-drop}px)`}}><A id={id} /></Fill>
      </Grade>
      <KText text={L(11)} t0={T0(11)} t1={T1(11) - 0.15} x={160} y={900} size={40} weight={400} drift={[6, 0]} spacing={0.25} />
    </Fill>
  );
};

const BarShadow: React.FC<{t: number; a: number; speed?: number; k?: number}> = ({t, a, speed = 60, k = 0.55}) => (
  <Fill style={{mixBlendMode: 'multiply', opacity: k, pointerEvents: 'none',
    backgroundImage: 'repeating-linear-gradient(90deg, transparent 0px, transparent 150px, rgba(5,8,20,.95) 180px, rgba(5,8,20,.95) 214px, transparent 244px)',
    backgroundPosition: `${(t - a) * speed}px 0`, filter: 'blur(10px)'}} />
);
const Sweep: React.FC<{t: number; at: number; dur?: number; color?: string}> = ({t, at, dur = 1.6, color = '200,215,255'}) => {
  const p = seg(t, at, at + dur);
  return p <= 0 || p >= 1 ? null : <Fill style={{background: `linear-gradient(100deg, transparent ${p * 140 - 30}%, rgba(${color},.35) ${p * 140 - 15}%, transparent ${p * 140}%)`, mixBlendMode: 'screen'}} />;
};

// ================================================================ 副歌一 1:04.35–1:23.40（热：光、字带、她在唱）
export const Chorus1_9: React.FC = () => {
  const t = useT();
  useLyrics();
  const k = pulse(KICKS, t, 0.12);
  return (
    <Fill style={{background: '#000', transform: `scale(${1 + 0.012 * k})`}}>
      <Cut a={64.35} b={67.56}><Open13 t={t} /></Cut>
      <Cut a={67.56} b={72.11}><Orbit14 t={t} /></Cut>
      <Cut a={72.11} b={74.82}><Bye15 t={t} /></Cut>
      <Cut a={74.82} b={79.7}><Seats16 t={t} /></Cut>
      <Cut a={79.7} b={83.4}><Face17 t={t} /></Cut>
      <Vignette k={0.45} />
    </Fill>
  );
};

// ⑬ 门消失了：光从她背后的圆里涌出来，满场的暖光；她唱，字带从她身后流过
const Open13: React.FC<{t: number}> = ({t}) => {
  const a = 64.35, b = 67.56;
  const r = 1200 * ease(seg(t, a, a + 1.2));
  const push = 1 + 0.12 * io(seg(t, a, b));
  const wave = (ph: number, y: number, amp: number) => {
    let d = `M -200 ${y}`;
    for (let x = -200; x <= 2200; x += 60) d += ` L ${x} ${(y + Math.sin(x * 0.004 + ph) * amp).toFixed(1)}`;
    return d;
  };
  return (
    <Fill>
      <Field temp="heat" glow={[960, 520]} />
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}><circle cx={960} cy={430} r={Math.min(r, 470)} fill="#ffd9a0" opacity={0.85} /></svg>
      <Rays cx={960} cy={420} n={56} k={0.8 * ease(seg(t, a, a + 0.6))} spin={0.05} r0={260} />
      <Motes n={90} color="#ffd59a" size={4} op={0.9} glow seed={31} speed={1.3} />
      <Ribbon id="r13b" d={wave((t - a) * 0.8, 520, 90)} text={L(13)} t0={a} speed={260} size={58} op={0.9} repeat={3} />
      <Cam s={push} oy={1000}><Sing ids={SING_FRONT} y={60} s={breath(t)} origin="960px 1080px" /></Cam>
      <Ribbon id="r13f" d={wave((t - a) * 0.8 + 2, 820, 70)} text={L(13)} t0={a - 1.3} speed={340} size={74} op={0.95} repeat={3} weight={700} />
      <Flash at={[a]} frames={2} />
    </Fill>
  );
};

const wave14 = (ph: number, y: number, amp: number) => { let d = `M -200 ${y}`; for (let x = -200; x <= 2200; x += 60) d += ` L ${x} ${(y + Math.sin(x * 0.004 + ph) * amp).toFixed(1)}`; return d; };
// ⑭ 她在光里唱：背景、她、前后两半圈字带各在不同的深度；"体温"用真字形，军鼓那一下被切成两半
const Orbit14: React.FC<{t: number}> = ({t}) => {
  const a = 67.56, b = 72.11;
  const p = seg(t, a, b);
  const rot = lerp(-16, 16, io(p));
  const tw = charT(14, '体温');
  const crack = SNARES.find((s) => s.t > tw + 0.3)?.t ?? tw + 0.8;
  const cutK = ease(seg(t, crack, crack + 0.4));
  const hit = impact(t - crack);
  return (
    <Fill>
      <Field temp="heat" glow={[960 - rot * 20, 480]} />
      <Rays cx={1060} cy={380} n={48} k={0.7} spin={-0.06} />
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}><circle cx={1060 + rot * 4} cy={420} r={420} fill="#ffd9a0" opacity={0.75} /></svg>
      <Ribbon id="r14b" d={wave14((t - a) * 0.9, 330, 80)} text={L(14)} t0={a} speed={300} size={56} op={0.8} hot="体温" hotColor="#fff" />
      <Cam x={140 + rot * 3} s={breath(t)} oy={1080}><Sing ids={SING_34} y={30} /></Cam>
      <Ribbon id="r14f" d={wave14((t - a) * 0.9 + 2, 900, 60)} text={L(14)} t0={a - 1} speed={360} size={64} hot="体温" hotColor="#fff" weight={700} />
      <Motes n={70} color="#ffd59a" size={4} op={0.85} glow seed={41} speed={1.4} />
      {/* 体温：唱到这两个字时从中间亮出来，军鼓上被切开 */}
      {t >= tw - E && (
        <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0, mixBlendMode: 'screen', opacity: 1 - seg(t, b - 0.35, b)}}>
          <g style={{filter: 'drop-shadow(0 0 40px rgba(255,140,40,.9))'}}>
            {(['above', 'below'] as const).map((keep, j) => (
              <GlyphWord key={keep} data={GB} word="体温" x={80} y={110} w={600 * (1 + 0.05 * ease(seg(t, tw, tw + 0.3)))} h={303} fill="#fff4e4" opacity={ease(seg(t, tw, tw + 0.2))}
                cut={{x: 380, y: 262, angle: -14, keep}}
                warp={(x, y) => { const s = (j ? 1 : -1) * cutK; return [x + s * 38 + hit * 12, y + s * 30]; }} />
            ))}
          </g>
        </svg>
      )}
      <Flash at={[crack]} frames={1} />
    </Fill>
  );
};

// ⑮ バイバイ：手心朝上 → 合 → 攥紧；然后整个画面碎成斜窗格飞走
const Bye15: React.FC<{t: number}> = ({t}) => {
  const a = 72.11, b = 74.82;
  const i = clamp(Math.floor((t - a + E) / BEAT), 0, 2);
  const brk = charT(15, '永遠');
  const piece = (j: number) => {
    const age = t - brk - Math.abs(j - 3) * 0.05;
    const k = age < 0 ? 0 : ease(age / 0.7);
    return {x: (j - 3) * 90 * k, y: -380 * k * (0.6 + rnd(j)), z: 500 * k, rotateY: (j - 3) * 18 * k, rotateZ: (rnd(j + 2) - 0.5) * 30 * k, gone: age > 0.9};
  };
  return (
    <Fill>
      <Field temp="heat" glow={[960, 600]} />
      <Motes n={100} color="#ffd59a" size={4} op={0.9} glow seed={51} speed={1.6} />
      <Panes count={8} width={300} slope={0.3} offset={-260} piece={piece}>
        <Grade mode="heat"><Cam s={1.06 + 0.02 * ((t - a) % BEAT) / BEAT}><A id={[51, 52, 53][i]} /></Cam></Grade>
      </Panes>
      <KText text={L(15)} t0={T0(15)} t1={T1(15) - 0.05} x={140} y={130} size={92} enter="type" step={0.09} drift={[0, 0]} weight={800} wrap={1500} glow="rgba(255,140,40,.6)" />
      <Motes n={120} color="#fff0d0" size={5} op={1} glow seed={52} burst={{x: 960, y: 560, at: brk, power: 1.3}} style={{opacity: t >= brk - E ? 1 : 0}} />
    </Fill>
  );
};

// ⑯ 空会场俯拍：先是画，然后变成网点，点像火星一样往上飘走（幻觉露出一半真相）
const Seats16: React.FC<{t: number}> = ({t}) => {
  const a = 74.82, b = 79.7;
  const toDots = ease(seg(t, a + 0.6, a + 1.6));
  const rise = seg(t, a + 1.6, b);
  const data = HT54 as number[][];
  return (
    <Fill style={{background: '#0a0402'}}>
      <Cam s={1.3 - 0.25 * ease(seg(t, a, b))}>
        <Grade mode="heat"><A id={54} style={{opacity: 1 - toDots}} /></Grade>
        <Dots data={data} color="#ffcf8a" glow style={{opacity: toDots}}
              fx={(x, y, r, i) => {
                const lift = Math.max(0, rise - rnd(i) * 0.6) * (500 + 900 * rnd(i + 1));
                const sway = Math.sin(t * 2 + i) * 12 * rise;
                return [x + sway, y - lift, r * (1 - 0.5 * rise * rnd(i + 2)), 1 - Math.max(0, rise - 0.4 - rnd(i) * 0.4) * 2];
              }} />
      </Cam>
      <KText text={L(16).split('　')[0]} t0={T0(16)} t1={charT(16, 'そう思') - 0.05} x={140} y={150} size={88} enter="type" step={0.08} drift={[4, 0]} weight={800} glow="rgba(255,140,40,.5)" />
      <KText text={L(16).split('　')[1] ?? ''} t0={charT(16, 'そう思')} t1={b - 0.1} x={540} y={760} size={88} enter="type" step={0.08} drift={[-4, 0]} weight={800} glow="rgba(255,140,40,.5)" />
    </Fill>
  );
};

// ⑰ 光里的脸，唱最后一句；最后一拍光熄灭
const Face17: React.FC<{t: number}> = ({t}) => {
  const a = 79.7, b = 83.4;
  const off = T1(17) + 0.1;
  const dark = t >= off - E;
  return (
    <Fill>
      <Grade mode="heat" extra={dark ? 'brightness(.05)' : `brightness(${1 + 0.1 * stem('other', t, 2)})`}>
        <Cam s={1.08 + 0.12 * io(seg(t, a, off))} oy={520}><Sing ids={SING_FACE} on={!dark} /></Cam>
      </Grade>
      {!dark && <Motes n={60} color="#ffe0b0" size={3} op={0.7} glow seed={61} />}
      <KText text={L(17).split('　')[0]} t0={T0(17)} t1={charT(17, 'どう') - 0.05} x={1790} y={110} size={54} vertical enter="type" step={0.1} weight={700} color="#2b1206" glow="rgba(255,240,215,.9)" />
      <KText text={L(17).split('　')[1] ?? ''} t0={charT(17, 'どう')} t1={off - 0.05} x={60} y={110} size={54} vertical enter="type" step={0.1} weight={700} color="#2b1206" glow="rgba(255,240,215,.9)" />
    </Fill>
  );
};

// ================================================================ 间奏一 1:23.40–1:31.02
// 前奏的缝又出现了，但在转、在重影；"体温"在中心展开、掉下来、变灰、落在地平线上；推近，她回头，眼里有泪，戛然而止
export const Interlude1_9: React.FC = () => {
  const t = useT();
  const hits = [84.17, 85.12, 85.61, 86.53, 87.51, 89.87, 90.88];
  const g = hits.find((h) => t >= h - E && t < h + 3 / 24);
  const HY = 600;
  return (
    <Fill style={{background: '#000'}}>
      <Cut a={83.4} b={88.7}>
        <Fill style={{transform: `rotate(${Math.sin((t - 83.4) * 1.1) * 4}deg) scale(${1.15 + 0.25 * io(seg(t, 86.8, 88.7))})`, transformOrigin: `960px ${HY}px`}}>
          <Field temp="autumn" k={0.5} />
          <Fill style={{background: 'rgba(0,0,0,.65)'}} />
          <Glitch on={g !== undefined} seed={Math.round((g ?? 0) * 10)}>
            <Chroma d={6 + 10 * (g !== undefined ? 1 : 0)}>
              <Slit y={HY} h={lerp(80, 420, io(seg(t, 83.4, 88.7)))}>
                <Grade mode="autumn"><Cam x={-500 - 300 * seg(t, 83.4, 88.7)} y={HY - 600}><A id={1} /><A id={2} style={{opacity: seg(t, 85, 88)}} /></Cam></Grade>
              </Slit>
            </Chroma>
          </Glitch>
          <Horizon y={HY - lerp(80, 420, io(seg(t, 83.4, 88.7))) / 2} k={0.9} />
          <Horizon y={HY + lerp(80, 420, io(seg(t, 83.4, 88.7))) / 2} k={0.9} />
          <FallingWord t={t} HY={HY} />
        </Fill>
      </Cut>
      {/* 1:28.7–1:30.3：她回头（背后，三张），冷色的会场 */}
      <Cut a={88.7} b={90.3}>
        <Grade mode="autumn" extra="brightness(.9)">
          <Cam s={1.25 + 0.06 * seg(t, 88.7, 90.3)} x={-200}><A id={2} /></Cam>
          <Cam s={1.25 + 0.15 * io(seg(t, 88.7, 90.3))} oy={120} y={40}><A id={t < 89.37 - E ? 98 : t < 89.87 - E ? 99 : 100} /></Cam>
        </Grade>
        <Motes n={30} color="#ffd8a8" size={3} up={false} op={0.6} seed={71} />
      </Cut>
      {/* 1:30.3–1:31.02：眼里的泪，滑下来，切 */}
      <Cut a={90.3} b={91.02}>
        <Grade mode="autumn"><Cam s={1.05 + 0.04 * seg(t, 90.3, 91.0)}><A id={t < 90.65 - E ? 79 : 78} /></Cam></Grade>
      </Cut>
      <Letterbox h={t >= 88.7 ? 120 : 0} />
      <Vignette k={0.65} />
    </Fill>
  );
};

// 体温：在中心展开（字距从 0 拉开），掉下来，越掉越灰，落在地平线上弹一下
const FallingWord: React.FC<{t: number; HY: number}> = ({t, HY}) => {
  const a = 83.55, land = 86.53;
  if (t < a - E) return null;
  const open = ease(seg(t, a, a + 0.8));
  const fall = seg(t, a + 1.0, land);
  const y = lerp(260, HY - 150, fall * fall) + (t > land ? -24 * Math.abs(Math.sin((t - land) * 9)) * Math.exp(-(t - land) * 4) : 0);
  const grey = seg(t, a + 0.8, land + 0.4);
  const w = 300 + 380 * open;
  const col = `rgb(${Math.round(lerp(255, 120, grey))},${Math.round(lerp(236, 122, grey))},${Math.round(lerp(210, 126, grey))})`;
  return (
    <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
      <g style={{filter: `drop-shadow(0 0 ${30 * (1 - grey)}px rgba(255,140,40,.9))`}}>
        <GlyphWord data={GL} word="体温" x={960 - w / 2} y={y} w={w} h={150} fill={col}
          warp={(x, yy, i) => [x + (i ? 1 : -1) * 40 * open * (1 - fall), yy + (t > land ? 0 : Math.sin(x * 0.02 + t * 6) * 3 * fall)]} />
      </g>
    </svg>
  );
};
void CREAM; void near; void on12; void shake;
void Scene3D; void Plane; void Hole;
